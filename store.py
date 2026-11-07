"""Owner: Storage/models. Basic JSON save/load works; add CSV export, versioning, rebuilding objects."""
import json
from exceptions import StorageError


class FarmLogStore:
    def __init__(self, path="farm_data.json"):
        self.path = path

    def save(self, plots):
        """plots: list[FarmPlot]"""
        try:
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump({"version": 1, "plots": [p.to_dict() for p in plots]}, fh, indent=2)
        except OSError as e:
            raise StorageError(f"Could not save: {e}")

    def load_raw(self):
        """Returns list of plot dicts."""
    #TODO: rebuild FarmPlot objects

        try:
            with open(self.path, encoding="utf-8") as fh:
                return json.load(fh)["plots"]
        except FileNotFoundError:
            return []
        except (json.JSONDecodeError, KeyError) as e:
            raise StorageError(f"Corrupt data file: {e}")

    def export_activities_csv(self, plots, csv_path):
        raise NotImplementedError  # TODO