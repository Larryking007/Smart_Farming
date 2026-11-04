"""Owner: Weather/data. Stub returns fake data; replace with real Open-Meteo calls.

Real endpoints:
  Geocoding: https://geocoding-api.open-meteo.com/v1/search?name=Akure&count=1
  Forecast:  https://api.open-meteo.com/v1/forecast?latitude=..&longitude=..
             &daily=temperature_2m_max,temperature_2m_min,precipitation_sum
             &hourly=soil_moisture_0_to_1cm&forecast_days=14&timezone=auto
TODO: use requests with timeout=10, raise APIRequestError on failure,
      InvalidLocationError if geocoding returns no results,
      ForecastUnavailableError if fields are missing/None.
"""
from datetime import date, timedelta
from models import Location, DailyForecast


class WeatherClient:
    def __init__(self, use_mock=True, timeout=10):
        self.use_mock = use_mock
        self.timeout = timeout

    def geocode(self, name):
        """Place name -> Location."""
        return Location(name=name, lat=7.25, lon=5.19)  # mock

    def get_forecast(self, lat, lon, days=14):
        """Returns a list[DailyForecast] of length `days`."""
        today = date.today()
        return [
            DailyForecast(
                date=(today + timedelta(days=i)).isoformat(),
                temp_max=30 + (i % 4),
                temp_min=21,
                rain_mm=0.0 if i % 5 else 18.0,
                soil_moisture=0.28,
            )
            for i in range(days)
        ]
