"""Typed WebSocket event protocol for the agent pipeline.

Each event is a Pydantic model with a Literal `type` field. Together they
form a discriminated union that documents the wire format used between
backend (`_forward_event` in main.py) and the frontend AgentTimeline.

These models are not enforced at the WebSocket boundary today (events
are emitted as raw dicts for compatibility with the existing frontend),
but they serve as the source of truth for the protocol shape.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel


class AgentStartedEvent(BaseModel):
    type: Literal["agent_started"] = "agent_started"
    name: str


class ToolCalledEvent(BaseModel):
    type: Literal["tool_called"] = "tool_called"
    tool_name: str
    agent: Optional[str] = None
    args: Optional[Dict[str, Any]] = None


class ToolResultEvent(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool_name: str = ""
    agent: Optional[str] = None
    preview: str = ""
    preview_truncated: bool = False


class HandoffEvent(BaseModel):
    type: Literal["handoff"] = "handoff"
    to_agent: str
    from_agent: Optional[str] = None


class FactsPartialEvent(BaseModel):
    type: Literal["facts_partial"] = "facts_partial"
    facts: Dict[str, Any] = {}


class RetryEvent(BaseModel):
    type: Literal["retry"] = "retry"
    attempt: int
    reason: str


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    facts: Dict[str, Any] = {}
    pdf_ready: bool = False


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str


AgentEvent = Union[
    AgentStartedEvent,
    ToolCalledEvent,
    ToolResultEvent,
    HandoffEvent,
    FactsPartialEvent,
    RetryEvent,
    DoneEvent,
    ErrorEvent,
]
