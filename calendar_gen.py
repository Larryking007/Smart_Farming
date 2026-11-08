
"""Owner: Calendar/alerts.
Generates crop calendars and detects weather alerts.
"""

from datetime import datetime, timedelta

from models import CalendarEvent, WeatherAlert


def _parse_date(value):
    """Validate and parse a date in YYYY-MM-DD format."""
    if not isinstance(value, str):
        raise ValueError("Date must be a string in YYYY-MM-DD format.")

    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(
            f"Invalid date: {value!r}. Use YYYY-MM-DD."
        ) from exc

    if parsed.strftime("%Y-%m-%d") != value:
        raise ValueError(f"Invalid date format: {value!r}. Use YYYY-MM-DD.")

    return parsed


def build_season_calendar(planting_date, crop):
    """Generate planting, weeding, and harvest events for a crop."""

    start = _parse_date(planting_date)

    if not isinstance(crop.name, str) or not crop.name.strip():
        raise ValueError("Crop must have a valid name.")

    if (
        not isinstance(crop.days_to_harvest, int)
        or isinstance(crop.days_to_harvest, bool)
        or crop.days_to_harvest < 1
    ):
        raise ValueError("Days to harvest must be a positive integer.")

    if not isinstance(crop.weeding_days, list):
        raise ValueError("Crop weeding_days must be a list.")

    for day in crop.weeding_days:
        if (
            not isinstance(day, int)
            or isinstance(day, bool)
            or day < 1
            or day >= crop.days_to_harvest
        ):
            raise ValueError(
                "Each weeding day must be a positive integer "
                "before the harvest day."
            )

    events = [
        CalendarEvent(
            start.strftime("%Y-%m-%d"),
            f"Plant {crop.name}",
            "planting",
        )
    ]

    for number, day in enumerate(sorted(set(crop.weeding_days)), start=1):
        event_date = start + timedelta(days=day)
        events.append(
            CalendarEvent(
                event_date.strftime("%Y-%m-%d"),
                f"Weeding #{number}",
                "weeding",
            )
        )

    harvest_date = start + timedelta(days=crop.days_to_harvest)

    events.append(
        CalendarEvent(
            harvest_date.strftime("%Y-%m-%d"),
            "Harvest",
            "harvest",
        )
    )

    return sorted(events, key=lambda event: (event.date, event.kind))


def detect_alerts(
    crop,
    forecast,
    heavy_rain_mm=50,
    dry_spell_days=7,
    dry_rain_mm=1,
    heat_buffer_c=3,
):
    """
    Detect heavy rain, heat, and dry-spell alerts.

    Forecast items must provide date, rain_mm, and temp_max,
    as defined by the project's DailyForecast model.

    Thresholds are configurable defaults, not universal
    agricultural recommendations.
    """

    if not isinstance(dry_spell_days, int) or isinstance(
        dry_spell_days, bool
    ) or dry_spell_days < 1:
        raise ValueError("dry_spell_days must be a positive integer.")

    for name, value in (
        ("heavy_rain_mm", heavy_rain_mm),
        ("dry_rain_mm", dry_rain_mm),
        ("heat_buffer_c", heat_buffer_c),
    ):
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or value < 0
        ):
            raise ValueError(f"{name} must be a non-negative number.")

    if not isinstance(forecast, (list, tuple)):
        raise ValueError("Forecast must be a list or tuple.")

    if not isinstance(crop.max_temp, (int, float)):
        raise ValueError("Crop max_temp must be numeric.")

    daily_data = []

    for day in forecast:
        parsed_date = _parse_date(day.date)

        for field_name in ("rain_mm", "temp_max"):
            value = getattr(day, field_name)

            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or value < 0 and field_name == "rain_mm"
            ):
                raise ValueError(
                    f"Forecast {field_name} must contain a valid number."
                )

        daily_data.append((parsed_date, day))

    # Sort the data so dry spells are detected chronologically.
    daily_data.sort(key=lambda item: item[0])

    alerts = []
    dry_run = 0
    previous_date = None
    dry_spell_alerted = False

    for current_date, day in daily_data:
        date_text = current_date.strftime("%Y-%m-%d")

        # A gap in the forecast breaks a consecutive dry spell.
        if (
            previous_date is None
            or current_date - previous_date != timedelta(days=1)
        ):
            dry_run = 0
            dry_spell_alerted = False

        if day.rain_mm >= heavy_rain_mm:
            alerts.append(
                WeatherAlert(
                    date_text,
                    "danger",
                    f"Heavy rain expected ({day.rain_mm:.0f} mm)",
                )
            )

        if day.temp_max > crop.max_temp + heat_buffer_c:
            alerts.append(
                WeatherAlert(
                    date_text,
                    "warning",
                    f"Heatwave risk ({day.temp_max:.0f} C)",
                )
            )

        if day.rain_mm < dry_rain_mm:
            dry_run += 1

            if dry_run >= dry_spell_days and not dry_spell_alerted:
                alerts.append(
                    WeatherAlert(
                        date_text,
                        "warning",
                        f"Dry spell: {dry_spell_days}+ days without rain",
                    )
                )
                dry_spell_alerted = True
        else:
            dry_run = 0
            dry_spell_alerted = False

        previous_date = current_date

    return alerts
