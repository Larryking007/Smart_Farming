"""Shared data shapes. Owner: Storage/models. Do not change field names without telling the team."""
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Location:
    name: str
    lat: float
    lon: float


@dataclass
class Crop:
    name: str
    min_temp: float          # deg C, below this the crop suffers
    max_temp: float          # deg C, above this the crop suffers
    water_mm_per_week: float
    days_to_harvest: int
    weeding_days: list = field(default_factory=list)   # days after planting
    common_pests: list = field(default_factory=list)


@dataclass
class DailyForecast:
    date: str                # "YYYY-MM-DD"
    temp_max: float
    temp_min: float
    rain_mm: float
    soil_moisture: Optional[float] = None   # m3/m3, modeled estimate


@dataclass
class Advice:
    plant_now: bool
    best_window: str         # e.g. "2026-11-10 to 2026-11-17"
    irrigation: str
    pest_risks: list = field(default_factory=list)
    summary: str = ""
    source: str = "rules"    # "gemini" or "rules" (fallback)


@dataclass
class Activity:
    date: str
    kind: str                # planting | weeding | fertilizing | irrigation | harvest | other
    notes: str = ""


@dataclass
class CalendarEvent:
    date: str
    title: str
    kind: str                # planting | weeding | harvest


@dataclass
class WeatherAlert:
    date: str
    level: str               # "warning" | "danger"
    message: str


@dataclass
class FarmPlot:
    plot_id: str
    name: str
    location: Location
    crop_name: str
    planting_date: Optional[str] = None
    activities: list = field(default_factory=list)   # list[Activity]
    calendar: list = field(default_factory=list)     # list[CalendarEvent]

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(
            plot_id=d["plot_id"], name=d["name"], location=Location(**d["location"]),
            crop_name=d["crop_name"], planting_date=d.get("planting_date"),
            activities=[Activity(**a) for a in d.get("activities", [])],
            calendar=[CalendarEvent(**c) for c in d.get("calendar", [])],
        )
