# Garry Telegram `/collab` Slash Command Spec

**Date:** 2026-05-17  
**Status:** Implemented MVP on 2026-05-17  
**Scope:** Garry-only Telegram slash command for toggling company brain access

## Summary

Add a Garry-only Hermes plugin that registers a Telegram-visible `/collab`
slash command.

The command controls whether Garry's Telegram agent can use the
`collab-router` MCP tools:

```text
collab-router:ask_partner_brain
collab-router:ask_partner_brains
```

User-facing copy should call this **company brain access**, not "Garry's
collab brain." Garry-only is the deployment scope, not the product label.

This is a demo operator switch. It does not change partner A2A sidecar
availability, does not change router policy, and does not grant Monica or
Laurie any new access.

## Goals

- Let the demo operator turn company brain access on and off from
  Telegram.
- Make `/collab status` explain the current company brain access state clearly.
- Keep the feature scoped to Garry for now.
- Avoid patching Hermes core.
- Avoid editing tracked Hermes profile files under `/root/.hermes` directly.
- Preserve the existing router policy model: tool availability and route
  authorization remain separate controls.

## Non-Goals

- Do not implement `/collab` for Monica or Laurie in this version.
- Do not let the LLM decide policy.
- Do not expose arbitrary `hermes config` or shell command execution through
  Telegram.
- Do not toggle `A2A_ENABLED`; that is an inbound sidecar/container-level
  switch.
- Do not promise immediate mid-turn tool-cache mutation. The MVP may require a
  fresh session via `/reset`.

## User Experience

### `/collab status`

Reports Telegram company brain access state.

Example when enabled:

```text
Company brain access is on for Telegram.

Available tools:
- ask_partner_brain
- ask_partner_brains

Policy still controls which partners Garry can ask.
```

Example when disabled:

```text
Company brain access is off for Telegram.

Garry will answer from his own brain only unless another tool is enabled.
```

### `/collab on`

Enables the two collab-router MCP tools for the `telegram` platform.

MVP response:

```text
Company brain access is on for Telegram.
Send /reset to start a fresh session with company brain access.
```

### `/collab off`

Disables the two collab-router MCP tools for the `telegram` platform.

MVP response:

```text
Company brain access is off for Telegram.
Send /reset to start a fresh session without company brain access.
```

### Invalid Usage

For anything except `on`, `off`, or `status`, return:

```text
Usage: /collab on | off | status
```

If the user sends plain `/collab`, treat it as `/collab status`.

## Implementation Approach

Use a Hermes user plugin installed only in Garry's persisted Hermes home:

```text
/root/.hermes/plugins/collab_toggle/
  plugin.yaml
  __init__.py
```

The repo-tracked seed lives at:

```text
setup/docker/mock-garry-profile/plugins/collab_toggle/
```

`setup/docker/entrypoint.sh` seeds profile plugins into `/root/.hermes/plugins`
non-destructively and enables newly seeded plugins with `hermes plugins enable`.
The running demo container has also been seeded and enabled manually.

The plugin should register one command:

```python
ctx.register_command(
    "collab",
    handler=handle_collab,
    description="Turn company brain access on/off",
    args_hint="[on|off|status]",
)
```

Hermes gateway dispatch already supports plugin slash commands. Registered
commands are visible through `/commands` and dispatched before skill commands.

## State Model

The source of truth is Garry's Hermes tool configuration for the `telegram`
platform.

The plugin should toggle exactly these tool names:

```text
collab-router:ask_partner_brain
collab-router:ask_partner_brains
```

Preferred implementation:

- Reuse Hermes' internal tool configuration helpers if a stable API is
  available.
- Otherwise, invoke Hermes' own CLI as a subprocess:

```bash
hermes tools enable --platform telegram \
  collab-router:ask_partner_brain collab-router:ask_partner_brains

hermes tools disable --platform telegram \
  collab-router:ask_partner_brain collab-router:ask_partner_brains
```

Subprocess execution is acceptable for the MVP because the command is
operator-only, narrow, and uses Hermes' public CLI instead of hand-editing
config YAML.

## Session Reload Behavior

Hermes snapshots available tools for a session. The MVP should not attempt to
mutate the active session's tool cache.

After `on` or `off`, tell the user to send:

```text
/reset
```

This is clear enough for the stage demo and avoids fragile mid-session reload
behavior.

Optional follow-up:

- After toggling, call the same internal behavior as `/reload-mcp` or `/reset`
  if Hermes exposes a stable gateway API for that.
- Only do this after verifying prompt-cache and running-agent behavior.

## Authorization

The command is Garry-only by deployment:

- Install the plugin only in `hermes-garry`'s `/root/.hermes/plugins`.
- Do not copy it into Monica or Laurie profile templates yet.

The command should also fail closed if it is somehow installed elsewhere:

- Read `PARTNER_NAME` from the environment.
- If `PARTNER_NAME` is not `Garry`, return:

```text
/collab is only enabled for Garry in this demo.
```

Gateway user authorization remains Hermes' responsibility. This command should
not implement a separate user allowlist in v0.

## Router Policy Interaction

`/collab on` only makes the company brain tools available to Garry's Telegram
agent.

It does not change `setup/router/config.yaml`. If Garry asks an unauthorized
partner, the router still rejects the request.

For the current demo policy:

```text
Garry -> Monica: allowed
Garry -> Laurie: allowed
Monica -> Garry: blocked
Laurie -> Garry: blocked
```

The status output may mention this distinction, but should stay short.

## Failure Handling

If the Hermes CLI command fails, return a compact error:

```text
Could not update company brain access. Check Garry container logs.
```

Log the subprocess exit code and stderr to Hermes logs if possible.

If `collab-router` is not configured in Garry's MCP servers, `/collab on`
should return:

```text
collab-router is not configured for Garry. Register the MCP server first.
```

If the router is configured but currently unreachable, `/collab on` may still
enable the tools, but `/collab status` should say:

```text
Company brain access is enabled, but collab-router is not reachable right now.
```

## Acceptance Criteria

1. In Garry Telegram, `/commands` includes `/collab`.
2. `/collab status` returns enabled/disabled company brain access state.
3. `/collab on` enables:
   - `collab-router:ask_partner_brain`
   - `collab-router:ask_partner_brains`
4. `/collab off` disables both tools for Garry Telegram.
5. After `/collab on` plus `/reset`, Garry's Telegram agent can call the
   collab-router tools.
6. After `/collab off` plus `/reset`, Garry's Telegram agent answers without
   those collab-router tools.
7. Monica and Laurie do not gain `/collab` from this change.
8. Router policy still rejects disallowed routes independently of the toggle.

## Test Plan

### Unit-Level

If implemented as a plugin module, add tests for:

- argument parsing: empty, `status`, `on`, `off`, invalid
- Garry-only guard using `PARTNER_NAME`
- subprocess command construction
- status parsing from Hermes tool config

### Manual Docker Smoke Test

Enable the plugin in Garry's container and restart:

```bash
docker compose -f setup/docker/docker-compose.yml restart hermes-garry
```

Verify the command is registered:

```bash
docker compose -f setup/docker/docker-compose.yml exec hermes-garry \
  hermes plugins list
```

From Telegram:

```text
/commands
/collab status
/collab off
/reset
```

Ask Garry:

```text
I am meeting Maya from Acme. What do we know?
```

Expected: Garry should answer from his own sparse brain only.

Then:

```text
/collab on
/reset
```

Ask again:

```text
I am meeting Maya from Acme. What do we know?
```

Expected: Garry can call `collab-router` and bring in Monica/Laurie context.

## Rollout

1. Implement as a Garry-only user plugin in the running demo container.
2. Smoke-test in Telegram.
3. If stable, add a repo-tracked plugin or profile bootstrap path so new Garry
   volumes get the command automatically.
4. Later, generalize to all partners by making the plugin read caller identity
   and route config dynamically.

## Open Questions

- Should `/collab on` automatically trigger `/reset`, or should it only tell
  the user to reset?
- Should status check router reachability live, or only report tool
  availability?
- Should dashboard policy and live router policy eventually share one writable
  source of truth so `/collab status` can show both tool availability and
  route authorization?
