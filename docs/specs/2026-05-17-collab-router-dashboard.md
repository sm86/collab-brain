# Collab Router Dashboard Spec

**Date:** 2026-05-17  
**Status:** Implemented draft  
**Scope:** Demo UI and observability surface for collab-router agent cards, editable demo policy, and live routing events

## Summary

Add a standalone `collab-dashboard` service for demos. Telegram and Hermes remain the conversational surfaces; this dashboard is the projected control-plane view that makes the router story easy to understand:

- which partner agents exist
- which agent cards and skills are available
- which brain routes are local, allowed, or blocked
- how demo policy changes affect the matrix
- what committed mock markdown seeded each partner brain
- what happened when the router handled a request

The current implementation is a single stdlib Python server in `src/dashboard_server.py`, packaged by `setup/docker/dashboard.Dockerfile`, and exposed by Compose at `http://localhost:8095`.

## Demo UI

The dashboard should read clearly on a projected screen. It uses a compact operational layout rather than a landing page.

### Policy Controls

The top-right control resets the in-memory policy to the default demo hierarchy. The dashboard intentionally labels this as **Demo Policy**, not production router policy.

Default hierarchy:

```text
Garry -> Monica -> Laurie
```

Default access:

| Caller | Garry | Monica | Laurie |
|---|---|---|---|
| Garry | Local | Allowed | Allowed |
| Monica | Blocked | Local | Allowed |
| Laurie | Blocked | Blocked | Local |

This tells the demo story directly:

- Everyone can use their own brain locally.
- Garry can access Monica and Laurie.
- Monica cannot access Garry, but can access Laurie.
- Laurie cannot access Garry or Monica.

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
| `Local` | Caller and target are the same partner. The agent uses its own local brain; no router call is needed. |
| `Allowed` | Demo policy permits this caller -> target route for `company-info`. |
| `Blocked` | Demo policy blocks the route before any outbound A2A call. |

Non-local cells include a `company-info` checkbox. Toggling it calls `PATCH /admin/access`, updates in-memory demo policy, refreshes the matrix, and appends a `policy_updated` timeline event.

The matrix reflects dashboard demo policy, not `setup/router/config.yaml`.

### Org Hierarchy Diagram

The policy panel includes a small visual hierarchy:

```text
Garry -> Monica -> Laurie
```

This is a demo explanation aid. It does not imply reporting structure outside the synthetic demo.

### Mock Data Tab

The dashboard has a second tab, **Mock Data**, that shows the committed markdown files used to seed each demo partner brain. It is read-only and backed by `setup/mockdata`, not `/root/.gbrain`.

The UI groups files by partner and folder:

- `companies`
- `people`
- `meetings`

Selecting a file displays the markdown content in a fixed-width reader. This helps the demo audience understand why each partner agent has different context.

### Live Timeline

The timeline shows newest events first. Each event includes:

- event type
- caller
- target
- skill
- status
- reason
- duration when provided

Rejected routes must be visually clear: the router decision is shown, and no A2A success/failure event should appear for that target. Local routes should show `local` and explain that no router call is needed.

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

Returns current demo policy, configured partners, access matrix, recent events, and uptime.

Optional query:

- `include_cards=1`: also fetch and include agent card state.

The response includes:

- `policy_mode`: currently `demo`
- `policy`: in-memory demo policy, including `label`, `description`, and caller rules
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

### `GET /admin/mock-data`

Returns an index of committed mock markdown files grouped by partner and folder.

Example shape:

```json
{
  "root": "/workspace/setup/mockdata",
  "partners": {
    "garry": {
      "available": true,
      "groups": {
        "companies": [
          {
            "path": "companies/acme.md",
            "name": "acme.md",
            "group": "companies"
          }
        ]
      }
    }
  }
}
```

### `GET /admin/mock-data/file`

Returns one committed markdown file.

Query parameters:

| Name | Required | Example |
|---|---:|---|
| `partner` | yes | `garry` |
| `path` | yes | `companies/acme.md` |

Response:

```json
{
  "partner": "garry",
  "path": "companies/acme.md",
  "name": "acme.md",
  "content": "# Acme..."
}
```

The implementation validates the partner key, requires a `.md` file, and rejects path traversal.

### `PATCH /admin/access`

Updates one non-local route in the in-memory demo policy.

Request:

```json
{
  "caller": "garry",
  "target": "monica",
  "skill": "company-info",
  "enabled": false
}
```

Rules:

- `enabled` must be boolean.
- `caller` and `target` must be configured partners.
- local routes cannot be edited.
- only `company-info` is supported in v0.

Successful responses return the normalized event and updated access matrix:

```json
{
  "event": {
    "event": "policy_updated",
    "caller": "garry",
    "target": "monica",
    "skill": "company-info",
    "status": "blocked",
    "reason": "policy blocked"
  },
  "access_matrix": {}
}
```

### `POST /admin/policy/reset`

Resets the in-memory demo policy to the default hierarchy.

Successful responses return the full `/admin/state` payload and append a `policy_reset` event.

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

For allowed synthetic routes, this endpoint appends both a `router_decision` event and a hardcoded `a2a_call_succeeded` event with `duration_ms: 1200` and `reason: "demo call completed"`. Rejected synthetic routes append only the `router_decision` event. Local synthetic routes append only a `router_decision` event with status `local`.

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
| `DASHBOARD_AGENT_CARD_TIMEOUT` | `2.5` | Seconds to wait for sidecar health/card fetches. |
| `DASHBOARD_MAX_EVENTS` | `100` | Max in-memory timeline events. |
| `DASHBOARD_PARTNERS_JSON` | unset | Optional JSON override for partner names and A2A URLs. |
| `DASHBOARD_MOCKDATA_ROOT` | `/workspace/setup/mockdata` | Read-only root for mock markdown files. |

Default partners:

```json
{
  "garry": {"name": "Garry", "a2a_url": "http://hermes-garry:8080"},
  "monica": {"name": "Monica", "a2a_url": "http://hermes-monica:8080"},
  "laurie": {"name": "Laurie", "a2a_url": "http://hermes-laurie:8080"}
}
```

## Current Limitations

- Demo policy state is in memory and resets on dashboard restart.
- The dashboard access matrix uses built-in demo policy, not `setup/router/config.yaml`.
- Timeline storage is in memory only.
- In-memory state is best-effort under concurrent updates in the threaded demo server.
- Admin endpoints are unauthenticated; Compose binds the host port to `127.0.0.1`.
- `POST /admin/demo-request` is synthetic and does not represent real router traffic.
- Dashboard policy toggles do not yet modify live router MCP policy.
- Mock Data reads committed markdown only; it does not inspect the imported GBrain database.

## Future Work

- Load the access matrix from `setup/router/config.yaml` or a shared policy store.
- Make dashboard policy edits update live router behavior once the dashboard graduates from demo policy to router policy.

## Test Plan

Implemented tests cover:

- default hierarchy allows Garry -> Monica and Garry -> Laurie
- default hierarchy allows Monica -> Laurie
- default hierarchy blocks Monica -> Garry
- default hierarchy blocks Laurie -> Garry and Laurie -> Monica
- self routes are local
- policy toggles can enable and disable non-local routes
- local route edits are rejected
- policy reset restores the default hierarchy
- timeline events are normalized with expected fields
- mock data index lists committed markdown
- mock data file reads return content
- path traversal is rejected for mock data file reads

Validation commands:

```bash
python3 -m unittest discover -s tests -v
docker compose -f setup/docker/docker-compose.yml config --quiet
python3 -m py_compile src/a2a_server.py src/collab_router.py src/dashboard_server.py
```
