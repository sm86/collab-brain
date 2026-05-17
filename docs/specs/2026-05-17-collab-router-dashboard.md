# Collab Router Dashboard Spec

**Date:** 2026-05-17  
**Status:** Implemented draft  
**Scope:** Demo UI and observability surface for collab-router agent cards, access state, and live routing events

## Summary

Add a standalone `collab-dashboard` service for demos. Telegram and Hermes remain the conversational surfaces; this dashboard is the projected control-plane view that makes the router story easy to understand:

- which partner agents exist
- which agent cards and skills are available
- which routes are enabled or disabled
- what happened when the router handled a request

The current implementation is a single stdlib Python server in `src/dashboard_server.py`, packaged by `setup/docker/dashboard.Dockerfile`, and exposed by Compose at `http://localhost:8095`.

## Demo UI

The dashboard should read clearly on a projected screen. It uses a compact operational layout rather than a landing page.

### Scenario Bar

Top-right segmented controls switch between two predefined demo states:

| Scenario | Behavior |
|---|---|
| `Disabled demo` | Garry can ask Laurie, but Garry -> Monica is blocked. |
| `Enabled demo` | Garry can ask both Monica and Laurie. |

The active scenario uses strong contrast. Scenario changes append a `scenario_changed` event to the timeline.

### Agent Cards

The top content section shows one card per configured partner:

- Garry
- Monica
- Laurie

Each card displays:

- partner name and key
- sidecar A2A URL
- `/healthz` status: `ok`, `degraded`, or `unreachable`
- `/.well-known/agent-card.json` status: `ok`, `unknown`, or `unreachable`
- protocol binding when available
- exposed skills, especially `company-info`

Unreachable or malformed sidecars show degraded card state without breaking the page. The current UI maps `degraded` health to a neutral badge.

### Access Matrix

The middle section shows caller rows and target columns for the `company-info` skill.

Cell states:

| State | Meaning |
|---|---|
| `Allowed` | The selected scenario permits this caller -> target route. |
| `Blocked` | Policy blocks the route before any outbound A2A call, or the route is a self-call. |

The implementation has two route statuses: `allowed` and `blocked`. Self-calls are represented as `status: "blocked"` with `reason: "self blocked"` and are currently painted with the same blocked styling as policy-blocked cells. The matrix reflects the dashboard's active demo scenario. It is not yet loaded from `setup/router/config.yaml`.

### Live Timeline

The timeline shows newest events first. Each event includes:

- event type
- caller
- target
- skill
- status
- reason
- duration when provided

Rejected routes must be visually clear: the router decision is shown, and no A2A success/failure event should appear for that target. Allowed demo routes can show a router decision followed by A2A success/failure events when real router traffic posts them.

The browser polls `/admin/state` every 1.5 seconds and refreshes agent cards every 10 seconds.

## Admin API

### `GET /`

Serves the dashboard HTML, CSS, and JavaScript.

### `GET /healthz`

Returns dashboard liveness:

```json
{"status":"ok"}
```

### `GET /admin/state`

Returns current scenario, available scenarios, configured partners, access matrix, recent events, and uptime.

Optional query:

- `include_cards=1`: also fetch and include agent card state.

The response includes:

- `scenario`: active scenario id
- `scenario_detail`: full scenario config for the active scenario
- `scenarios`: `[{id,label,description}]` list used to render scenario buttons
- `partners`: configured partner map
- `access_matrix`: caller/target route state
- `events`: recent normalized events
- `uptime_seconds`: dashboard process uptime

### `GET /admin/agent-cards`

Fetches each configured partner's `/healthz` and `/.well-known/agent-card.json`, then returns normalized card state.

Example shape:

```json
{
  "agent_cards": [
    {
      "partner": "monica",
      "name": "Monica",
      "a2a_url": "http://hermes-monica:8080",
      "health": "ok",
      "card_status": "ok",
      "skills": [
        {
          "id": "company-info",
          "name": "Company info from brain",
          "description": "Given a company name or query..."
        }
      ],
      "protocol": "HTTP+JSON",
      "card": {
        "name": "Hermes",
        "skills": []
      },
      "error": null
    }
  ]
}
```

`card` contains the full raw agent-card JSON when the fetch succeeds. `protocol` is optional and is present only when the card fetch succeeds and includes a supported interface.

### `GET /admin/events`

Returns recent in-memory timeline events, newest first.

### `POST /admin/scenario`

Switches between predefined demo scenarios:

```json
{"scenario":"enabled"}
```

Allowed values:

- `enabled`
- `disabled`

Invalid scenarios return `400`.

Successful responses return the full `/admin/state` payload. The scenario switch also appends a `scenario_changed` event where `status` is the new scenario id, for example `enabled`, and `reason` is the human label, for example `Enabled demo`.

### `POST /admin/events`

Accepts best-effort event posts from router services.

```json
{
  "event": "router_decision",
  "caller": "garry",
  "target": "monica",
  "skill": "company-info",
  "status": "rejected",
  "reason": "policy blocked",
  "duration_ms": 0
}
```

The dashboard normalizes each event by adding an id and timestamp.

Routers can post events by setting:

```env
DASHBOARD_EVENTS_URL=http://collab-dashboard:8095/admin/events
```

Event posting is observability-only. Router behavior must continue if the dashboard is unavailable.

Successful responses return `201` with:

```json
{"event":{"id":"evt-...","timestamp":1779012345.0}}
```

### `POST /admin/demo-request`

Creates synthetic timeline events for local demoing without a live MCP request.

```json
{"caller":"garry","targets":["monica","laurie"]}
```

This endpoint is demo-only support. It does not call partner A2A sidecars and should not be used as proof of real router execution.

For allowed synthetic routes, this endpoint appends both a `router_decision` event and a hardcoded `a2a_call_succeeded` event with `duration_ms: 1200` and `reason: "demo call completed"`. Rejected synthetic routes append only the `router_decision` event.

Successful responses return `201` with:

```json
{"events":[{"event":"router_decision"},{"event":"a2a_call_succeeded"}]}
```

## Runtime Shape

Compose service:

```yaml
collab-dashboard:
  image: collab-brain-dashboard:latest
  build:
    context: ../..
    dockerfile: setup/docker/dashboard.Dockerfile
  ports:
    - "127.0.0.1:8095:8095"
```

Environment:

| Variable | Default | Purpose |
|---|---:|---|
| `DASHBOARD_BIND` | `0.0.0.0` | Bind address inside the container. |
| `DASHBOARD_PORT` | `8095` | Dashboard HTTP port. |
| `DASHBOARD_SCENARIO` | `disabled` | Initial demo scenario. |
| `DASHBOARD_AGENT_CARD_TIMEOUT` | `2.5` | Seconds to wait for sidecar health/card fetches. |
| `DASHBOARD_MAX_EVENTS` | `100` | Max in-memory timeline events. |
| `DASHBOARD_PARTNERS_JSON` | unset | Optional JSON override for partner names and A2A URLs. |

Default partners:

```json
{
  "garry": {"name": "Garry", "a2a_url": "http://hermes-garry:8080"},
  "monica": {"name": "Monica", "a2a_url": "http://hermes-monica:8080"},
  "laurie": {"name": "Laurie", "a2a_url": "http://hermes-laurie:8080"}
}
```

## Current Limitations

- Scenario state is in memory and resets on dashboard restart.
- The dashboard access matrix uses built-in demo scenarios, not `setup/router/config.yaml`.
- Timeline storage is in memory only.
- In-memory state is best-effort under concurrent updates in the threaded demo server.
- Admin endpoints are unauthenticated; Compose binds the host port to `127.0.0.1`.
- `POST /admin/demo-request` is synthetic and does not represent real router traffic.

## Future Work

- Load the access matrix from `setup/router/config.yaml` instead of built-in dashboard scenarios.
- Visually distinguish self-blocked routes from policy-blocked routes if the demo needs that distinction.

## Test Plan

Implemented tests cover:

- disabled scenario blocks Garry -> Monica
- disabled scenario allows Garry -> Laurie
- enabled scenario allows Garry -> Monica and Garry -> Laurie
- self routes are blocked
- timeline events are normalized with expected fields

Validation commands:

```bash
python3 -m unittest discover -s tests -v
docker compose -f setup/docker/docker-compose.yml config --quiet
python3 -m py_compile src/a2a_server.py src/collab_router.py src/dashboard_server.py
```
