"""Structured output schema for the small claims complaint generator.

CLASS CONCEPT — Structured Outputs.
Every agent that emits facts produces a `CaseFacts` (or partial). The
Planner merges partials before the Drafter renders the PDF packet.
"""

from __future__ import annotations

from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class Party(BaseModel):
    name: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    phone: str = ""
    email: str = ""


class Defendant(Party):
    dos_entity_name: str = ""
    dos_id: str = ""
    service_address: str = ""
    registered_agent: str = ""
    entity_status: str = ""


class Contract(BaseModel):
    date_formed: Optional[date] = None
    scope_of_work: str = ""
    agreed_amount: float = 0.0
    payment_terms: str = ""
    evidence_ids: List[str] = Field(default_factory=list)


class Performance(BaseModel):
    delivered_on: Optional[date] = None
    deliverables: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)


class Breach(BaseModel):
    date: Optional[date] = None
    nature: str = "non-payment"
    amount_owed: float = 0.0
    evidence_ids: List[str] = Field(default_factory=list)


class Damages(BaseModel):
    principal: float = 0.0
    interest_from: Optional[date] = None
    interest_rate: float = 0.09
    total_demanded: float = 0.0


class Venue(BaseModel):
    borough: Literal[
        "Manhattan", "Bronx", "Brooklyn", "Queens", "Staten Island", ""
    ] = ""
    basis: str = ""


class Exhibit(BaseModel):
    label: str
    description: str
    file_ref: str


class JurisdictionCheck(BaseModel):
    in_monetary_limit: bool = False
    within_statute_of_limitations: bool = False
    venue_proper: bool = False
    issues: List[str] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)


class CaseFacts(BaseModel):
    plaintiff: Party = Field(default_factory=Party)
    defendant: Defendant = Field(default_factory=Defendant)
    contract: Contract = Field(default_factory=Contract)
    performance: Performance = Field(default_factory=Performance)
    breach: Breach = Field(default_factory=Breach)
    damages: Damages = Field(default_factory=Damages)
    venue: Venue = Field(default_factory=Venue)
    exhibits: List[Exhibit] = Field(default_factory=list)
    jurisdiction_check: JurisdictionCheck = Field(default_factory=JurisdictionCheck)
    notes: List[str] = Field(default_factory=list)

    def missing_required(self) -> List[str]:
        missing = []
        if not self.plaintiff.name: missing.append("plaintiff.name")
        if not self.plaintiff.address: missing.append("plaintiff.address")
        if not self.defendant.name: missing.append("defendant.name")
        if not self.defendant.service_address: missing.append("defendant.service_address")
        if self.damages.principal <= 0: missing.append("damages.principal")
        if not self.contract.scope_of_work: missing.append("contract.scope_of_work")
        if not self.breach.date: missing.append("breach.date")
        if not self.venue.borough: missing.append("venue.borough")
        return missing
