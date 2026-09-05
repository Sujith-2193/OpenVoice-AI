# Production hardening

This branch upgrades the original OpenVoice AI demo architecture without removing its realtime voice pipeline or LangGraph handoffs.

## Business data

The three specialist agents now use `backend/src/data/store.py` instead of hard-coded catalog, order, and policy responses.

MongoDB stores:

- products and searchable catalog fields
- orders and delivery status
- store policies

A fresh development database is seeded only when its collections are empty. Existing records are never overwritten by startup seeding.

## Local stack

`docker-compose.yml` provides MongoDB with a persistent Docker volume and starts OpenVoice only after MongoDB passes its health check.

Set `OPENAI_API_KEY` and `ASR_MODEL_PATH` in the shell or an environment file before starting the stack.

## Smoke test

With MongoDB reachable:

```bash
cd backend
uv run python scripts/check_business_data.py
```

The check verifies product search, latest-order lookup, and policy lookup.

## Runtime consistency

The repository and CUDA Docker image now target Python 3.11 consistently. The agent model/provider are configurable through `OPENVOICE_AGENT_MODEL` and `OPENVOICE_AGENT_PROVIDER` instead of being hard-coded in every specialist module.

## Attribution

These changes are an extension of the existing OpenVoice AI project. They do not claim original ownership of the pre-existing voice, WebRTC, ASR, VAD, TTS, or LangGraph implementation.
