import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from advisor import PlantingAdvisor
from models import Advice, DailyForecast, Location
from store import FarmLogStore
from streamlit.testing.v1 import AppTest
from weather_client import WeatherClient


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


class TestStreamlitAppFlows(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.location = Location("Akure", 7.25, 5.2)
        start_date = date(2026, 11, 12)
        self.forecast = [
            DailyForecast(
                (start_date + timedelta(days=offset)).isoformat(),
                40 if offset == 0 else 30,
                22,
                60 if offset == 0 else 0,
            )
            for offset in range(7)
        ]
        self.advice = Advice(
            True,
            "2026-11-12 to 2026-11-18",
            "Check soil moisture before irrigating.",
            ["Stem borer"],
            "The forecast is mostly suitable for planting.",
            "rules",
        )

    def run_app(self):
        def use_temp_store(store, path="farm_data.json"):
            store.path = str(Path(self.temp_dir.name) / "farm_data.json")

        store_patcher = patch.object(FarmLogStore, "__init__", use_temp_store)
        store_patcher.start()
        self.addCleanup(store_patcher.stop)
        return AppTest.from_file(str(APP_PATH)).run()

    def mock_geocoding(self):
        patcher = patch.object(
            WeatherClient,
            "geocode",
            return_value=self.location,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_saving_plot_persists_plot_and_calendar(self):
        self.mock_geocoding()
        app = self.run_app()
        app.text_input(key="farm_name").set_value("North Field")
        app.text_input(key="location").set_value("Akure")
        app.button(key="save_plot").click().run()

        self.assertFalse(app.exception)
        self.assertEqual(len(app.session_state.plots), 1)
        saved_plot = app.session_state.plots[0]
        self.assertEqual(saved_plot.name, "North Field")
        self.assertEqual(saved_plot.planting_date, date.today().isoformat())
        self.assertEqual(len(saved_plot.calendar), 4)

        reloaded_app = self.run_app()
        self.assertFalse(reloaded_app.exception)
        self.assertEqual(len(reloaded_app.session_state.plots), 1)
        self.assertEqual(reloaded_app.session_state.plots[0].name, "North Field")

    def test_planting_activity_updates_saved_calendar(self):
        self.mock_geocoding()
        app = self.run_app()
        app.text_input(key="farm_name").set_value("North Field")
        app.text_input(key="location").set_value("Akure")
        app.button(key="save_plot").click().run()
        plot_id = app.session_state.plots[0].plot_id

        app.selectbox(key="activity_plot_id").select(plot_id)
        app.text_area(key="activity_notes").set_value("Seedlings planted")
        app.form_submit_button[0].click().run()

        self.assertFalse(app.exception)
        saved_plot = app.session_state.plots[0]
        self.assertEqual(len(saved_plot.activities), 1)
        self.assertEqual(saved_plot.activities[0].kind, "planting")
        self.assertEqual(saved_plot.activities[0].notes, "Seedlings planted")
        self.assertEqual(saved_plot.planting_date, date.today().isoformat())
        self.assertTrue(saved_plot.calendar)

    def test_advice_flow_displays_forecast_alerts(self):
        self.mock_geocoding()
        forecast_patcher = patch.object(
            WeatherClient,
            "get_forecast",
            return_value=self.forecast,
        )
        advisor_patcher = patch.object(
            PlantingAdvisor,
            "advise",
            return_value=self.advice,
        )
        forecast_patcher.start()
        advisor_patcher.start()
        self.addCleanup(forecast_patcher.stop)
        self.addCleanup(advisor_patcher.stop)

        app = self.run_app()
        app.text_input(key="location").set_value("Akure")
        app.button(key="get_advice").click().run()

        self.assertFalse(app.exception)
        self.assertEqual(len(app.session_state.result["alerts"]), 2)
        self.assertTrue(any("Heavy rain" in item.value for item in app.error))
        self.assertTrue(any("Heatwave" in item.value for item in app.warning))


if __name__ == "__main__":
    unittest.main()