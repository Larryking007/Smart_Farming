"""Shared custom exceptions. Owner: AI/advisor lead. Everyone raises/catches these."""


class FarmAdvisorError(Exception):
    """Base class for all app errors. The UI catches this and shows a message."""


class InvalidInputError(FarmAdvisorError):
    """Bad user input (date, coordinates, plot name...)."""


class InvalidLocationError(FarmAdvisorError):
    """Location could not be parsed or geocoded."""


class UnsupportedCropError(FarmAdvisorError):
    """Crop is not in crops.json."""


class ForecastUnavailableError(FarmAdvisorError):
    """Forecast data is missing or incomplete."""


class APIRequestError(FarmAdvisorError):
    """Network failure, timeout, or non-200 response (Open-Meteo or Gemini)."""


class StorageError(FarmAdvisorError):
    """Save/load problem (missing, corrupt, or unwritable file)."""

class ValidationError(FarmAdvisorError):
    """Data validation failed (e.g., invalid date format, out-of-range values)."""

class APIRequestError(FarmAdvisorError):
    """Network failure, timeout, or non-200 response (Open-Meteo or Gemini)."""

class ForecastUnavailableError(FarmAdvisorError):
    """Forecast data is missing or incomplete."""
