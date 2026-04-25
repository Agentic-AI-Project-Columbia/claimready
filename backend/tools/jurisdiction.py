"""Jurisdiction validation + statutory damages computation.

Pure functions exposed as agent tools. Cites NYC CCA § 1805 (monetary cap),
CPLR § 213(2) (6-year SOL for breach of contract), CPLR § 5004 (9% interest).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import List

from agents import function_tool
from pydantic import BaseModel

NYC_SMALL_CLAIMS_CAP = 10_000.00
SOL_BREACH_OF_CONTRACT_YEARS = 6
STATUTORY_INTEREST_RATE = 0.09
NYC_BOROUGHS = {"Manhattan", "Bronx", "Brooklyn", "Queens", "Staten Island"}


class JurisdictionResult(BaseModel):
    in_monetary_limit: bool
    within_statute_of_limitations: bool
    venue_proper: bool
    issues: List[str]
    citations: List[str]


class DamagesResult(BaseModel):
    principal: float
    interest_accrued: float
    total_demanded: float
    daily_interest: float
    days_elapsed: int


@function_tool
def validate_jurisdiction(
    amount_owed: float,
    breach_date_iso: str,
    borough: str,
    defendant_in_nyc: bool,
) -> JurisdictionResult:
    """Validate NYC small-claims jurisdiction for a candidate filing.

    Args:
        amount_owed: Principal claim in USD.
        breach_date_iso: Date of breach as ISO string (YYYY-MM-DD).
        borough: One of Manhattan / Bronx / Brooklyn / Queens / Staten Island.
        defendant_in_nyc: Whether the defendant has a NYC address or does business in NYC.
    """
    issues: List[str] = []
    citations: List[str] = []

    in_cap = amount_owed <= NYC_SMALL_CLAIMS_CAP
    if not in_cap:
        issues.append(
            f"Claim of ${amount_owed:,.2f} exceeds the $10,000 NYC small-claims cap. "
            "Must be filed in Civil Court (not Small Claims Part) or split — but splitting is forbidden."
        )
    citations.append("NYC Civil Court Act § 1805 (monetary jurisdiction)")

    try:
        bdate = date.fromisoformat(breach_date_iso)
        cutoff = date.today() - timedelta(days=SOL_BREACH_OF_CONTRACT_YEARS * 365)
        in_sol = bdate >= cutoff
    except ValueError:
        in_sol = False
        issues.append(f"Could not parse breach date: {breach_date_iso!r}")
    if not in_sol:
        issues.append(
            "Breach is older than the 6-year statute of limitations for contract claims."
        )
    citations.append("CPLR § 213(2) (6-year SOL for contract)")

    venue_ok = borough in NYC_BOROUGHS and defendant_in_nyc
    if borough not in NYC_BOROUGHS:
        issues.append(f"Borough {borough!r} is not a NYC borough.")
    if not defendant_in_nyc:
        issues.append("Defendant must have a NYC address or do business in NYC for venue.")
    citations.append("NYC Civil Court Act § 1801 (venue)")

    return JurisdictionResult(
        in_monetary_limit=in_cap,
        within_statute_of_limitations=in_sol,
        venue_proper=venue_ok,
        issues=issues,
        citations=citations,
    )


@function_tool
def compute_damages(principal: float, breach_date_iso: str) -> DamagesResult:
    """Compute principal + statutory 9% pre-judgment interest from breach date.

    Args:
        principal: Amount owed at the time of breach.
        breach_date_iso: ISO date (YYYY-MM-DD) when payment first became overdue.
    """
    try:
        bdate = date.fromisoformat(breach_date_iso)
    except ValueError:
        bdate = date.today()
    days = max((date.today() - bdate).days, 0)
    daily = principal * STATUTORY_INTEREST_RATE / 365.0
    interest = daily * days
    return DamagesResult(
        principal=round(principal, 2),
        interest_accrued=round(interest, 2),
        total_demanded=round(principal + interest, 2),
        daily_interest=round(daily, 4),
        days_elapsed=days,
    )
