import json
import unittest
from datetime import date
from unittest.mock import Mock, patch

from exceptions import APIRequestError, AdviceFormatError
from gemini_advisor import (
    build_user_prompt,
    call_gemini,
    to_advice,
    validate_response,
)
from models import Crop, DailyForecast, Location


class TestGeminiAdvisor(unittest.TestCase):

    def setUp(self):
        self.crop = Crop("maize", 15, 35, 25, 110, common_pests=["stem borer"])
        self.location = Location("Akure", 7.25, 5.2)
        self.forecast = [
            DailyForecast("2026-11-12", 31, 22, 4),
            DailyForecast("2026-11-13", 30, 21, 3),
        ]
        self.response_data = {
            "plant_now": True,
            "confidence": "high",
            "best_window_start": "2026-11-12",
            "best_window_end": "2026-11-13",
            "irrigation_needed": False,
            "irrigation_advice": "Rainfall should be sufficient for now.",
            "pest_disease_risks": ["Stem borer"],
            "weather_concerns": ["Check the forecast for heavy rain."],
            "summary": "Temperatures are suitable for planting.",
        }

    def test_build_user_prompt_includes_inputs_and_today(self):
        prompt = build_user_prompt(
            self.crop,
            self.location,
            self.forecast,
            {"dry_week": False},
            today=date(2026, 11, 12),
        )

        self.assertIn('"name": "maize"', prompt)
        self.assertIn('"name": "Akure"', prompt)
        self.assertIn('"dry_week": false', prompt)
        self.assertIn("CURRENT DATE: 2026-11-12", prompt)

    def test_validate_response_accepts_forecast_window(self):
        validated = validate_response(self.response_data, self.forecast)

        self.assertIs(validated, self.response_data)

    def test_validate_response_rejects_missing_required_field(self):
        invalid_response = dict(self.response_data)
        del invalid_response["summary"]

        with self.assertRaisesRegex(AdviceFormatError, "summary"):
            validate_response(invalid_response, self.forecast)

    def test_validate_response_rejects_dates_outside_forecast(self):
        invalid_response = dict(self.response_data)
        invalid_response["best_window_end"] = "2026-11-14"

        with self.assertRaisesRegex(AdviceFormatError, "must exist"):
            validate_response(invalid_response, self.forecast)

    def test_to_advice_combines_pest_and_weather_risks(self):
        advice = to_advice(self.response_data)

        self.assertTrue(advice.plant_now)
        self.assertEqual(advice.best_window, "2026-11-12 to 2026-11-13")
        self.assertEqual(advice.pest_risks, [
            "Stem borer",
            "Weather concern: Check the forecast for heavy rain.",
        ])
        self.assertEqual(advice.source, "gemini")

    @patch("gemini_advisor.requests.post")
    def test_call_gemini_parses_response_without_network(self, post):
        response = Mock(status_code=200)
        response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{"text": json.dumps(self.response_data)}],
                },
            }],
        }
        post.return_value = response

        result = call_gemini("test-key", "test prompt", model="test-model", retries=0)

        self.assertEqual(result, self.response_data)
        post.assert_called_once()
        self.assertIn("test-model:generateContent", post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs["headers"]["x-goog-api-key"], "test-key")

    @patch("gemini_advisor.requests.post")
    def test_call_gemini_raises_for_auth_error_without_retry(self, post):
        response = Mock(status_code=401, reason="Unauthorized")
        response.json.return_value = {"error": {"message": "Invalid API key"}}
        post.return_value = response

        with self.assertRaisesRegex(APIRequestError, "401"):
            call_gemini("test-key", "test prompt", retries=0)

        post.assert_called_once()


if __name__ == "__main__":
    unittest.main()