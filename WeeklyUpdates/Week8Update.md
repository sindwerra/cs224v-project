# Week 8 Update

## Summary
- Delivered a minimal working HF-Agent prototype on the OpenAI Agents SDK with a strictly-typed function tool for KB-based red‑flag screening.
- Added MongoDB persistence interfaces (no-op fallback) and updated the architecture doc to reflect Agents SDK + MongoDB.
- Prepared interactive demos for single-turn and multi-turn conversations; laid the groundwork to map the five CS224V scenarios into reproducible runs.

## What we built this week
- Agents SDK integration:
  - `HF-Intake-Agent` with `risk_evaluator_tool` (Pydantic models, strict JSON schema) for red‑flag checks (SBP<80, SBP<90+symptoms, K+≥6.0, eGFR<20, HR<50, Cr↑>30%).
  - Single-turn demo: `scripts/run_agents_sdk_agents_demo.py`.
  - Interactive session demo: `scripts/run_agents_sdk_conv.py` (SQLite-backed session).
- KB-driven safety logic:
  - `agent_sdk/red_flags.py` implements rule-first risk evaluation based on our HF protocol.
- Persistence (placeholders wired in):
  - `agent_sdk/mongo_store.py`: `save_episode(payload)` and `append_message(episode_id, message)` with indexes and ENV-based config; no-op if Mongo is unavailable.
  - `agent_sdk/hf_agents_sdk.py` now prefers Mongo functions, with graceful fallback.
- Architecture:
  - `docs/hf_agent_architecture.md` revised for Agents SDK + MongoDB; includes collections, indexing, and versioning (`based_on_state_version`).

## Gaps vs. the 5 scenario tests
- Context at start: need to load an existing patient/episode before dialog; persist latest `patient_state` between turns.
- Multi-turn slot filling: current prototype supports it via session; we will add guardrails or enforced slot policy so red‑flag evaluation only runs once required fields are present.
- Physician flow: for now, we will implement a synchronous rule-based physician “plan generator” (up‑titrate/maintain/down‑titrate/hold/stop + monitoring/follow-up) before moving to async.
- Scenario runners: convert each scenario into a scripted input sequence with expected terminal outcomes (safety first, short conversations).

## Plan for next week
- Wire Mongo writes in the demos (append messages every turn; upsert episode snapshot after risk evaluation).
- Implement a minimal rule-based Physician planner and persist to a `recommendations` collection (linked to `episode_id`, `based_on_state_version`).
- Add guardrail-based slot enforcement for the multi-turn intake path and finalize a streaming session demo.
- Build reproducible scripts for the 5 scenarios and verify expected outcomes end-to-end.

## Risks / Blockers
- Coordination with the other team on ownership of the physician input surface and data model boundaries.
- Clinical alignment on a few edge thresholds/priority rules; need mentor/clinician confirmation.


