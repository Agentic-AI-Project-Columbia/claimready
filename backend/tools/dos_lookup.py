"""NY Department of State Active Corporations lookup.

CLASS CONCEPT — Tool Use.
Wraps the official NY Open Data SODA endpoint (Active Corporations,
dataset id n9v6-gdp6) so an agent can resolve an LLC name into a
service-of-process address.

No scraping, no API key. Public dataset.
"""

from __future__ import annotations

from typing import List, Optional

import requests
from agents import function_tool
from pydantic import BaseModel

SODA_URL = "https://data.ny.gov/resource/n9v6-gdp6.json"


class BusinessRecord(BaseModel):
    dos_id: str = ""
    current_entity_name: str = ""
    entity_type: str = ""
    county: str = ""
    jurisdiction: str = ""
    dos_process_name: str = ""
    dos_process_address_1: str = ""
    dos_process_city: str = ""
    dos_process_state: str = ""
    dos_process_zip: str = ""
    registered_agent_name: str = ""

    @property
    def service_address(self) -> str:
        parts = [self.dos_process_address_1]
        city_state = " ".join(p for p in [self.dos_process_city, self.dos_process_state] if p)
        if city_state:
            parts.append(city_state)
        if self.dos_process_zip:
            parts[-1] = f"{parts[-1]} {self.dos_process_zip}".strip()
        return ", ".join(p for p in parts if p)


class LookupResult(BaseModel):
    query: str
    matches: List[BusinessRecord]
    error: Optional[str] = None


def _query_soda(name: str, limit: int = 5) -> List[dict]:
    where = f"upper(current_entity_name) like upper('%{name.replace(chr(39), chr(39)*2)}%')"
    params = {"$where": where, "$limit": str(limit)}
    resp = requests.get(SODA_URL, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


@function_tool
def lookup_ny_business(name: str) -> LookupResult:
    """Search the NY Department of State Active Corporations database.

    Returns up to 5 matching business records with service-of-process address.
    Use the canonical entity name from these results when filling the complaint.

    Args:
        name: Business name to search (partial match, case-insensitive).
    """
    try:
        rows = _query_soda(name)
    except Exception as exc:
        return LookupResult(query=name, matches=[], error=str(exc))

    matches = [
        BusinessRecord(
            dos_id=str(r.get("dos_id", "")),
            current_entity_name=r.get("current_entity_name", ""),
            entity_type=r.get("entity_type", ""),
            county=r.get("county", ""),
            jurisdiction=r.get("jurisdiction", ""),
            dos_process_name=r.get("dos_process_name", ""),
            dos_process_address_1=r.get("dos_process_address_1", ""),
            dos_process_city=r.get("dos_process_city", ""),
            dos_process_state=r.get("dos_process_state", ""),
            dos_process_zip=r.get("dos_process_zip", ""),
            registered_agent_name=r.get("registered_agent_name", ""),
        )
        for r in rows
    ]
    return LookupResult(query=name, matches=matches)
