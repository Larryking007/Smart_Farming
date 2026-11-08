"""Geocode locations and provide daily weather forecasts."""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from exceptions import APIRequestError, InvalidInputError, InvalidLocationError, ForecastUnavailableError
from models import Location, DailyForecast

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT_SECONDS = 10
MAX_FORECAST_DAYS = 16


def _get_json(base_url: str, params: dict, operation: str) -> dict:
    request_url = f"{base_url}?{urlencode(params)}"
    try:
        with urlopen(request_url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise APIRequestError(
            f"{operation} request failed with HTTP {error.code}."
        ) from error
    except (URLError, TimeoutError, OSError) as error:
        raise APIRequestError(f"{operation} request failed: {error}.") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise APIRequestError(f"{operation} returned an invalid response.") from error

    if not isinstance(data, dict):
        raise APIRequestError(f"{operation} returned an invalid response.")
    return data


class WeatherClient:
    """Client for Open-Meteo geocoding and forecast APIs."""

    def geocode(self, name: str = "Akure") -> Location:
        """Resolve a place name to its first matching location."""
        data = _get_json(
            GEOCODING_URL,
            {
                "name": name,
                "count": 1,
                "language": "en",
                "format": "json",
            },
            "Geocoding",
        )
        results = data.get("results", [])
        if not results:
            raise InvalidLocationError(f"No results found for location: {name}")

        city = results[0]
        try:
            return Location(
                name=city["name"],
                lat=float(city["latitude"]),
                lon=float(city["longitude"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise APIRequestError("Geocoding returned incomplete location data.") from error

    def get_forecast(
        self, lat: float, lon: float, days: int = 14
    ) -> list[DailyForecast]:
        """Fetch daily weather and average hourly soil moisture by date."""
        if not isinstance(days, int) or not 1 <= days <= MAX_FORECAST_DAYS:
            raise InvalidInputError(
                f"days must be between 1 and {MAX_FORECAST_DAYS}."
            )
        if not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise InvalidInputError("Latitude or longitude is out of range.")

        data = _get_json(
            WEATHER_URL,
            {
                "latitude": lat,
                "longitude": lon,
                "daily": (
                    "temperature_2m_max,temperature_2m_min,precipitation_sum"
                ),
                "hourly": "soil_moisture_0_to_1cm",
                "forecast_days": days,
                "timezone": "auto",
            },
            "Forecast",
        )

        try:
            daily = data["daily"]
            dates = daily["time"]
            temp_max = daily["temperature_2m_max"]
            temp_min = daily["temperature_2m_min"]
            rain = daily["precipitation_sum"]
            if not all(len(values) == len(dates) for values in (temp_max, temp_min, rain)):
                raise ValueError("Daily forecast arrays have different lengths.")
            if len(dates) != days:
                raise ValueError("Forecast did not contain the requested number of days.")

            hourly = data.get("hourly", {})
            moisture_by_date: dict[str, list[float]] = {}
            for timestamp, moisture in zip(
                hourly.get("time", []),
                hourly.get("soil_moisture_0_to_1cm", []),
            ):
                if moisture is not None:
                    forecast_date = timestamp.split("T", 1)[0]
                    moisture_by_date.setdefault(forecast_date, []).append(float(moisture))

            forecasts = []
            for index, forecast_date in enumerate(dates):
                moisture_values = moisture_by_date.get(forecast_date, [])
                soil_moisture = (
                    sum(moisture_values) / len(moisture_values)
                    if moisture_values
                    else None
                )
                forecasts.append(
                    DailyForecast(
                        date=forecast_date,
                        temp_max=float(temp_max[index]),
                        temp_min=float(temp_min[index]),
                        rain_mm=float(rain[index]),
                        soil_moisture=soil_moisture,
                    )
                )
        except (KeyError, TypeError, ValueError, IndexError) as error:
            raise ForecastUnavailableError(
                "Open-Meteo returned incomplete or invalid forecast data."
            ) from error

        return forecasts