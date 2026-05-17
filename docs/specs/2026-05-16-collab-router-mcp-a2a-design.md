# Collab Router MCP-to-A2A Design Spec

**Date:** 2026-05-16
**Status:** Implemented v0 on 2026-05-17; remaining work is hardening and broader end-to-end demo validation
**Scope:** Caller-side orchestration for Hermes agents to request partner brain context through a policy-aware router

## Summary

Add small, per-caller `collab-router` services that let Hermes agents ask other partner agents for brain-grounded company context without calling partner A2A sidecars directly.

Hermes should call the router as an MCP tool. The router should enforce allow/reject policy, then forward approved requests to the target partner's A2A `/message:send` endpoint.

```text
Hermes agent in a partner container
  -> MCP client call
     -> that partner's collab-router MCP server
        -> policy allow/reject
        -> A2A HTTP call
           -> target partner Hermes A2A sidecar
              -> target partner GBrain + Hermes
```

The router is the control plane. Partner A2A sidecars stay simple and local-brain-only. v0 uses one router instance per calling partner so caller identity comes from trusted deployment configuration, not from model-provided tool input.

## Naming

Use **`collab-router`** as the service and package name.

Do not use `gateway` for the first version. Hermes already has a `hermes gateway` command for messaging platforms, and `gateway` implies a broader public ingress boundary. This component is narrower: route collaborative partner-brain requests, enforce policy, and translate MCP tool calls into A2A calls.

Acceptable future names if the scope grows:

- `a2a-router`: if the service only routes A2A traffic.
- `partner-router`: if the domain remains partner-to-partner collaboration.
- `agent-broker`: if it later owns discovery, fanout, aggregation, retries, and richer policy.
- `a2a-gateway`: only if it becomes the main network ingress/egress boundary for all A2A traffic.

## Why MCP Outside, A2A Inside

Hermes already supports MCP servers as tool providers:

```bash
hermes mcp add <name> --url <endpoint>
hermes mcp add <name> --command <cmd> --args <args...>
```

Hermes also presents MCP tools using `server:tool` notation, for example `collab-router:ask_partner_brain`.

Verified locally on 2026-05-16 before this spec revision:

- `hermes mcp add <name> --url <endpoint>` exists.
- `hermes mcp add <name> --command <cmd> --args <args...>` exists.
- `hermes tools` manages built-in and MCP tools using names such as `server:tool`.

Verified for the v0 implementation on 2026-05-17:

- Hermes `--url` works with the router's stateless Streamable HTTP-style MCP endpoint at `/mcp`.
- The router handles JSON-RPC `initialize`, `ping`, `tools/list`, and `tools/call` over HTTP POST.
- The router does not issue `Mcp-Session-Id`; it is stateless and expects every JSON-RPC message to arrive as a standalone HTTP POST.
- `hermes tools enable collab-router:ask_partner_brain collab-router:ask_partner_brains` enables the tools.
- Hermes can attach header auth using `headers.Authorization: Bearer ${MCP_COLLAB_ROUTER_API_KEY}` in `~/.hermes/config.yaml`; the token value is stored in `~/.hermes/.env`.

Implemented v0 gates:

- MCP HTTP transport is verified against Hermes and documented here with its stateless session behavior.
- Caller-to-router isolation is implemented with per-caller MCP auth tokens.
- Target A2A sidecars are configured to listen on the Compose network with `A2A_BIND=0.0.0.0`.
- Router-to-sidecar bearer-token verification is implemented for `/message:send`.

Use MCP between Hermes and the router because:

- It is Hermes' existing extension path for callable tools.
- It gives the model a typed tool instead of relying on ad hoc `curl`.
- It avoids patching Hermes core for a demo-specific A2A client.
- It leaves room to package the router as a plugin later.

Use A2A between the router and partner agents because:

- Partner sidecars already expose an A2A-shaped `POST /message:send`.
- A2A is the intended agent-to-agent protocol surface in this repo.
- It keeps each partner's local GBrain access inside that partner container.

## Non-Goals

- Do not build a generic full A2A client into Hermes core.
- Do not expose partner A2A sidecars directly to end-user prompts or public networks.
- Do not implement A2A tasks, streaming, push notifications, or JSON-RPC envelopes in v0.
- Do not let the router read partner GBrain stores directly.
- Do not merge partner brain data into one shared persistent brain.
- Do not make policy decisions inside the LLM prompt.

## Components

### Hermes Agent

Hermes acts as the MCP client. It should call a router-provided MCP tool when it needs another partner's brain context.

Recommended tool name:

```text
collab-router:ask_partner_brain
collab-router:ask_partner_brains
```

Recommended profile or skill guidance:

```text
When you need another demo partner's local brain context, call
collab-router:ask_partner_brain for one partner or
collab-router:ask_partner_brains for multiple partners. Do not invent partner
knowledge. Do not call partner A2A sidecars directly.
```

### Collab Router

The router is a standalone service. v0 runs one router instance per caller, for example `collab-router-garry`, `collab-router-monica`, and `collab-router-laurie`. Each instance must be reachable only by its corresponding Hermes agent through MCP auth or Docker network segmentation, and acts as an A2A client to other partner sidecars.

Responsibilities:

- Receive typed MCP tool calls from Hermes.
- Identify the calling partner from trusted router deployment config.
- Validate the requested target partner(s), effective skill, query, and purpose.
- Apply deterministic allow/reject policy before any outbound A2A call.
- Forward approved requests to the target partner's `/message:send`.
- Return the target partner's A2A response text to Hermes.
- Log decision metadata for audit and debugging.

### Partner A2A Sidecars

Existing sidecars stay unchanged for v0. They expose:

- `GET /healthz`
- `GET /.well-known/agent-card.json`
- `POST /message:send`

Each sidecar queries only its own local GBrain and returns a concise company briefing.

The sidecar contract is defined by [Hermes A2A Endpoint - Design Spec](./2026-05-16-hermes-a2a-endpoint-design.md). If that sidecar request/response shape changes, this router spec must be updated to match it rather than becoming a second source of truth.

Router-to-sidecar routing requires sidecars to listen on the Compose network:

```yaml
environment:
  A2A_ENABLED: "true"
  A2A_BIND: 0.0.0.0
  A2A_PORT: 8080
  A2A_ROUTER_TOKEN: "${A2A_ROUTER_TOKEN}"
```

This is distinct from host publication. A sidecar bound to the prior default `127.0.0.1` is reachable only from inside its own container and cannot be called by `collab-router-*`.

If sidecar ports are published for host debugging, bind them to localhost only or place them behind a debug Compose profile:

```yaml
ports:
  - "127.0.0.1:8081:8080"
```

Do not publish sidecar ports on all host interfaces for the default demo path.

## Caller Identity

Caller identity is load-bearing. v0 must not accept caller identity from the LLM, prompt text, ordinary MCP tool arguments, or A2A metadata.

Use one router instance per caller:

```yaml
collab-router-garry:
  environment:
    ROUTER_CALLER: garry

collab-router-monica:
  environment:
    ROUTER_CALLER: monica

collab-router-laurie:
  environment:
    ROUTER_CALLER: laurie
```

Each Hermes container is configured to talk only to its own router instance:

```text
hermes-garry -> collab-router-garry
hermes-monica -> collab-router-monica
hermes-laurie -> collab-router-laurie
```

The router must ignore any tool-supplied `caller`, `source`, or equivalent identity field if one appears. It may include `ROUTER_CALLER` in forwarded A2A metadata for observability, but policy decisions must use only the trusted configured caller.

One-router-per-caller is not sufficient by itself on the default Compose network: any service can usually reach `http://collab-router-garry:8090/mcp` unless the network or MCP server blocks it. v0 must therefore use one of these controls:

- **Preferred:** Per-caller MCP auth token. Each Hermes container is configured with only its own router token; each router rejects MCP requests without the matching token.
- **Alternative:** Per-caller Docker networks. Each Hermes container shares a private MCP network only with its own router, while routers also join a shared A2A network for sidecar calls.
- **Demo-only acceptance:** If neither control is implemented, cross-router impersonation is an accepted local-demo gap: Monica's Hermes could call Garry's router and be treated as Garry.

## MCP Tool Contract

### `ask_partner_brain`

Ask one partner's local brain what it knows about a company or founder context.

Input schema:

```json
{
  "partner": "monica",
  "company_query": "Acme",
  "purpose": "Prep Garry for a meeting with Maya from Acme in 30 minutes"
}
```

Fields:

| Field | Type | Required | Notes |
|---|---:|---:|---|
| `partner` | string | yes | Target partner key, for example `garry`, `monica`, `laurie`. |
| `company_query` | string | yes | Company name or concise query. |
| `purpose` | string | yes | Why the caller needs this context. Required for policy and audit. |

The `skill` is intentionally not an input in v0. The router fixes it to `default_skill` (`company-info`) so the model cannot request arbitrary sidecar capabilities. If additional skills are added later, make `skill` an explicit enum field and validate it against policy.

Output on allow:

```json
{
  "status": "ok",
  "partner": "monica",
  "skill": "company-info",
  "text": "Monica has two Acme touchpoints..."
}
```

Output on reject:

```json
{
  "status": "rejected",
  "partner": "monica",
  "skill": "company-info",
  "reason": "garry is not allowed to ask monica for this skill"
}
```

Output on upstream failure:

```json
{
  "status": "upstream_error",
  "partner": "monica",
  "skill": "company-info",
  "reason": "target A2A endpoint timed out"
}
```

`status` is the single discriminator the model should branch on. Do not combine a success flag with an error field.

Tool behavior:

1. Normalize `partner` to a configured partner key.
2. Load caller identity from trusted router config such as `ROUTER_CALLER`.
3. Require non-empty `company_query` and `purpose`.
4. Evaluate policy.
5. If rejected, return `status=rejected` without calling A2A.
6. If allowed, create an A2A `SendMessageRequest`.
7. POST to the target partner's `/message:send`.
8. Extract `message.parts[*].text` from the A2A response.
9. Return `status=ok` with the text, or `status=upstream_error` if the sidecar call fails.

### `ask_partner_brains`

Ask multiple partner brains the same company/founder question in parallel. This is included in v0 because the primary demo asks Monica and Laurie for Acme context, and sequential partner calls can add avoidable latency on stage.

Input schema:

```json
{
  "partners": ["monica", "laurie"],
  "company_query": "Acme",
  "purpose": "Prep Garry for a meeting with Maya from Acme in 30 minutes"
}
```

Fields:

| Field | Type | Required | Notes |
|---|---:|---:|---|
| `partners` | string array | yes | Target partner keys. Empty arrays reject. Duplicate partners are de-duped. |
| `company_query` | string | yes | Company name or concise query. |
| `purpose` | string | yes | Why the caller needs this context. Required for policy and audit. |

Output:

```json
{
  "status": "ok",
  "skill": "company-info",
  "results": [
    {
      "status": "ok",
      "partner": "monica",
      "skill": "company-info",
      "text": "Monica has two Acme touchpoints..."
    },
    {
      "status": "ok",
      "partner": "laurie",
      "skill": "company-info",
      "text": "Laurie has product and compliance notes..."
    }
  ]
}
```

Batch status semantics:

| Condition | Batch `status` |
|---|---|
| All partner calls return `ok` | `ok` |
| At least one partner returns `ok`, and at least one returns `rejected` or `upstream_error` | `partial` |
| No partner returns `ok` because policy rejects every target | `rejected` |
| No partner returns `ok` because every allowed target fails upstream | `upstream_error` |

Each item in `results` uses the same per-partner shape as `ask_partner_brain`, including `status`, `partner`, `skill`, and either `text` or `reason`.

Tool behavior:

1. Normalize and de-dupe `partners`.
2. Load caller identity from trusted router config such as `ROUTER_CALLER`.
3. Require non-empty `partners`, `company_query`, and `purpose`.
4. Evaluate policy independently for each target partner.
5. Return rejected items without calling A2A.
6. Forward all allowed partner calls concurrently, with one timeout per target.
7. Preserve the requested partner order in `results`.

## A2A Forwarding Contract

The router sends the existing v0.1 A2A-shaped body defined by [Hermes A2A Endpoint - Design Spec](./2026-05-16-hermes-a2a-endpoint-design.md):

```json
{
  "message": {
    "messageId": "<router-generated uuid>",
    "role": "ROLE_USER",
    "parts": [
      {
        "text": "Acme"
      }
    ]
  },
  "metadata": {
    "caller": "garry",
    "target": "monica",
    "skill": "company-info",
    "purpose": "Prep Garry for a meeting with Maya from Acme in 30 minutes"
  }
}
```

The current sidecar ignores `metadata`, which is acceptable. The router still includes it so logs and future sidecar policy hooks have a stable shape.

Router-to-sidecar calls must include:

```http
Authorization: Bearer ${A2A_ROUTER_TOKEN}
```

Sidecars must reject `/message:send` when `A2A_ROUTER_TOKEN` is configured and the bearer token is missing or wrong. `GET /healthz` may remain unauthenticated for local health checks.

The router expects:

```json
{
  "message": {
    "messageId": "<target-generated uuid>",
    "role": "ROLE_AGENT",
    "parts": [
      {
        "text": "<briefing>"
      }
    ]
  }
}
```

## Routing Configuration

Use Docker service names for in-network routing, not host `localhost` ports.

Example router config:

```yaml
caller: garry

partners:
  garry:
    a2a_url: http://hermes-garry:8080
  monica:
    a2a_url: http://hermes-monica:8080
  laurie:
    a2a_url: http://hermes-laurie:8080

default_skill: company-info
timeout_seconds: 90
```

From inside a container, `localhost` points to that same container. The router must call Compose service names such as `http://hermes-monica:8080/message:send`.

Host-mapped ports like `127.0.0.1:8081:8080`, `127.0.0.1:8082:8080`, and `127.0.0.1:8083:8080` are only for host smoke tests or local debugging.

## Policy Configuration

Policy should be deterministic and evaluated before forwarding.

Example:

```yaml
policy:
  require_purpose: true
  deny_self_calls: true

  callers:
    garry:
      can_ask:
        - monica
        - laurie
      skills:
        - company-info
    monica:
      can_ask:
        - garry
        - laurie
      skills:
        - company-info
    laurie:
      can_ask:
        - garry
        - monica
      skills:
        - company-info
```

Optional v0.2 policy fields:

```yaml
  allow_companies:
    - Acme
  deny_companies: []
  max_query_chars: 500
  rate_limits:
    per_caller_per_minute: 10
```

Policy response semantics:

| Condition | Result |
|---|---|
| Unknown caller | reject |
| Unknown target partner | reject |
| Missing purpose | reject |
| Caller targets self and `deny_self_calls=true` | reject |
| Skill not allowed for caller | reject |
| Target not in caller's `can_ask` list | reject |
| A2A target timeout/failure | policy allow stands, but tool returns `status=upstream_error` |

## Docker Shape

Add one service per caller. Example for Garry:

```yaml
collab-router-garry:
  image: collab-brain-router:latest
  build:
    context: ../..
    dockerfile: setup/docker/router.Dockerfile
  environment:
    ROUTER_CALLER: garry
    ROUTER_CONFIG: /workspace/setup/router/config.yaml
    COLLAB_ROUTER_MCP_TOKEN: "${COLLAB_ROUTER_GARRY_MCP_TOKEN}"
    A2A_ROUTER_TOKEN: "${A2A_ROUTER_TOKEN}"
  volumes:
    - ../..:/workspace
```

Do not publish router ports in the default Compose file. Host `ports:` are for debugging only and should be added under a debug override or Compose profile, because publishing them weakens the "only the corresponding Hermes can call this router" assumption.

If a router host port is needed for debugging, bind it to localhost:

```yaml
ports:
  - "127.0.0.1:8091:8090"
```

Repeat for each caller with distinct service names:

| Hermes container | Router service | MCP URL registered inside that Hermes container |
|---|---|---|
| `hermes-garry` | `collab-router-garry` | `http://collab-router-garry:8090/mcp` |
| `hermes-monica` | `collab-router-monica` | `http://collab-router-monica:8090/mcp` |
| `hermes-laurie` | `collab-router-laurie` | `http://collab-router-laurie:8090/mcp` |

Do not register every Hermes container against `collab-router-garry`; that silently makes every caller look like Garry.

MCP caller-auth tokens and router-to-sidecar tokens live in `setup/docker/env/hermes.env`, not tracked YAML or profile files:

```env
COLLAB_ROUTER_GARRY_MCP_TOKEN=...
COLLAB_ROUTER_MONICA_MCP_TOKEN=...
COLLAB_ROUTER_LAURIE_MCP_TOKEN=...
A2A_ROUTER_TOKEN=...
```

Hermes header auth is configured interactively by `hermes mcp add`. The saved v0 shape is:

```bash
headers:
  Authorization: Bearer ${MCP_COLLAB_ROUTER_API_KEY}
```

Hermes containers should connect to their own router via MCP:

```bash
hermes mcp add collab-router --url http://collab-router-garry:8090/mcp
```

Enable the MCP tools using:

```bash
hermes tools enable collab-router:ask_partner_brain
hermes tools enable collab-router:ask_partner_brains
```

If Hermes is configured outside Compose, use the host-published router URL instead:

```bash
hermes mcp add collab-router --url http://localhost:8091/mcp --auth header
```

Only use host-published router URLs for local debugging or non-Compose Hermes clients.

If using Docker network isolation instead of MCP auth, use this topology:

```text
mcp-garry:  hermes-garry  <-> collab-router-garry
mcp-monica: hermes-monica <-> collab-router-monica
mcp-laurie: hermes-laurie <-> collab-router-laurie
a2a-backplane: all collab-router-* services + all hermes-* A2A sidecars
```

Hermes containers should not join other callers' `mcp-*` networks. Routers join their caller-specific `mcp-*` network plus the shared `a2a-backplane`. Sidecars join `a2a-backplane`.

## Security Model

v0 is demo-local and Docker-network-scoped. Caller identity is trusted only if each router instance's `ROUTER_CALLER` is paired with caller-to-router isolation. `ROUTER_CALLER` alone is not a security boundary.

Required v0 protections:

- Router is the only service Hermes agents are instructed and configured to call.
- Each router accepts MCP requests only from its corresponding Hermes agent, enforced by per-caller MCP auth or per-caller Docker networks.
- Partner sidecars used by the router set `A2A_ENABLED=true`, `A2A_BIND=0.0.0.0`, and `A2A_PORT=8080`.
- Partner sidecars should not be host-published by default. If published for debugging, bind to `127.0.0.1`, for example `127.0.0.1:8081:8080`.
- Router rejects by default.
- Every request has an effective caller, target partner, fixed skill, query, and purpose before policy evaluation.
- Router logs all decisions.
- Router-to-sidecar `/message:send` requests must include `Authorization: Bearer ${A2A_ROUTER_TOKEN}`.
- Sidecars must reject `/message:send` without the configured `A2A_ROUTER_TOKEN`.

Demo-only acceptance:

- Without MCP auth or per-caller Docker networks, a Hermes container could bypass caller identity by calling another caller's router, for example Monica calling `http://collab-router-garry:8090/mcp` and being treated as Garry. This is acceptable only for a local hackathon/demo build and must block implementation approval for any hosted or adversarial deployment.
- If sidecar token verification is intentionally omitted, a Hermes container could still bypass policy by directly calling another partner's `http://hermes-*:8080/message:send` endpoint on the Compose network. Omitting token verification is acceptable only for a local throwaway demo and keeps the spec blocked for implementation approval.

Deferred production protections:

- Stronger MCP authentication for hosted deployments.
- Signed caller identity.
- TLS for cross-host traffic.
- Structured audit log persistence.
- Rate limiting.
- Request body size limits.

## Logging

Log one structured event per router decision:

```json
{
  "event": "router_decision",
  "caller": "garry",
  "target": "monica",
  "skill": "company-info",
  "status": "ok",
  "reason": "policy allow",
  "duration_ms": 18432
}
```

For rejected requests, do not log full sensitive prompt text by default. Log the normalized company query only if explicitly enabled for demo debugging.

## Error Handling

MCP tool responses should be model-readable and non-ambiguous.

Examples:

```json
{
  "status": "rejected",
  "partner": "monica",
  "skill": "company-info",
  "reason": "unknown target partner: brad"
}
```

```json
{
  "status": "upstream_error",
  "partner": "monica",
  "skill": "company-info",
  "reason": "target A2A endpoint timed out"
}
```

Rejects and upstream failures are different:

- Reject means policy blocked the request before A2A.
- Upstream failure means policy allowed the request, but the target sidecar failed.

## Demo Flow

User asks Garry's Hermes:

```text
I am meeting Maya from Acme in 30 minutes. What do Monica and Laurie know?
```

Garry's Hermes should:

1. Search Garry's local GBrain first if needed.
2. Call `collab-router:ask_partner_brains` with `partners=["monica","laurie"]` and `company_query=Acme`.
3. Merge Garry, Monica, and Laurie context into one meeting brief.
4. Clearly attribute partner-sourced context.

The router should:

1. Approve Garry -> Monica `company-info`.
2. Approve Garry -> Laurie `company-info`.
3. Forward to `http://hermes-monica:8080/message:send` and `http://hermes-laurie:8080/message:send` concurrently.
4. Return both partner briefings to Garry's Hermes in the requested order.

## Implementation Options

### Option A: Single Python Router Implementation with Streamable HTTP MCP

One Python service implements:

- MCP server endpoint at `/mcp`, using stateless Streamable HTTP-style JSON-RPC POSTs verified against `hermes mcp add --url`.
- Internal A2A HTTP client.
- YAML config loading.
- Policy evaluation.

This is the implemented v0. Sessions are stateless; no `Mcp-Session-Id` is issued. Tool calls are authenticated by per-caller bearer tokens stored in `setup/docker/env/hermes.env` and registered into each Hermes profile as `MCP_COLLAB_ROUTER_API_KEY`.

### Option B: Stdio MCP Server Inside Each Hermes Container

Install a small stdio MCP server into each Hermes container. The stdio server calls a central HTTP router.

This is useful if HTTP MCP has environment or auth friction. It is less clean operationally because every Hermes container needs the stdio MCP server installed/configured.

### Option C: Direct Hermes Shell/Curl Skill

Write only a skill that instructs Hermes to call `curl` against the router.

Do not choose this except as a temporary debugging fallback. It is less typed, less reliable, and harder to audit.

## Test Plan

Router unit checks:

- Unknown caller rejects.
- Unknown target rejects.
- Missing purpose rejects.
- Self-call rejects when configured.
- Allowed caller/target/skill passes.
- Denied caller/target/skill rejects before outbound HTTP.
- `ask_partner_brains` fanout preserves partner order and returns `partial` when one target fails.

Router integration checks:

```bash
docker compose -f setup/docker/docker-compose.yml exec collab-router-garry \
  curl -s http://localhost:8090/healthz
```

From inside a Hermes container:

```bash
hermes mcp add collab-router --url http://collab-router-garry:8090/mcp
hermes mcp test collab-router
# Enable the MCP tool using the verified Hermes tool-selection command.
```

Positive caller auth/isolation check:

```text
From hermes-garry, collab-router-garry must be reachable and must list/call
collab-router:ask_partner_brain and collab-router:ask_partner_brains.
```

Sidecar reachability check from the router:

```bash
docker compose -f setup/docker/docker-compose.yml exec collab-router-garry \
  curl -s http://hermes-monica:8080/healthz
```

Caller isolation check:

```text
From hermes-monica, a request to collab-router-garry must fail auth or be unreachable unless the implementation has explicitly accepted the demo-only cross-router spoofing gap.
```

End-to-end demo check:

```text
Ask Garry's Hermes: "I am meeting Maya from Acme in 30 minutes. Ask Monica and Laurie what they know, then merge it into a meeting plan."
```

Expected:

- Garry's Hermes calls `collab-router:ask_partner_brains`.
- Router logs two allowed decisions.
- Router calls Monica and Laurie A2A sidecars concurrently.
- Final answer includes partner-attributed context.
- No direct call from Garry's Hermes to `http://hermes-monica:8080` or `http://hermes-laurie:8080`.

## Open Questions

- Should policy be global YAML, per-partner YAML, or loaded from a future admin UI?
- Should rejected requests be visible to the target partner, or only to the caller/admin logs?

## Recommendation

Build `collab-router` as per-caller MCP server instances plus an A2A client. Trust caller identity only from deployment config plus caller-to-router isolation, not from tool input. Keep partner A2A sidecars private and simple, but require shared `A2A_ROUTER_TOKEN` verification on `/message:send`. Use deterministic router policy for allow/reject. Include `ask_partner_brains` fanout in v0 for the stage demo. Package as a Hermes plugin only after the standalone service works end to end.
