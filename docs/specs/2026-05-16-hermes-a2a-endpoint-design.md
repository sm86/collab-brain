# Hermes A2A Endpoint — Design Spec

**Date:** 2026-05-16
**Status:** Approved for implementation
**Scope:** Server-only A2A sidecar for the existing Hermes Docker container

## Summary

Add a small Python stdlib HTTP sidecar to the existing Hermes Docker container. It exposes a minimal, A2A-compliant REST surface (HTTP+JSON / gRPC-transcoded binding) for hackathon use:

- `GET /healthz` — liveness
- `GET /.well-known/agent-card.json` — A2A AgentCard
- `POST /message:send` — single skill: `company-info`

Each `/message:send` call pre-queries the local GBrain for the user's company query, embeds the result in a hardcoded prompt template, and shells out to `hermes chat -Q -q "<prompt>"`. Hermes' stdout is returned as the assistant message. No tasks, no streaming, no auth, no push notifications.

## Why this skill (company-info, not chat)

This repo is "collab-brain." The demo workflow ([docs/gbrain-acme-demo-workflow.md](../gbrain-acme-demo-workflow.md)) is partners (Garry, Brad, Diana) merging brain context about Acme into one briefing. Exposing Hermes as a *generic chat* over A2A wouldn't move that demo forward; exposing it as a `company-info` skill that returns brain-grounded notes about a company does.

The A2A surface is the protocol by which one partner's agent will eventually ask another partner's agent "what do you know about Acme?" This spec covers the **server side only** (being callable). The multi-instance deployment, brain partitioning, and caller-side tool are explicitly deferred to a follow-up spec.

## Verified prerequisites

Both binaries are present in the running `hermes-agent` container (`gbrain 0.35.1.0`, current Hermes Agent install):

- `hermes chat -Q -q "<prompt>"` exists. `-Q` is "Quiet mode for programmatic use: suppress banner, spinner, and tool previews. Only output the final response and session info." `-q QUERY` is the single-shot non-interactive query.
- `gbrain query "<query>"` exists. Hybrid search (vector + keyword + RRF + multi-query expansion). Supports `--limit N` (default 20), `--detail low|medium|high` (default medium).

## A2A compliance level

**Option B — "A2A-shaped."** Uses A2A's HTTP+JSON binding for endpoints and message format per the canonical proto definition ([`specification/a2a.proto`](https://github.com/a2aproject/A2A/blob/main/specification/a2a.proto)):

- Roles serialize as the proto enum names: `"ROLE_USER"`, `"ROLE_AGENT"` (proto3 JSON convention).
- `Part` is a `oneof` of `text` / `raw` / `url` / `data`. Text parts serialize as `{"text": "..."}` — no `kind` discriminator. v0.1 only emits and accepts the `text` variant.
- `AgentCard` uses `supportedInterfaces` (REQUIRED) — there is no top-level `protocolVersion`; the protocol version lives per-interface.
- Discovery URL is `/.well-known/agent-card.json`.
- Operation paths come from the proto's `google.api.http` annotations — `POST /message:send` (no `/v1/` prefix). Any version prefix lives in the `url` of the `AgentInterface`, not in our route table.

Skips the JSON-RPC error envelope in favor of plain HTTP status + `{"error": "<msg>"}`. Returns direct `Message` responses (the `message` arm of the `SendMessageResponse.payload` oneof) in place of a `Task`, which the spec allows.

Other A2A optional surfaces are deferred: no `tasks/*` endpoints, no `message/stream` (SSE), no push notifications, no auth (`securitySchemes`), no extra entries in `supportedInterfaces` beyond our HTTP+JSON one.

## Architecture

```
┌─────────────────────── hermes container ────────────────────────┐
│                                                                  │
│  entrypoint.sh                                                   │
│    ├─ if A2A_ENABLED=true: start a2a_server.py (background)     │
│    └─ exec HERMES_COMMAND (foreground; or sleep infinity)       │
│                                                                  │
│  /opt/a2a/a2a_server.py  (stdlib only, ~150 lines)               │
│    ├─ ThreadingHTTPServer on ${A2A_BIND}:${A2A_PORT}            │
│    ├─ GET /.well-known/agent-card.json                           │
│    ├─ GET /healthz                                               │
│    └─ POST /message:send                                         │
│           ├─ subprocess: gbrain query <user_query> --detail med │
│           └─ subprocess: hermes chat -Q -q <wrapped prompt>     │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
                                ▲
               host port ${A2A_PORT}:8080
       (reachable from host only if A2A_BIND=0.0.0.0)
```

## Files changed

Source code lives in `src/`, not `setup/docker/`. `setup/` is for build/deploy artifacts (Dockerfile, compose, entrypoint, env templates); the Python sidecar is application code and belongs in `src/`. The Docker build context is already the repo root (`context: ../..` in compose), so this adds zero friction.

| File | Change | Rough size |
|---|---|---|
| `src/a2a_server.py` | **NEW** — single-file stdlib HTTP server | ~150 lines |
| `setup/docker/Dockerfile` | Add `COPY src/a2a_server.py /opt/a2a/a2a_server.py` | +1 line |
| `setup/docker/entrypoint.sh` | Branch on `A2A_ENABLED`, start sidecar in background | +5 lines |
| `setup/docker/docker-compose.yml` | Expose `${A2A_PORT:-8080}:8080`, pass through `A2A_*` env vars | +3 lines |
| `setup/docker/env/hermes.env.example` | Add `A2A_*` vars with comments | +6 lines |
| `README.md` | Short "A2A endpoint" section with curl examples and bind-address warning | +20 lines |

Single flat file (`src/a2a_server.py`), not a package. Promote to `src/a2a/` if a second module ever shows up.

## Endpoint contracts

All endpoints serve and accept `application/json`. No CORS, no auth.

### `GET /healthz`

Liveness check. Does **not** invoke Hermes or GBrain.

```
GET /healthz
→ 200  {"status": "ok"}
```

### `GET /.well-known/agent-card.json`

Static per-process AgentCard, computed once at startup from env vars. Field shape matches the proto (`supportedInterfaces` REQUIRED, no top-level `protocolVersion`, no `stateTransitionHistory`).

```json
{
  "name": "Hermes",
  "description": "Hermes Agent CLI exposed over A2A. Forwards a company-info query to the agent's GBrain and returns brain-grounded notes about the company.",
  "version": "0.1.0",
  "supportedInterfaces": [
    {
      "url": "${A2A_PUBLIC_URL}",
      "protocolBinding": "HTTP+JSON",
      "protocolVersion": "1.0"
    }
  ],
  "capabilities": {
    "streaming": false,
    "pushNotifications": false
  },
  "defaultInputModes": ["text/plain"],
  "defaultOutputModes": ["text/plain"],
  "skills": [
    {
      "id": "company-info",
      "name": "Company info from brain",
      "description": "Given a company name or query, returns what this agent's brain knows about that company — past interactions, key contacts, what they're working on, current status, and open risks — drawn from notes, meetings, and company entries in the agent's GBrain.",
      "tags": ["company-info", "brain", "crm", "notes", "briefing"],
      "examples": [
        "Acme",
        "What do you know about Acme?",
        "Give me a briefing on Stripe based on our past meetings."
      ]
    }
  ]
}
```

- `A2A_PUBLIC_URL` populates `supportedInterfaces[0].url` (defaults to `http://localhost:${A2A_PORT}`). The operation path `/message:send` is relative to this URL.
- `version` is the **sidecar** version (`0.1.0`), separate from the per-interface `protocolVersion` which is the A2A protocol version this interface speaks (`1.0`).
- `capabilities` includes only fields present in the current `AgentCapabilities` proto. Drop `streaming` and `pushNotifications` to `false` since v0.1 implements neither.
- All other fields are hardcoded constants in `a2a_server.py`.

### `POST /message:send`

Body shape matches `SendMessageRequest` from the proto (`message` REQUIRED, `configuration`/`metadata` optional and ignored by v0.1).

**Request body**

```json
{
  "message": {
    "messageId": "<client uuid; optional in v0.1, see note>",
    "role": "ROLE_USER",
    "parts": [
      {"text": "Acme"}
    ]
  }
}
```

- **`role`**: proto enum name. Accept only `"ROLE_USER"` on the request.
- **`parts`**: each part is the `Part` oneof — exactly one of `text`, `raw`, `url`, `data`. v0.1 only emits and accepts the `text` variant; any other variant is a `400`.
- **`messageId`**: proto says REQUIRED. We accept it missing as a v0.1 leniency and generate one server-side to keep `curl` ergonomics low for the demo. Explicitly flagged as a deviation; real A2A clients always send one.

**Server behavior**

1. Parse body as JSON. On parse failure → `400`.
2. Validate: `message.role == "ROLE_USER"`, `message.parts` is a non-empty array, and every part is an object with exactly one content key which must be `"text"` mapping to a string. Any other shape → `400`.
3. Concatenate all text parts' `text` with `"\n"` → `user_query`.
4. **Pre-query brain**: `subprocess.run(["gbrain", "query", user_query, "--limit", "20", "--detail", "medium"], capture_output=True, text=True, timeout=A2A_GBRAIN_TIMEOUT)` → `brain_notes`. If exit != 0 or stdout empty, set `brain_notes = "(no brain results)"` and continue — do **not** fail the request.
5. **Build prompt** from `PROMPT_TEMPLATE` (below).
6. **Call Hermes**: `subprocess.run(["hermes", "chat", "-Q", "-q", prompt], capture_output=True, text=True, timeout=A2A_HERMES_TIMEOUT)`.
7. `stdout.strip()`. If empty → `502`. Otherwise wrap as the agent message in the response.

**Hardcoded prompt template in `a2a_server.py`**

```python
PROMPT_TEMPLATE = """\
You are a YC partner. A peer agent is asking what YOU know about a company
so they can prepare for a meeting. Answer ONLY from the notes below — your
personal brain. Do not invent details. If the notes are empty or unrelated,
say plainly that you have no record of this company.

Return a concise briefing covering, as available:
- Past interactions (meetings, emails, threads — with dates if known)
- Key contacts and their roles
- What the company is working on / current state
- Your assessment and any open risks or unanswered questions

=== Brain notes ===
{brain_notes}
=== End brain notes ===

Company query from peer agent:
{user_query}
"""
```

**Response body**

Body shape is the `message` arm of the `SendMessageResponse.payload` oneof (proto3 JSON encodes oneof variants as just the field name, so the response is `{"message": {...}}` — no `payload` wrapper).

```json
{
  "message": {
    "messageId": "<server-generated uuid4>",
    "role": "ROLE_AGENT",
    "parts": [
      {"text": "<briefing>"}
    ]
  }
}
```

## Process behavior

### Startup (`setup/docker/entrypoint.sh`)

```bash
# pseudo-diff
if [ "${A2A_ENABLED:-false}" = "true" ]; then
  python3 /opt/a2a/a2a_server.py &
  echo "a2a sidecar started on ${A2A_BIND:-127.0.0.1}:${A2A_PORT:-8080}"
fi

# existing logic, unchanged:
if [ -n "${HERMES_COMMAND}" ]; then
  exec ${HERMES_COMMAND}
else
  exec sleep infinity
fi
```

Sidecar runs in the background so it does not block the existing foreground process. If `A2A_ENABLED` is unset or not `"true"`, the sidecar is not started — zero behavior change for existing users. No PID file, no health-wait, no auto-restart on crash; failures are observable via `docker logs` and `/healthz` connection-refused.

### Concurrency

`http.server.ThreadingHTTPServer` (one-line difference from `HTTPServer`). Each request runs in its own thread; concurrent A2A calls do not queue head-of-line. No thread pool, no connection cap, no rate limit. Documented limitation: a burst of concurrent calls spawns N concurrent `hermes` subprocesses and will tank the host. Acceptable for hackathon. Fix in v0.2 would be a small `ThreadPoolExecutor`.

### Env vars (`setup/docker/env/hermes.env.example`)

| Var | Default | Purpose |
|---|---|---|
| `A2A_ENABLED` | `false` | Master switch. Sidecar starts only when `true`. |
| `A2A_PORT` | `8080` | Port the sidecar binds inside the container. |
| `A2A_BIND` | `127.0.0.1` | Bind address inside container. Secure default. |
| `A2A_PUBLIC_URL` | `http://localhost:${A2A_PORT}` | Goes into AgentCard `url` field — what external callers should hit. |
| `A2A_HERMES_TIMEOUT` | `90` | Seconds; Hermes subprocess timeout. |
| `A2A_GBRAIN_TIMEOUT` | `15` | Seconds; gbrain subprocess timeout. |

### Docker compose change

```yaml
ports:
  - "${A2A_PORT:-8080}:${A2A_PORT:-8080}"
```

Both host-side and container-side ports come from the same env var, so `A2A_PORT` means "the port" everywhere — no split semantics. The sidecar's `ThreadingHTTPServer` binds to `A2A_PORT` inside the container; compose publishes the same number on the host.

### Security defaults

- **Bind defaults to `127.0.0.1`** (inside container). The compose `ports:` line publishes a host port, but with the sidecar bound to localhost-inside-container, the published port cannot be reached from the host. To call from the host, the user must explicitly set `A2A_BIND=0.0.0.0`. README spells this out with a one-line setup note.
- **No auth.** Hackathon scope. README adds a loud warning: do not publish this endpoint to a network you don't fully control.
- **No TLS.** `A2A_PUBLIC_URL` defaults to `http://`.

## Error handling

Three buckets. ~6 lines of handler code total. Granular detail goes to stderr, not into the JSON response body.

| Condition | Status | Body |
|---|---|---|
| Any request validation failure (parse, missing fields, wrong shape) | `400` | `{"error": "bad request"}` |
| Hermes subprocess timeout, non-zero exit, or empty stdout | `502` | `{"error": "hermes failed"}` |
| Unhandled exception in handler | `500` | `{"error": "internal error"}` |

`gbrain` failure is **not** an HTTP error — it degrades silently to `"(no brain results)"` and the request continues. Logged to stderr.

**Hermes output cleaning** is deferred. We use `stdout.strip()` only. If `hermes chat -Q -q` emits a trailing "Session: <uuid>" line in practice, we add one targeted strip then — not preemptively. The smoke test in the test plan is where we observe real output.

**Logging**: one line per request to stderr — `[a2a] METHOD PATH status=N ms=N`. No structured logging, no log file.

**Explicitly skipped**: retries, request body size limits, CORS preflight, A2A task-lifecycle errors (we never return Tasks).

## Test plan

Three smoke checks. No automated suite; no CI.

### 1. Syntax

```bash
python3 -m py_compile src/a2a_server.py
```

### 2. Build & start

```bash
docker compose -f setup/docker/docker-compose.yml up -d --build
docker compose -f setup/docker/docker-compose.yml logs hermes | grep a2a
# expect: "a2a sidecar started on 127.0.0.1:8080"
```

### 3. End-to-end via `docker exec`

Default bind is `127.0.0.1`, so host curl will not reach the sidecar without `A2A_BIND=0.0.0.0`. Use `docker exec` for the smoke check:

```bash
# 3a — liveness
docker exec hermes-agent curl -s http://localhost:8080/healthz
# expect: {"status": "ok"}

# 3b — agent card
docker exec hermes-agent curl -s http://localhost:8080/.well-known/agent-card.json | head -30
# expect: JSON with name=Hermes, supportedInterfaces[0].protocolBinding=HTTP+JSON, skills[0].id=company-info

# 3c — end-to-end company-info call (requires Acme content in brain)
docker exec hermes-agent curl -s -X POST http://localhost:8080/message:send \
  -H 'Content-Type: application/json' \
  -d '{"message":{"role":"ROLE_USER","parts":[{"text":"Acme"}]}}'
# expect: {"message":{"messageId":"<uuid>","role":"ROLE_AGENT","parts":[{"text":"<briefing>"}]}}
```

**Pre-req for 3c**: brain must contain Acme content. If `setup/mockdata/garry/` has not been imported yet:

```bash
docker exec hermes-agent gbrain import /workspace/setup/mockdata/garry --no-embed
```

(`--no-embed` skips vector embedding so it works without `OPENAI_API_KEY`. Keyword search still finds Acme.)

### Explicitly skipped

- Unit tests for validation paths.
- Concurrency stress test.
- Auth/TLS/CORS tests (none exist).
- Agent-card JSON-schema validation against the A2A spec.
- Multi-brain / `--source` tests (out of scope).

## Out of scope (deferred to follow-up specs)

- **Multi-instance deployment**: running multiple Hermes containers (one per partner brain) with distinct ports and `hermes-home` volumes.
- **Caller side**: a way for Hermes to make outbound A2A calls (as a tool, or documented use of an existing HTTP-request capability).
- **Multi-brain selector**: scoping `/message:send` to a specific GBrain source via `--source` or a metadata field. `gbrain query --source <id>` already exists and is the natural extension point.
- **Tasks / streaming / push notifications**: any A2A surface beyond `message:send`.
- **Auth**: securitySchemes in the agent card, bearer tokens, etc.
- **Output cleaning**: regex-based stripping of Hermes session-info trailers. Deferred until observed in practice.
- **Schemas**: full A2A AgentCard / Message JSON-schema validation.

The next spec, when it gets written, is "multi-instance + caller side" — that is what unlocks the actual partner-to-partner brain-merging demo flow described in `docs/gbrain-acme-demo-workflow.md`.

## References

- A2A protocol overview: https://a2a-protocol.org/latest/topics/what-is-a2a/
- A2A specification: https://a2a-protocol.org/latest/specification/
- Hermes Agent (NousResearch): https://github.com/NousResearch/hermes-agent
- GBrain (garrytan): https://github.com/garrytan/gbrain
- Demo workflow that motivates this spec: [`docs/gbrain-acme-demo-workflow.md`](../gbrain-acme-demo-workflow.md)
