"""Companies House API client with correct rate-limit handling."""
from ._version import __version__
from .companies_house import CompaniesHouse, normalise_number
from .errors import APIError, AuthError, NotFound, RateLimited, TrialUnverified
from .registrum import Registrum

__all__ = [
    "APIError",
    "AuthError",
    "CompaniesHouse",
    "NotFound",
    "RateLimited",
    "Registrum",
    "TrialUnverified",
    "__version__",
    "normalise_number",
]
