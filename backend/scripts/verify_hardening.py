"""Static smoke checks for the production deployment boundary.

This test intentionally avoids importing torch/ASR/LLM dependencies so it can
run in a lightweight CI job.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
server = (ROOT / "backend/src/api/server.py").read_text(encoding="utf-8")
hardened = (ROOT / "backend/src/api/hardened.py").read_text(encoding="utf-8")
entrypoint = (ROOT / "entrypoint.sh").read_text(encoding="utf-8")

assert "allow_origins=[\"*\"]" in server, "Upstream server changed; review CORS layering"
assert "SecurityMiddleware" in hardened
assert "OPENVOICE_API_KEY" in hardened
assert "OPENVOICE_RATE_LIMIT" in hardened
assert "OPENVOICE_MAX_CONNECTIONS" in hardened
assert "OPENVOICE_MAX_HTTP_BODY_BYTES" in hardened
assert "src.api.hardened:app" in entrypoint
print("production hardening static checks: PASS")
