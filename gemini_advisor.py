"""
Gemini-powered planting advice for Smart Farming.

Expected by advisor.py:
    build_user_prompt(crop, location, forecast, flags, today=None)
    call_gemini(api_key, user_prompt, model=None, timeout=30, retries=1)
    validate_response(data, forecast)
    to_advice(data)

Keep API keys in environment variables. Never commit them to GitHub.
"""

from __future__ import annotations

import json
import os
import time
from datetime import date, datetime
from typing import Any, Iterable

import requests

from exceptions import APIRequestError, AdviceFormatError
from models import Advice


DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)

# Gemini's structured-output schema keeps responses predictable.
RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "plant_now": {"type": "BOOLEAN"},
        "confidence": {
            "type": "STRING",
            "enum": ["low", "medium", "high"],
        },
        "best_window_start": {"type": "STRING"},
        "best_window_end": {"type": "STRING"},
        "irrigation_needed": {"type": "BOOLEAN"},
        "irrigation_advice": {"type": "STRING"},
        "pest_disease_risks": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
        },
        "weather_concerns": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
        },
        "summary": {"type": "STRING"},
    },
    "required": [
        "plant_now",
        "confidence",
        "best_window_start",
        "best_window_end",
        "irrigation_needed",
        "irrigation_advice",
        "pest_disease_risks",
        "weather_concerns",
        "summary",
    ],
}


def _value(obj: Any, name: str, default: Any = None) -> Any:
    """Read a field from either a dictionary or a model object."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _as_date(value: Any) -> date | None:
    """Convert a date/datetime/ISO date string to a date."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def _clean_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def build_user_prompt(
    crop: Any,
    location: Any,
    forecast: Iterable[Any],
    flags: dict[str, Any],
    today: date | None = None,
) -> str:
    """Build a clear, data-grounded prompt from the project's model objects."""
    forecast = list(forecast or [])
    today = today or date.today()

    crop_details = {
        "name": _value(crop, "name", "Unknown crop"),
        "minimum suitable temperature (C)": _value(crop, "min_temp"),
        "maximum suitable temperature (C)": _value(crop, "max_temp"),
        "weekly water requirement (mm)": _value(crop, "water_mm_per_week"),
        "days to harvest": _value(crop, "days_to_harvest"),
        "common pests": _clean_list(_value(crop, "common_pests", [])),
    }
    location_details = {
        "name": _value(location, "name", "Unknown location"),
        "latitude": _value(location, "lat"),
        "longitude": _value(location, "lon"),
    }

    forecast_rows = []
    for day in forecast:
        forecast_rows.append({
            "date": str(_value(day, "date", "")),
            "maximum temperature C": _value(day, "temp_max"),
            "minimum temperature C": _value(day, "temp_min"),
            "rainfall mm": _value(day, "rain_mm"),
            "soil moisture": _value(day, "soil_moisture"),
        })

    return f"""
You are a careful agricultural decision-support assistant.
Assess whether the crop below should be planted using ONLY the supplied
crop profile, location, computed flags, and weather forecast.

CURRENT DATE: {today.isoformat()}

CROP PROFILE:
{json.dumps(crop_details, indent=2, default=str)}

LOCATION:
{json.dumps(location_details, indent=2, default=str)}

COMPUTED WEATHER FLAGS:
{json.dumps(flags or {}, indent=2, default=str)}

FORECAST:
{json.dumps(forecast_rows, indent=2, default=str)}

RULES:
1. Never invent weather observations, forecast dates, measurements, or crop facts.
2. Base the recommendation on the supplied forecast and crop requirements.
3. Use a planting window only when its dates exist in the supplied forecast.
4. If no suitable window exists, set both window dates to empty strings.
5. Set plant_now to true only when the available evidence supports planting.
6. Explain irrigation in practical, cautious language. Do not prescribe an
   exact quantity unless the supplied data supports it.
7. Mention plausible pest/disease risks only when supported by crop or weather
   context. If there is no clear risk, return an empty list.
8. Keep the summary concise and explain the main reason for the decision.
9. Return only the JSON object required by the response schema.
""".strip()


def _extract_response_text(payload: dict[str, Any]) -> str:
    """Safely extract generated text from a Gemini response."""
    candidates = payload.get("candidates") or []
    if not candidates:
        feedback = payload.get("promptFeedback", {})
        reason = feedback.get("blockReason", "No candidate returned")
        raise APIRequestError(f"Gemini did not return an answer: {reason}")

    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    text_parts = [
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and part.get("text")
    ]
    if not text_parts:
        finish_reason = candidates[0].get("finishReason", "unknown")
        raise APIRequestError(
            f"Gemini returned no text (finish reason: {finish_reason})."
        )
    return "\n".join(text_parts).strip()


def _parse_json_response(text: str) -> dict[str, Any]:
    """Parse JSON, including a defensive fallback for fenced responses."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise AdviceFormatError(
            f"Gemini returned invalid JSON: {exc.msg}."
        ) from exc

    if not isinstance(result, dict):
        raise AdviceFormatError("Gemini response must be a JSON object.")
    return result


def call_gemini(
    api_key: str,
    user_prompt: str,
    model: str | None = None,
    timeout: int = 30,
    retries: int = 1,
) -> dict[str, Any]:
    """
    Send a prompt to Gemini and return its parsed JSON response.

    Retries temporary network/server/rate-limit errors only. Authentication,
    invalid-model, and malformed-request errors are returned immediately.
    """
    if not api_key or not api_key.strip():
        raise APIRequestError(
            "GEMINI_API_KEY is missing. Add it to your environment."
        )
    if not user_prompt or not user_prompt.strip():
        raise APIRequestError("The Gemini prompt cannot be empty.")

    selected_model = (model or DEFAULT_MODEL).strip()
    url = API_URL.format(model=selected_model)
    headers = {
        "x-goog-api-key": api_key.strip(),
        "Content-Type": "application/json",
    }
    body = {
        "systemInstruction": {
            "parts": [{
                "text": (
                    "You are a cautious agricultural advisor. "
                    "Follow the user's data and output requirements exactly."
                )
            }]
        },
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
            "responseJsonSchema": RESPONSE_SCHEMA,
        },
    }

    attempts = max(0, int(retries)) + 1
    retryable_statuses = {408, 429, 500, 502, 503, 504}
    last_error: Exception | None = None

    for attempt in range(attempts):
        try:
            response = requests.post(
                url,
                headers=headers,
                json=body,
                timeout=timeout,
            )

            if response.status_code >= 400:
                message = ""
                try:
                    error_data = response.json()
                    message = error_data.get("error", {}).get("message", "")
                except (ValueError, AttributeError):
                    message = response.text[:500]

                error = APIRequestError(
                    f"Gemini API error {response.status_code}: "
                    f"{message or response.reason}"
                )
                if (
                    response.status_code not in retryable_statuses
                    or attempt == attempts - 1
                ):
                    raise error
                last_error = error
                time.sleep(min(2 ** attempt, 8))
                continue

            try:
                payload = response.json()
            except ValueError as exc:
                raise APIRequestError(
                    "Gemini returned a response that was not valid JSON."
                ) from exc

            response_text = _extract_response_text(payload)
            return _parse_json_response(response_text)

        except requests.Timeout as exc:
            last_error = APIRequestError(
                f"Gemini request timed out after {timeout} seconds."
            )
            if attempt == attempts - 1:
                raise last_error from exc
        except requests.ConnectionError as exc:
            last_error = APIRequestError(
                "Could not connect to Gemini. Check your internet connection."
            )
            if attempt == attempts - 1:
                raise last_error from exc
        except requests.RequestException as exc:
            raise APIRequestError(f"Gemini network error: {exc}") from exc

        if attempt < attempts - 1:
            time.sleep(min(2 ** attempt, 8))

    raise last_error or APIRequestError("Gemini request failed.")


def validate_response(
    data: dict[str, Any],
    forecast: Iterable[Any],
) -> dict[str, Any]:
    """Validate Gemini's output before it is used by the application."""
    if not isinstance(data, dict):
        raise AdviceFormatError("Advice must be a JSON object.")

    required = {
        "plant_now",
        "confidence",
        "best_window_start",
        "best_window_end",
        "irrigation_needed",
        "irrigation_advice",
        "pest_disease_risks",
        "weather_concerns",
        "summary",
    }
    missing = required.difference(data)
    if missing:
        raise AdviceFormatError(
            "Gemini response is missing: " + ", ".join(sorted(missing))
        )

    for field in ("plant_now", "irrigation_needed"):
        if not isinstance(data[field], bool):
            raise AdviceFormatError(f"'{field}' must be true or false.")

    if data["confidence"] not in {"low", "medium", "high"}:
        raise AdviceFormatError(
            "'confidence' must be low, medium, or high."
        )

    for field in ("irrigation_advice", "summary"):
        if not isinstance(data[field], str) or not data[field].strip():
            raise AdviceFormatError(f"'{field}' must be a non-empty string.")

    for field in ("best_window_start", "best_window_end"):
        if not isinstance(data[field], str):
            raise AdviceFormatError(f"'{field}' must be a string.")

    for field in ("pest_disease_risks", "weather_concerns"):
        if not isinstance(data[field], list) or not all(
            isinstance(item, str) and item.strip() for item in data[field]
        ):
            raise AdviceFormatError(f"'{field}' must be a list of text items.")

    start_text = data["best_window_start"].strip()
    end_text = data["best_window_end"].strip()

    # Empty dates mean that no suitable planting window was identified.
    if bool(start_text) != bool(end_text):
        raise AdviceFormatError(
            "Both planting-window dates must be supplied together."
        )

    forecast_dates = {
        parsed
        for parsed in (_as_date(_value(day, "date")) for day in forecast or [])
        if parsed is not None
    }

    if start_text and end_text:
        start = _as_date(start_text)
        end = _as_date(end_text)
        if start is None or end is None:
            raise AdviceFormatError(
                "Planting-window dates must use YYYY-MM-DD format."
            )
        if start > end:
            raise AdviceFormatError(
                "Planting-window start date cannot be after its end date."
            )
        if start not in forecast_dates or end not in forecast_dates:
            raise AdviceFormatError(
                "Planting-window dates must exist in the supplied forecast."
            )
    elif data["plant_now"]:
        raise AdviceFormatError(
            "Gemini cannot recommend planting now without a valid window."
        )

    return data


def to_advice(data: dict[str, Any]) -> Advice:
    """Convert validated Gemini data to the project's Advice model."""
    start = data.get("best_window_start", "").strip()
    end = data.get("best_window_end", "").strip()
    best_window = (
        f"{start} to {end}"
        if start and end
        else "No good window in the available forecast"
    )

    risks = _clean_list(data.get("pest_disease_risks", []))
    risks.extend(
        f"Weather concern: {item}"
        for item in _clean_list(data.get("weather_concerns", []))
    )

    irrigation = data.get("irrigation_advice", "").strip()
    if data.get("irrigation_needed") and not irrigation:
        irrigation = "Irrigation may be needed; check soil moisture."
    elif not data.get("irrigation_needed") and not irrigation:
        irrigation = "No immediate irrigation is indicated by the forecast."

    return Advice(
        plant_now=data["plant_now"],
        best_window=best_window,
        irrigation=irrigation,
        pest_risks=risks,
        summary=data["summary"].strip(),
        source="gemini",
    )
