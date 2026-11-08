"""Owner: AI/advisor. Stub uses simple rules. Add Gemini call, keep rules as fallback.

Plan: compute_flags() -> numbers; build prompt from flags + crop; ask Gemini for JSON
{plant_now, best_window, irrigation, pest_risks, summary}; validate; on any
APIRequestError or bad JSON, return rule-based Advice (source="rules").
"""
import os

from exceptions import FarmAdvisorError
from gemini_advisor import build_user_prompt, call_gemini, validate_response, to_advice
from models import Advice

class PlantingAdvisor:
    def __init__(self, gemini_api_key=None):
        self.api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY")
        self.last_error = None   # why the last call fell back to rules (for the UI status bar)

    def compute_flags(self, crop, forecast):
        week = forecast[:7]
        rain_7d = sum(d.rain_mm for d in week)
        avg_max = sum(d.temp_max for d in week) / len(week)
        return {
            "rain_7d_mm": rain_7d,
            "avg_max_temp": avg_max,
            "too_hot": avg_max > crop.max_temp,
            "too_cold": avg_max < crop.min_temp,
            "dry_week": rain_7d < crop.water_mm_per_week * 0.5,
        }

    def advise(self, crop, forecast, location=None):
        """Gemini advice when a key and location are available; rule-based advice otherwise."""
        self.last_error = None
        if self.api_key and location is not None:
            try:
                flags = self.compute_flags(crop, forecast)
                data = call_gemini(self.api_key, build_user_prompt(crop, location, forecast, flags))
                return to_advice(validate_response(data, forecast))
            except FarmAdvisorError as e:
                self.last_error = str(e)   # fall through to the rules
        return self.advise_with_rules(crop, forecast)

    def advise_with_rules(self, crop, forecast):
        f = self.compute_flags(crop, forecast)
        ok = not (f["too_hot"] or f["too_cold"])
        return Advice(
            plant_now=ok,
            best_window=f"{forecast[0].date} to {forecast[6].date}" if ok else "Wait and re-check",
            irrigation="Irrigate" if f["dry_week"] else "Rainfall looks sufficient",
            pest_risks=list(crop.common_pests),
            summary=f"7-day rain {f['rain_7d_mm']:.0f} mm, avg high {f['avg_max_temp']:.0f} C.",
            source="rules",
        )
