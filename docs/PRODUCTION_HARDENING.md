# Production hardening

This branch upgrades the original OpenVoice AI demo architecture without removing its realtime voice pipeline or LangGraph handoffs.

## Business data

The three specialist agents now use `backend/src/data/store.py` instead of hard-coded catalog, order, and policy responses.

MongoDB stores:

- products and searchable catalog fields
- orders and delivery status
- store policies

A fresh development database is seeded only when its collections are empty. Existing records are never overwritten by startup seeding.

## Security boundary

The container now starts `src.api.hardened:app`, an ASGI wrapper around the original API. It provides:

- API-key authentication via `X-API-Key` or Bearer token when `OPENVOICE_API_KEY` is configured
- WebSocket authentication via the same key in the browser-compatible `api_key` query parameter
- per-client sliding-window rate limiting
- a configurable concurrent WebSocket connection ceiling
- an HTTP request-body size limit
- explicit CORS origins instead of wildcard CORS at the deployment boundary
- graceful SIGINT/SIGTERM handling
- proxy-header support for deployments behind a reverse proxy

For production, set a strong `OPENVOICE_API_KEY` and a real `OPENVOICE_ALLOWED_ORIGINS` value. Leaving the key empty is intended only for local development.

## Local stack

`docker-compose.yml` provides MongoDB with a persistent Docker volume and starts OpenVoice only after MongoDB passes its health check. MongoDB is not published to the host.

Set `OPENAI_API_KEY` and `ASR_MODEL_PATH` in the shell or an environment file before starting the stack.

## Smoke test

With MongoDB reachable:

```bash
cd backend
uv run python scripts/check_business_data.py
```

The check verifies product search, latest-order lookup, and policy lookup.

The lightweight hardening check can run without GPU/LLM dependencies:

```bash
python backend/scripts/verify_hardening.py
python -m compileall -q backend/src backend/scripts
```

## CI

`.github/workflows/ci.yml` validates Python syntax and the hardening boundary, then installs, builds, and lints the React frontend.

## Runtime consistency

The repository and CUDA Docker image now target Python 3.11 consistently. The agent model/provider are configurable through `OPENVOICE_AGENT_MODEL` and `OPENVOICE_AGENT_PROVIDER` instead of being hard-coded in every specialist module.

## Scope and attribution

This is production hardening for a portfolio/deployment-ready implementation, not a claim that the system is universally production-safe under every threat model or traffic profile. The changes are an extension of the existing OpenVoice AI project and do not claim original ownership of the pre-existing voice, WebRTC, ASR, VAD, TTS, or LangGraph implementation.
