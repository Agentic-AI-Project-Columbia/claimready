"""Multi-agent runtime — Planner with specialist handoffs.

CLASS CONCEPT — Agent Framework (multi-agent orchestration).
Built on the OpenAI Agents SDK using Vertex AI Gemini as the underlying
LLM (via LiteLLM). The Planner agent decides which specialist to hand
off to next; specialists each own a focused sub-task and return updated
CaseFacts.

Architecture (mirrors the airbnb-data-analyst-agent reference repo):

    Planner  ─handoff→  Extractor      (multimodal evidence → partial CaseFacts)
             ─handoff→  Defendant      (NY DOS lookup → service of process)
             ─handoff→  Jurisdiction   (RAG + validator → cap/SOL/venue check)
             ─handoff→  Drafter        (renders the PDF packet)

All four specialists also have direct tool access for their domain.
"""

from __future__ import annotations

import os
from typing import Optional

from agents import Agent
from agents.extensions.models.litellm_model import LitellmModel

from schema import CaseFacts
from tools.dos_lookup import lookup_ny_business
from tools.jurisdiction import compute_damages, validate_jurisdiction
from tools.rag import search_legal_kb


def _model() -> LitellmModel:
    """Build the LiteLLM-wrapped Vertex AI Gemini model.

    Auth flows through Application Default Credentials:
      - Locally: `gcloud auth application-default login`
      - On Cloud Run: the service's runtime service account
    """
    model_id = os.getenv("AGENT_MODEL", "vertex_ai/gemini-2.5-flash")
    project = os.getenv("GCP_PROJECT_ID", "agentic-ai-487000")
    location = os.getenv("GCP_REGION", "us-east1")
    # LiteLLM picks these up automatically:
    os.environ.setdefault("VERTEXAI_PROJECT", project)
    os.environ.setdefault("VERTEXAI_LOCATION", location)
    return LitellmModel(model=model_id)


def build_extractor() -> Agent:
    return Agent(
        name="Extractor",
        instructions=(
            "You read a single piece of evidence (contract, email thread, invoice, screenshot, "
            "or freeform note) and extract structured facts about a breach-of-contract claim. "
            "Output a CaseFacts populated only with fields you can support directly from the "
            "evidence. Never invent. Cite which artifact supplied each field via "
            "evidence_ids (use the artifact's filename or short id provided in the prompt). "
            "If a field is not present, leave it empty/zero."
        ),
        model=_model(),
        output_type=CaseFacts,
    )


def build_defendant_agent() -> Agent:
    return Agent(
        name="DefendantResolver",
        instructions=(
            "You resolve a defendant business name into its NY Department of State record. "
            "Call lookup_ny_business with the candidate name. If multiple matches return, "
            "pick the one whose registered jurisdiction is NY and whose entity_type is LLC "
            "or CORP and whose name most closely matches. Populate the defendant fields of "
            "CaseFacts: name, dos_entity_name (canonical), dos_id, service_address, "
            "registered_agent. If no match, leave dos_id empty and add a note explaining "
            "the user must verify the legal name."
        ),
        model=_model(),
        tools=[lookup_ny_business],
        output_type=CaseFacts,
    )


def build_jurisdiction_agent() -> Agent:
    return Agent(
        name="JurisdictionChecker",
        instructions=(
            "You verify the case is properly venued in the NYC Civil Court Small Claims Part. "
            "Steps: (1) call validate_jurisdiction with amount_owed, breach_date_iso, borough, "
            "and defendant_in_nyc=true if the defendant has a NYC service address; otherwise false. "
            "(2) call compute_damages with principal and breach_date_iso to compute statutory "
            "interest. (3) call search_legal_kb to retrieve at least one citation each for the "
            "monetary cap, SOL, and venue. (4) Populate jurisdiction_check and damages on the "
            "returned CaseFacts. Include human-readable issues and citations."
        ),
        model=_model(),
        tools=[validate_jurisdiction, compute_damages, search_legal_kb],
        output_type=CaseFacts,
    )


def build_drafter_agent() -> Agent:
    return Agent(
        name="Drafter",
        instructions=(
            "You produce a final, court-ready CaseFacts. Do NOT call any tools. Inspect the "
            "incoming CaseFacts; for each empty required field "
            "(plaintiff.name, plaintiff.address, defendant.name, defendant.service_address, "
            "damages.principal, contract.scope_of_work, breach.date, venue.borough), "
            "add a clear note in CaseFacts.notes telling the user what is still missing. "
            "Otherwise return CaseFacts unchanged. The PDF will be rendered by the backend, "
            "not by you."
        ),
        model=_model(),
        output_type=CaseFacts,
    )


def build_planner() -> Agent:
    extractor = build_extractor()
    defendant = build_defendant_agent()
    jurisdiction = build_jurisdiction_agent()
    drafter = build_drafter_agent()

    planner = Agent(
        name="Planner",
        instructions=(
            "You orchestrate the production of a NYC small-claims breach-of-contract complaint. "
            "You receive: (a) the user's intake answers as a partial CaseFacts JSON, "
            "(b) one or more uploaded evidence artifacts. "
            "Your job is to coordinate handoffs in this order:\n"
            "  1. Hand off to Extractor for each artifact to enrich the CaseFacts (merge the "
            "     returned partial CaseFacts into the running CaseFacts).\n"
            "  2. If defendant.dos_id is empty and defendant.name is set, hand off to "
            "     DefendantResolver to fill the service-of-process address.\n"
            "  3. Hand off to JurisdictionChecker to validate cap/SOL/venue and compute damages.\n"
            "  4. Hand off to Drafter to finalize and surface any missing required fields.\n"
            "Return the final CaseFacts. Do not invent facts. If a step fails, retry once, "
            "then surface the failure in CaseFacts.notes."
        ),
        model=_model(),
        handoffs=[extractor, defendant, jurisdiction, drafter],
        output_type=CaseFacts,
    )
    return planner


_planner_singleton: Optional[Agent] = None


def get_planner() -> Agent:
    global _planner_singleton
    if _planner_singleton is None:
        _planner_singleton = build_planner()
    return _planner_singleton
