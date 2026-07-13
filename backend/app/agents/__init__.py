"""
Agentic AI layer (Phase 6A-1).

This package wires a LangGraph supervisor workflow on top of the existing
FastAPI services. It is intentionally isolated from the deterministic chat /
detection pipelines:

- YOLO inference stays in ``app.integrations.yolo_engine`` and is only
  triggered through ``app.services.detection_service``.
- The existing ``/api/chat`` endpoints are untouched; the agent layer exposes
  a separate ``/api/agent/chat`` route.
- All third-party imports (``langchain``, ``langgraph``, ``deepagents``) are
  performed lazily inside the modules that need them so that a missing
  dependency cannot prevent the FastAPI app from starting.
"""
