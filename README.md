# collab-brain

## Hermes agent Docker container

Docker setup files are in `setup/docker/`:

- `setup/docker/Dockerfile` installs Hermes Agent from `https://github.com/NousResearch/hermes-agent` and GBrain from `https://github.com/garrytan/gbrain`
- `setup/docker/docker-compose.yml`
- `setup/docker/entrypoint.sh`
- `setup/docker/env/hermes.env` for local secrets/env vars
- `setup/docker/env/hermes.env.example` as a template
- `setup/docker/mock-garry-profile/` as a tracked starter Hermes profile

`setup/docker/env/hermes.env` is gitignored. Put your API keys there, for example:

```env
NOUS_API_KEY=...
OPENAI_API_KEY=...
OPENROUTER_API_KEY=...
HERMES_HOME=/root/.hermes
HERMES_BOOTSTRAP_PROFILE=true
HERMES_PROFILE_TEMPLATE_DIR=/opt/hermes/mock-garry-profile
HERMES_DEFAULT_PROVIDER=openrouter
HERMES_DEFAULT_MODEL=moonshotai/kimi-k2.6
GBRAIN_HOME=/root
GBRAIN_INIT_ON_START=true
GBRAIN_SEARCH_MODE=conservative
GBRAIN_IMPORT_MOCK_GARRY_ON_START=true
GBRAIN_MOCK_GARRY_SOURCE=/opt/hermes/mockdata/garry
HERMES_COMMAND=
```

## Build and start persistent container

```bash
docker compose -f setup/docker/docker-compose.yml up -d --build
```

If `HERMES_COMMAND` is blank, the container stays alive until you stop it.

## Mock Garry Hermes profile

The image bundles the sample profile from `setup/docker/mock-garry-profile/` at
`/opt/hermes/mock-garry-profile` and Garry's mock GBrain data at
`/opt/hermes/mockdata/garry`. On startup, the container copies profile files
only when the target file does not already exist:

- `SOUL.md` -> `/root/.hermes/SOUL.md`
- `USER.md` -> `/root/.hermes/memories/USER.md`
- `MEMORY.md` -> `/root/.hermes/memories/MEMORY.md`
- `config.yaml` -> `/root/.hermes/config.yaml`

This profile makes Hermes act as Garry's delegated Docker agent, not as Garry
directly. It uses public Garry/gstack/gbrain context as demo inspiration and
keeps secrets out of tracked files.

Project guidance for `/workspace` lives in the committed root `AGENTS.md`; the
entrypoint does not write files into the bind-mounted repo.

The bundled Garry mock data is imported into `/root/.gbrain` once on first
start. A marker file at `/root/.gbrain/.mock-garry-imported` prevents repeated
imports across container restarts.

Disable profile seeding with:

```env
HERMES_BOOTSTRAP_PROFILE=false
```

Disable mock data import with:

```env
GBRAIN_IMPORT_MOCK_GARRY_ON_START=false
```

## Login / open shell inside the container

```bash
docker compose -f setup/docker/docker-compose.yml exec hermes bash
```

Check Hermes is installed:

```bash
hermes doctor
```

## Use Hermes TUI

The default model is configured as OpenRouter `moonshotai/kimi-k2.6` / Kimi K2.6.

From your host machine:

```bash
docker compose -f setup/docker/docker-compose.yml exec hermes hermes
```

Or from inside the container shell:

```bash
hermes
```

First-time setup/configuration:

```bash
docker compose -f setup/docker/docker-compose.yml exec hermes hermes setup
```

Choose/change model:

```bash
docker compose -f setup/docker/docker-compose.yml exec hermes hermes model
```

## Use GBrain

GBrain is installed in the image using the required `git clone + bun link` path. On first container start, `gbrain init` creates a local PGLite brain at `/root/.gbrain` in the persistent Docker volume. Note: GBrain treats `GBRAIN_HOME` as the parent directory, so this setup uses `GBRAIN_HOME=/root`.

Check it:

```bash
docker compose -f setup/docker/docker-compose.yml exec hermes gbrain --version
docker compose -f setup/docker/docker-compose.yml exec hermes gbrain doctor --json
```

Import markdown files later with:

```bash
docker compose -f setup/docker/docker-compose.yml exec hermes gbrain import /workspace/path-to-markdown --no-embed
```

Re-import the Garry mock brain data manually with:

```bash
docker compose -f setup/docker/docker-compose.yml exec hermes bash -lc 'GBRAIN_HOME=/root gbrain import /opt/hermes/mockdata/garry --no-embed'
```

Vector embeddings require `OPENAI_API_KEY`; without it, keyword search still works.

## A2A company-info endpoint

The container can expose a small unauthenticated A2A-shaped HTTP endpoint for
brain-grounded company briefings:

- `GET /healthz`
- `GET /.well-known/agent-card.json`
- `POST /message:send`

Enable it in `setup/docker/env/hermes.env`:

```env
A2A_ENABLED=true
A2A_PORT=8080
A2A_BIND=127.0.0.1
A2A_PUBLIC_URL=http://localhost:8080
```

The default bind address is `127.0.0.1` inside the container. That is a secure
default, but it means the published host port is not reachable from your host
browser or curl. For host access, set:

```env
A2A_BIND=0.0.0.0
```

This endpoint has no auth and no TLS. Do not publish it to a network you do not
fully control.

Restart after changing the env file:

```bash
docker compose -f setup/docker/docker-compose.yml up -d --build
```

Smoke check from inside the container:

```bash
docker exec hermes-agent curl -s http://localhost:8080/healthz
docker exec hermes-agent curl -s http://localhost:8080/.well-known/agent-card.json
docker exec hermes-agent curl -s -X POST http://localhost:8080/message:send \
  -H 'Content-Type: application/json' \
  -d '{"message":{"role":"ROLE_USER","parts":[{"text":"Acme"}]}}'
```

`setup/docker/docker-compose.yml` publishes
`${A2A_PORT:-8080}:${A2A_PORT:-8080}`. If you change `A2A_PORT`, provide the
same value to Docker Compose interpolation, for example:

```bash
A2A_PORT=9090 docker compose -f setup/docker/docker-compose.yml up -d --build
```

## Run Hermes automatically instead of idle mode

Edit `setup/docker/env/hermes.env`:

```env
HERMES_COMMAND=hermes gateway start
```

Then restart:

```bash
docker compose -f setup/docker/docker-compose.yml up -d --build
```

## Stop manually

```bash
docker compose -f setup/docker/docker-compose.yml down
```

The service uses `restart: unless-stopped`, so Docker will restart it unless you explicitly stop it.
