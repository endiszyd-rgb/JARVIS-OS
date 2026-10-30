# AutoLogika JARVIS Read-only for OpenClaw

Experimental plugin pinned to OpenClaw `2026.10.7` / commit `157d8c2bc3ea2fa183afdc11088e69690bf8e64e`.

It exposes exactly two optional tools:

- `jarvis_workshop_orders` — bounded read from the verified offline AutoLogika snapshot;
- `jarvis_home_entity_state` — one allowlisted Home Assistant entity through JARVIS.

Both require narrow, independently revocable JARVIS service tokens. The bridge accepts only a loopback HTTP base URL and has no write, shell, host filesystem, Docker socket, messaging or device-control capability. Secrets are read from environment variables at execution time and are never returned.

See [`docs/OPENCLAW-INTEGRATION.md`](../../../docs/OPENCLAW-INTEGRATION.md) for setup and test instructions.
