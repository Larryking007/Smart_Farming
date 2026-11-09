"""
AI Planting Advisor
Uses Gemini AI when available and rule-based advice as a fallback.
"""

import os

from exceptions import FarmAdvisorError, ForecastUnavailableError
from gemini_advisor import (
    build_user_prompt,
    call_gemini,
    validate_response,
    to_advice,
)
from models import Advice


class PlantingAdvisor:

    def __init__(self, gemini_api_key=None):
        self.api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY")
        self.last_error = None

    def compute_flags(self, crop, forecast):
        """Calculate basic weather conditions for the selected crop."""

        if not forecast:
            raise ForecastUnavailableError("No forecast data available.")

        week = forecast[:7]

        rain_7d = sum(day.rain_mm for day in week)
        avg_max = sum(day.temp_max for day in week) / len(week)

        return {
            "rain_7d_mm": rain_7d,
            "avg_max_temp": avg_max,
            "too_hot": avg_max > crop.max_temp,
            "too_cold": avg_max < crop.min_temp,
            "dry_week": rain_7d < crop.water_mm_per_week * 0.5,
        }

    def advise(self, crop, forecast, location=None):
        """
        Generate planting advice using Gemini.
        If Gemini fails, use the rule-based system.
        """

        self.last_error = None

        if not forecast:
            raise ForecastUnavailableError("Forecast data is missing.")

        if self.api_key and location is not None:
            try:
                flags = self.compute_flags(crop, forecast)

                prompt = build_user_prompt(
                    crop,
                    location,
                    forecast,
                    flags
                )

                response = call_gemini(self.api_key, prompt)

                valid_response = validate_response(
                    response,
                    forecast
                )

                return to_advice(valid_response)

            except FarmAdvisorError as error:
                self.last_error = str(error)

        return self.advise_with_rules(crop, forecast)

    def advise_with_rules(self, crop, forecast):
        """Provide basic planting advice without AI."""

        flags = self.compute_flags(crop, forecast)

        suitable_temperature = not (
            flags["too_hot"] or flags["too_cold"]
        )

        planting_window = (
            f"{forecast[0].date} to {forecast[-1].date}"
            if suitable_temperature
            else "Wait and check the weather again"
        )

        irrigation = (
            "Additional irrigation may be needed because rainfall is low."
            if flags["dry_week"]
            else "Rainfall appears sufficient for now."
        )

        pests = list(crop.common_pests)

        summary = (
            f"Total rainfall over the forecast period is "
            f"{flags['rain_7d_mm']:.1f} mm. "
            f"Average daily maximum temperature is "
            f"{flags['avg_max_temp']:.1f} degrees Celsius."
        )

        return Advice(
            plant_now=suitable_temperature,
            best_window=planting_window,
            irrigation=irrigation,
            pest_risks=pests,
            summary=summary,
            source="rules"
        )
        

    
