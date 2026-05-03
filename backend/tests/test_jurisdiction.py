"""Tests for jurisdiction validation and damages computation."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from tools.jurisdiction import (
    _compute_damages_impl,
    _validate_jurisdiction_impl,
    DamagesResult,
    JurisdictionResult,
)


class TestValidateJurisdiction:
    def test_valid_claim_passes_all_checks(self):
        result = _validate_jurisdiction_impl(
            amount_owed=5000.0,
            breach_date_iso=date.today().isoformat(),
            borough="Manhattan",
            defendant_in_nyc=True,
        )
        assert result.in_monetary_limit is True
        assert result.within_statute_of_limitations is True
        assert result.venue_proper is True
        assert result.issues == []

    def test_amount_at_exact_cap_passes(self):
        result = _validate_jurisdiction_impl(
            amount_owed=10_000.00,
            breach_date_iso=date.today().isoformat(),
            borough="Brooklyn",
            defendant_in_nyc=True,
        )
        assert result.in_monetary_limit is True

    def test_amount_over_cap_fails(self):
        result = _validate_jurisdiction_impl(
            amount_owed=10_000.01,
            breach_date_iso=date.today().isoformat(),
            borough="Queens",
            defendant_in_nyc=True,
        )
        assert result.in_monetary_limit is False
        assert any("exceeds" in i for i in result.issues)

    def test_breach_within_sol_passes(self):
        recent = (date.today() - timedelta(days=365)).isoformat()
        result = _validate_jurisdiction_impl(1000.0, recent, "Bronx", True)
        assert result.within_statute_of_limitations is True

    def test_breach_beyond_sol_fails(self):
        old = (date.today() - timedelta(days=6 * 365 + 1)).isoformat()
        result = _validate_jurisdiction_impl(1000.0, old, "Bronx", True)
        assert result.within_statute_of_limitations is False
        assert any("statute of limitations" in i for i in result.issues)

    def test_invalid_date_fails_sol(self):
        result = _validate_jurisdiction_impl(1000.0, "not-a-date", "Manhattan", True)
        assert result.within_statute_of_limitations is False
        assert any("Could not parse" in i for i in result.issues)

    def test_invalid_borough_fails_venue(self):
        result = _validate_jurisdiction_impl(
            1000.0, date.today().isoformat(), "Hoboken", True
        )
        assert result.venue_proper is False
        assert any("not a NYC borough" in i for i in result.issues)

    def test_defendant_not_in_nyc_fails_venue(self):
        result = _validate_jurisdiction_impl(
            1000.0, date.today().isoformat(), "Manhattan", False
        )
        assert result.venue_proper is False
        assert any("NYC address" in i for i in result.issues)

    def test_all_boroughs_accepted(self):
        for borough in ["Manhattan", "Bronx", "Brooklyn", "Queens", "Staten Island"]:
            result = _validate_jurisdiction_impl(
                1000.0, date.today().isoformat(), borough, True
            )
            assert result.venue_proper is True

    def test_citations_always_present(self):
        result = _validate_jurisdiction_impl(
            1000.0, date.today().isoformat(), "Manhattan", True
        )
        assert len(result.citations) == 3
        assert any("§ 1805" in c for c in result.citations)
        assert any("§ 213" in c for c in result.citations)
        assert any("§ 1801" in c for c in result.citations)

    def test_multiple_issues_accumulated(self):
        old = (date.today() - timedelta(days=6 * 365 + 1)).isoformat()
        result = _validate_jurisdiction_impl(15_000.0, old, "Hoboken", False)
        assert result.in_monetary_limit is False
        assert result.within_statute_of_limitations is False
        assert result.venue_proper is False
        assert len(result.issues) >= 3


class TestComputeDamages:
    def test_zero_days_no_interest(self):
        result = _compute_damages_impl(5000.0, date.today().isoformat())
        assert result.principal == 5000.0
        assert result.interest_accrued == 0.0
        assert result.total_demanded == 5000.0
        assert result.days_elapsed == 0

    def test_one_year_of_interest(self):
        one_year_ago = (date.today() - timedelta(days=365)).isoformat()
        result = _compute_damages_impl(10_000.0, one_year_ago)
        assert result.days_elapsed == 365
        expected_interest = round(10_000.0 * 0.09 / 365.0 * 365, 2)
        assert result.interest_accrued == expected_interest
        assert result.total_demanded == round(10_000.0 + expected_interest, 2)

    def test_future_date_yields_zero_interest(self):
        future = (date.today() + timedelta(days=30)).isoformat()
        result = _compute_damages_impl(1000.0, future)
        assert result.days_elapsed == 0
        assert result.interest_accrued == 0.0

    def test_invalid_date_uses_today(self):
        result = _compute_damages_impl(1000.0, "bad-date")
        assert result.days_elapsed == 0
        assert result.interest_accrued == 0.0

    def test_daily_interest_calculation(self):
        result = _compute_damages_impl(
            3650.0, (date.today() - timedelta(days=1)).isoformat()
        )
        expected_daily = round(3650.0 * 0.09 / 365.0, 4)
        assert result.daily_interest == expected_daily
        assert result.days_elapsed == 1

    def test_zero_principal(self):
        result = _compute_damages_impl(
            0.0, (date.today() - timedelta(days=100)).isoformat()
        )
        assert result.principal == 0.0
        assert result.interest_accrued == 0.0
        assert result.total_demanded == 0.0
