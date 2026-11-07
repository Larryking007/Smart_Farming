"""Owner: Lead. Console smoke test wiring every module. The Tkinter UI will call the same functions."""
from weather_client import WeatherClient
from advisor import PlantingAdvisor
from crops import get_crop
from calendar_gen import build_season_calendar, detect_alerts
from models import FarmPlot
from store import FarmLogStore
from validators import validate_date
from exceptions import FarmAdvisorError


def run(planting_date="2026-11-10"):
    try:
        crop = get_crop(input(f"Enter crop name (e.g. maize, cassava, tomato, rice): "))
        loc = input(f"Enter location name (e.g. city, village, region): ")
        client = WeatherClient()
        forecast = client.get_forecast()
        advice = PlantingAdvisor().advise(crop, forecast)
        alerts = detect_alerts(crop, forecast)
        plot = FarmPlot("p1", "North field", loc, crop.name, validate_date(planting_date))
        plot.calendar = build_season_calendar(plot.planting_date, crop)
        FarmLogStore().save([plot])
        print(advice)
        print(alerts)
        print(plot.calendar)
    except FarmAdvisorError as e:
        print("Error:", e)


if __name__ == "__main__":
    run("2026-11-10")
