"""Centralized legal and domain constants for ClaimReady.

Single source of truth for NYC Small Claims Court parameters.
"""

from __future__ import annotations

NYC_SMALL_CLAIMS_CAP: float = 10_000.00
SOL_BREACH_OF_CONTRACT_YEARS: int = 6
STATUTORY_INTEREST_RATE: float = 0.09

NYC_BOROUGHS: set[str] = {
    "Manhattan",
    "Bronx",
    "Brooklyn",
    "Queens",
    "Staten Island",
}

BOROUGH_COURT_ADDRESS: dict[str, str] = {
    "Manhattan": "111 Centre Street, New York, NY 10013",
    "Bronx": "851 Grand Concourse, Bronx, NY 10451",
    "Brooklyn": "141 Livingston Street, Brooklyn, NY 11201",
    "Queens": "89-17 Sutphin Boulevard, Jamaica, NY 11435",
    "Staten Island": "927 Castleton Avenue, Staten Island, NY 10310",
}
