"""Shared data shapes. Owner: Storage/models. Do not change field names without telling the team."""

class Location:
    def __init__(self, name: str, lat: float, lon: float):
        self.name = name
        self.lat = lat
        self.lon = lon


class Crop:
    def __init__(self, name: str, min_temp: float, max_temp: float, water_mm_per_week: float, days_to_harvest: int):
        self.name = name
        self.min_temp = min_temp #below this temperature, the crop will not grow well
        self.max_temp = max_temp #above this temperature, the crop will not grow well
        self.water_mm_per_week = water_mm_per_week
        self.days_to_harvest = days_to_harvest
        self.weeding_days = []
        self.common_pests = []


class DailyForecast:
    def __init__(self, date: str, temp_max: float, temp_min: float, rain_mm: float):
        self.date = date #YYYY-MM-DD
        self.temp_max = temp_max
        self.temp_min = temp_min
        self.rain_mm = rain_mm
        self.soil_moisture = None   # m3/m3, modeled estimate



class Advice:
    def __init__(self, plant_now: bool, best_window: str, irrigation: str, pest_risks: list = None, summary: str = "", source: str = "rules"):
        self.plant_now = plant_now
        self.best_window = best_window #2024-06-01 to 2024-06-07
        self.irrigation = irrigation
        self.pest_risks = pest_risks if pest_risks is not None else []
        self.summary = summary
        self.source = source
    summary: str = ""
    source: str = "rules"    # "gemini" or "rules" (fallback)



class Activity:
    def __init__(self, date: str, kind: str, notes: str = ""):
        self.date = date
        self.kind = kind # planting | weeding | harvest | irrigation | pest_control
        self.notes = notes


class CalendarEvent:
    def __init__(self, date: str, title: str, kind: str):
        self.date = date
        self.title = title
        self.kind = kind # planting | weeding | harvest


class WeatherAlert:
    def __init__(self, date: str, level: str, message: str):
        self.date = date
        self.level = level # "warning" | "danger"
        self.message = message


class FarmPlot:
    def __init__(self, plot_id: str, name: str, location: Location, crop_name: str, planting_date: list[str] = None):
        self.plot_id = plot_id
        self.name = name
        self.location = location
        self.crop_name = crop_name
        self.planting_date = planting_date
        self.activities = []    #list of Activity objects
        self.calendar = []  #list of CalendarEvent objects

    def to_dict(self):
        return {
            "plot_id": self.plot_id,
            "name": self.name,
            "location": {
                "name": self.location.name,
                "lat": self.location.lat,
                "lon": self.location.lon
            },
            "crop_name": self.crop_name,
            "planting_date": self.planting_date,
            "activities": [vars(a) for a in self.activities],
            "calendar": [vars(e) for e in self.calendar]
        }
