"""FarmLogStore. Owner: Storage/models.

JSON  : the full app state (save / load / load_raw).
CSV   : read-only exports for spreadsheets, three files: plots, activities, calendar.
        Files are written as UTF-8 with a BOM so Excel shows accented names correctly.
        Free-text cells that start with = + - @ are prefixed with ' so spreadsheet apps
        never treat them as formulas (CSV injection).
"""
import csv
import json
import os

from exceptions import StorageError
from models import FarmPlot

PLOT_COLUMNS = ["plot_id", "plot_name", "crop", "location", "latitude", "longitude",
                "planting_date", "activity_count"]
ACTIVITY_COLUMNS = ["plot_id", "plot_name", "crop", "date", "activity_type", "notes"]
CALENDAR_COLUMNS = ["plot_id", "plot_name", "crop", "date", "event", "stage"]

_FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def _safe(value):
    """Neutralise spreadsheet formulas in free-text cells."""
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(_FORMULA_STARTS) else text


class FarmLogStore:
    def __init__(self, path="farm_data.json"):
        self.path = path

    # ------------------------------------------------------------ JSON
    def save(self, plots):
        """plots: list[FarmPlot]"""
        try:
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump({"version": 1, "plots": [p.to_dict() for p in plots]}, fh, indent=2)
        except OSError as e:
            raise StorageError(f"Could not save: {e}")

    def load_raw(self):
        """Returns list of plot dicts."""
        try:
            with open(self.path, encoding="utf-8") as fh:
                return json.load(fh)["plots"]
        except FileNotFoundError:
            return []
        except (json.JSONDecodeError, KeyError) as e:
            raise StorageError(f"Corrupt data file: {e}")

    def load(self):
        """Returns list[FarmPlot]."""
        try:
            return [FarmPlot.from_dict(d) for d in self.load_raw()]
        except (KeyError, TypeError) as e:
            raise StorageError(f"Corrupt data file: {e}")

    # ------------------------------------------------------------ CSV
    def export_plots_csv(self, plots, csv_path):
        rows = [[p.plot_id, _safe(p.name), p.crop_name, _safe(p.location.name),
                 p.location.lat, p.location.lon, p.planting_date or "", len(p.activities)]
                for p in plots]
        self._write_csv(csv_path, PLOT_COLUMNS, rows)

    def export_activities_csv(self, plots, csv_path):
        rows = [[p.plot_id, _safe(p.name), p.crop_name, a.date, a.kind, _safe(a.notes)]
                for p in plots for a in sorted(p.activities, key=lambda a: a.date)]
        self._write_csv(csv_path, ACTIVITY_COLUMNS, rows)

    def export_calendar_csv(self, plots, csv_path):
        rows = [[p.plot_id, _safe(p.name), p.crop_name, e.date, _safe(e.title), e.kind]
                for p in plots for e in sorted(p.calendar, key=lambda e: e.date)]
        self._write_csv(csv_path, CALENDAR_COLUMNS, rows)

    def export_all_csv(self, plots, folder):
        """Writes plots.csv, activities.csv and calendar.csv into `folder`. Returns the paths."""
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as e:
            raise StorageError(f"Could not create {folder}: {e}")
        paths = [os.path.join(folder, n) for n in ("plots.csv", "activities.csv", "calendar.csv")]
        self.export_plots_csv(plots, paths[0])
        self.export_activities_csv(plots, paths[1])
        self.export_calendar_csv(plots, paths[2])
        return paths

    @staticmethod
    def _write_csv(path, header, rows):
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                writer = csv.writer(fh)
                writer.writerow(header)
                writer.writerows(rows)
        except OSError as e:
            raise StorageError(f"Could not write {path}: {e}")
