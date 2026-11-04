"""Regex helpers. Owner: Storage/models. Fully working; extend and add tests."""
import re
from datetime import datetime
from exceptions import InvalidInputError

COORD_RE = re.compile(r"^\s*(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*$")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .,'-]{1,59}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
NUMBER_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*(mm|°C|C)\b")


def parse_coordinates(text):
    """'7.25, 5.19' -> (7.25, 5.19). Raises InvalidInputError."""
    m = COORD_RE.match(text)
    if not m:
        raise InvalidInputError(f"Invalid coordinates: {text!r}")
    lat, lon = float(m.group(1)), float(m.group(2))
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise InvalidInputError("Coordinates out of range")
    return lat, lon


def validate_location_name(text):
    if not NAME_RE.match(text.strip()):
        raise InvalidInputError(f"Invalid location name: {text!r}")
    return text.strip()


def validate_date(text):
    """Returns the date string if it is a real YYYY-MM-DD date."""
    if not DATE_RE.match(text.strip()):
        raise InvalidInputError("Date must look like YYYY-MM-DD")
    try:
        datetime.strptime(text.strip(), "%Y-%m-%d")
    except ValueError:
        raise InvalidInputError(f"Not a real date: {text!r}")
    return text.strip()


def extract_numbers(text):
    """'Rain 12.5 mm, high 31 °C' -> [(12.5, 'mm'), (31.0, '°C')]"""
    return [(float(v), u) for v, u in NUMBER_RE.findall(text)]
