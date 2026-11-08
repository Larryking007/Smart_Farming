
import unittest
from datetime import date, timedelta

from models import Crop, DailyForecast
from calendar_gen import build_season_calendar, detect_alerts


class TestSeasonCalendar(unittest.TestCase):

    def setUp(self):
        self.crop = Crop(
            name="maize",
            min_temp=15,
            max_temp=35,
            water_mm_per_week=25,
            days_to_harvest=110,
            weeding_days=[14, 35],
        )

    def test_builds_expected_events(self):
        events = build_season_calendar("2026-11-06", self.crop)

        self.assertEqual(len(events), 4)
        self.assertEqual(events[0].date, "2026-11-06")
        self.assertEqual(events[0].kind, "planting")
        self.assertEqual(events[-1].kind, "harvest")
        self.assertEqual(events[-1].date, "2027-02-24")

    def test_events_are_chronological(self):
        events = build_season_calendar("2026-11-06", self.crop)

        dates = [event.date for event in events]
        self.assertEqual(dates, sorted(dates))

    def test_rejects_invalid_planting_date(self):
        with self.assertRaises(ValueError):
            build_season_calendar("06-11-2026", self.crop)

    def test_rejects_weeding_after_harvest(self):
        self.crop.weeding_days = [120]

        with self.assertRaises(ValueError):
            build_season_calendar("2026-11-06", self.crop)


class TestWeatherAlerts(unittest.TestCase):

    def setUp(self):
        self.crop = Crop("maize", 15, 35, 25, 110, [14, 35])
        self.start = date(2026, 11, 6)

    def make_forecast(self, rain, temp=30, day_offset=0):
        current_date = self.start + timedelta(days=day_offset)

        return DailyForecast(
            date=current_date.strftime("%Y-%m-%d"),
            temp_max=temp,
            temp_min=22,
            rain_mm=rain,
        )

    def test_detects_heavy_rain(self):
        alerts = detect_alerts(
            self.crop,
            [self.make_forecast(60)],
        )

        self.assertTrue(any("Heavy rain" in a.message for a in alerts))

    def test_detects_heatwave(self):
        alerts = detect_alerts(
            self.crop,
            [self.make_forecast(5, temp=40)],
        )

        self.assertTrue(any("Heatwave" in a.message for a in alerts))

    def test_detects_dry_spell(self):
        forecast = [
            self.make_forecast(0, day_offset=i)
            for i in range(7)
        ]

        alerts = detect_alerts(self.crop, forecast)

        self.assertTrue(any("Dry spell" in a.message for a in alerts))

    def test_only_one_alert_per_continuous_dry_spell(self):
        forecast = [
            self.make_forecast(0, day_offset=i)
            for i in range(10)
        ]

        alerts = detect_alerts(self.crop, forecast)

        dry_alerts = [a for a in alerts if "Dry spell" in a.message]
        self.assertEqual(len(dry_alerts), 1)

    def test_forecast_order_does_not_change_dry_spell_detection(self):
        forecast = [
            self.make_forecast(0, day_offset=i)
            for i in range(7)
        ]

        alerts = detect_alerts(self.crop, list(reversed(forecast)))

        self.assertTrue(any("Dry spell" in a.message for a in alerts))

    def test_missing_forecast_days_break_dry_spell(self):
        forecast = [
            self.make_forecast(0, day_offset=i)
            for i in range(6)
        ]
        forecast.append(self.make_forecast(0, day_offset=8))

        alerts = detect_alerts(self.crop, forecast)

        self.assertFalse(any("Dry spell" in a.message for a in alerts))

    def test_rejects_invalid_dry_spell_threshold(self):
        with self.assertRaises(ValueError):
            detect_alerts(self.crop, [], dry_spell_days=0)


if __name__ == "__main__":
    unittest.main()
