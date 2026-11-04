"""Crop lookup. Owner: Storage/models. Replace DEFAULT_CROPS with crops.json loading."""
from models import Crop
from exceptions import UnsupportedCropError

DEFAULT_CROPS = {
    "maize":   Crop("maize", 15, 35, 25, 110, [14, 35], ["fall armyworm", "stem borer"]),
    "cassava": Crop("cassava", 18, 35, 20, 300, [30, 60, 90], ["mealybug", "mosaic disease"]),
    "tomato":  Crop("tomato", 15, 32, 30, 90, [14, 28, 42], ["late blight", "fruit borer"]),
    "rice":    Crop("rice", 20, 35, 50, 120, [20, 40], ["blast", "stem borer"]),
}


def get_crop(name):
    key = name.strip().lower()
    if key not in DEFAULT_CROPS:
        raise UnsupportedCropError(f"Unsupported crop: {name!r}. Try: {', '.join(DEFAULT_CROPS)}")
    return DEFAULT_CROPS[key]
