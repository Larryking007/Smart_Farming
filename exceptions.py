"""
Application-specific exceptions for Smart Farming.

All expected application errors inherit from FarmAdvisorError, allowing
advisor.py to catch known failures and safely fall back to rule-based advice.
"""


class FarmAdvisorError(Exception):
    """Base class for expected Smart Farming application errors."""


class InvalidInputError(FarmAdvisorError):
    """Raised when required input is missing or invalid."""


class InvalidLocationError(FarmAdvisorError):
    """Raised when a location cannot be found or used."""


class UnsupportedCropError(FarmAdvisorError):
    """Raised when the requested crop is not supported."""


class ForecastUnavailableError(FarmAdvisorError):
    """Raised when weather forecast data is unavailable or incomplete."""


class APIRequestError(FarmAdvisorError):
    """Raised when an external API request fails."""


class StorageError(FarmAdvisorError):
    """Raised when reading or writing application data fails."""


class AdviceFormatError(FarmAdvisorError):
    """Raised when AI-generated advice is missing or incorrectly formatted."""
