"""Owner: Calendar/alerts. Both functions work at a basic level; refine thresholds."""
from datetime import datetime, timedelta
from models import CalendarEvent, WeatherAlert


def build_season_calendar(planting_date, crop):
    start = datetime.strptime(planting_date, "%Y-%m-%d")
    fmt = lambda d: d.strftime("%Y-%m-%d")
    events = [CalendarEvent(fmt(start), f"Plant {crop.name}", "planting")]
    for n, day in enumerate(crop.weeding_days, 1):
        events.append(CalendarEvent(fmt(start + timedelta(days=day)), f"Weeding #{n}", "weeding"))
    events.append(CalendarEvent(fmt(start + timedelta(days=crop.days_to_harvest)), "Harvest", "harvest"))
    return sorted(events, key=lambda e: e.date)


def detect_alerts(crop, forecast, heavy_rain_mm=50, dry_spell_days=7):
    alerts, dry_run = [], 0
    for d in forecast:
        if d.rain_mm >= heavy_rain_mm:
            alerts.append(WeatherAlert(d.date, "danger", f"Heavy rain expected ({d.rain_mm:.0f} mm)"))
        if d.temp_max > crop.max_temp + 3:
            alerts.append(WeatherAlert(d.date, "warning", f"Heatwave risk ({d.temp_max:.0f} C)"))
        dry_run = dry_run + 1 if d.rain_mm < 1 else 0
        if dry_run == dry_spell_days:
            alerts.append(WeatherAlert(d.date, "warning", f"Dry spell: {dry_spell_days}+ days without rain"))
    return alerts
