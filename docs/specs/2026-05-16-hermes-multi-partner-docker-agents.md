# Hermes Multi-Partner Docker Agents Spec

**Date:** 2026-05-16
**Status:** Implemented
**Scope:** Demo Docker deployment with one isolated Hermes container per partner

## Summary

The demo runs multiple Docker containers, not one container with multiple brain folders. Build one reusable Hermes image, then run one isolated container per partner:

- Garry: `hermes-garry` / `hermes-garry-agent`
- Monica: `hermes-monica` / `hermes-monica-agent`
- Laurie: `hermes-laurie` / `hermes-laurie-agent`

Each container mounts the repo at `/workspace` and has its own named volume mounted at `/root`, so `/root/.hermes` and `/root/.gbrain` are isolated per partner. Cross-brain collaboration is represented as separate partner agents with separate local memory.

No backward compatibility with the old single Garry container is required.

## Key Changes

- Keep one shared Docker image built from `setup/docker/Dockerfile`.
- Replace the single `hermes` Compose service with three partner services.
- Give each service its own `/root` named volume:
  - `hermes-garry-home`
  - `hermes-monica-home`
  - `hermes-laurie-home`
- Add partner profile templates:
  - `setup/docker/mock-garry-profile/`
  - `setup/docker/mock-monica-profile/`
  - `setup/docker/mock-laurie-profile/`
- Copy all partner profile templates and mock corpora into the shared image.
- Replace Garry-specific import env vars with partner-neutral vars:
  - `PARTNER_NAME`
  - `HERMES_PROFILE_TEMPLATE_DIR`
  - `GBRAIN_MOCK_SOURCE`
  - `GBRAIN_MOCK_IMPORT_ON_START`
  - `GBRAIN_MOCK_IMPORT_MARKER`

## Implementation

`setup/docker/docker-compose.yml` uses a shared `x-hermes-common` anchor for common runtime settings. Only `hermes-garry` declares the `build:` block; all services use the same `collab-brain-hermes:latest` image so Compose does not export duplicate partner images. Partner-specific values live in each service's `environment:` block, not in `setup/docker/env/hermes.env`.

Shared env file values are limited to common settings such as API keys, model defaults, `GBRAIN_HOME=/root`, `GBRAIN_INIT_ON_START=true`, and `GBRAIN_MOCK_IMPORT_ON_START=true`.

Partner-specific service values:

| Service | `PARTNER_NAME` | Profile | Mock source | Marker |
|---|---|---|---|---|
| `hermes-garry` | `Garry` | `/opt/hermes/mock-garry-profile` | `/opt/hermes/mockdata/garry` | `.mock-garry-imported` |
| `hermes-monica` | `Monica` | `/opt/hermes/mock-monica-profile` | `/opt/hermes/mockdata/monica` | `.mock-monica-imported` |
| `hermes-laurie` | `Laurie` | `/opt/hermes/mock-laurie-profile` | `/opt/hermes/mockdata/laurie` | `.mock-laurie-imported` |

The entrypoint seeds `SOUL.md`, `USER.md`, `MEMORY.md`, and `config.yaml` from the selected profile template only when the destination file does not already exist. It does not seed partner-specific `AGENTS.md`; repo-level operational guidance remains shared.

The entrypoint imports mock GBrain data from `${GBRAIN_MOCK_SOURCE}` when `${GBRAIN_MOCK_IMPORT_ON_START}` is `true`, then writes `${GBRAIN_HOME}/.gbrain/${GBRAIN_MOCK_IMPORT_MARKER}`. Logs include `${PARTNER_NAME}` for easier debugging.

## A2A Ports

`/message:send` behavior is unchanged by this spec.

Every container keeps the A2A sidecar internal port at `8080`. Compose maps distinct host ports to avoid conflicts:

- Garry: `localhost:8081` -> container `8080`
- Monica: `localhost:8082` -> container `8080`
- Laurie: `localhost:8083` -> container `8080`

If `A2A_ENABLED=true`, health checks are:

```bash
curl -s http://localhost:8081/healthz
curl -s http://localhost:8082/healthz
curl -s http://localhost:8083/healthz
```

## Demo Flow

Start all partner containers:

```bash
docker compose -f setup/docker/docker-compose.yml up -d --build
```

Open shells:

```bash
docker compose -f setup/docker/docker-compose.yml exec hermes-garry bash
docker compose -f setup/docker/docker-compose.yml exec hermes-monica bash
docker compose -f setup/docker/docker-compose.yml exec hermes-laurie bash
```

Check isolated brains:

```bash
docker compose -f setup/docker/docker-compose.yml exec hermes-garry gbrain search "Acme"
docker compose -f setup/docker/docker-compose.yml exec hermes-monica gbrain search "Acme"
docker compose -f setup/docker/docker-compose.yml exec hermes-laurie gbrain search "Acme"
```

Expected separation:

- Garry: sparse bridge/email context.
- Monica: GTM, ICP, buyer urgency, Nina/procurement risk.
- Laurie: product, retrieval, HIPAA, David/compliance risk.

## Test Plan

Build and start all services:

```bash
docker compose -f setup/docker/docker-compose.yml up -d --build
docker compose -f setup/docker/docker-compose.yml ps
```

Verify:

- Three distinct containers are running.
- Each container has the correct `/root/.hermes` profile seed.
- Each container imported only its own mock corpus into `/root/.gbrain`.
- Import logs include `PARTNER_NAME`.
- Container restarts preserve each partner brain independently.
- If A2A is enabled, `/healthz` responds on ports `8081`, `8082`, and `8083`.

Do not add or change `/message:send` behavior or tests as part of this spec.

## Assumptions

- The demo architecture is multiple running Docker containers, not one container with multiple GBrain folders.
- One shared image can contain all profile templates and mock corpora.
- Partner-specific import markers are preferred for easier debugging.
- Partner-specific identity belongs in `SOUL.md`, `USER.md`, and `MEMORY.md`; repo-level `AGENTS.md` remains shared.
- The old single-service `hermes` Compose workflow can be removed.
- Caller-side orchestration and `/message:send` changes are out of scope.
