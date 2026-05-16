# collab-brain

## Hermes agent Docker containers

Docker setup files are in `setup/docker/`:

- `setup/docker/Dockerfile` installs Hermes Agent from `https://github.com/NousResearch/hermes-agent` and GBrain from `https://github.com/garrytan/gbrain`
- `setup/docker/docker-compose.yml`
- `setup/docker/entrypoint.sh`
- `setup/docker/env/hermes.env` for local secrets/env vars
- `setup/docker/env/hermes.env.example` as a template
- `setup/docker/mock-*-profile/` as tracked starter Hermes profiles

`setup/docker/env/hermes.env` is gitignored. Put your API keys there, for example:

```env
NOUS_API_KEY=...
OPENAI_API_KEY=...
OPENROUTER_API_KEY=...
HERMES_HOME=/root/.hermes
HERMES_BOOTSTRAP_PROFILE=true
HERMES_DEFAULT_PROVIDER=openrouter
HERMES_DEFAULT_MODEL=moonshotai/kimi-k2.6
GBRAIN_HOME=/root
GBRAIN_INIT_ON_START=true
GBRAIN_SEARCH_MODE=conservative
GBRAIN_MOCK_IMPORT_ON_START=true
HERMES_COMMAND=
```

Partner-specific profile paths and mock data sources live in
`setup/docker/docker-compose.yml`, not in the shared env file.

## Build and start persistent containers

```bash
docker compose -f setup/docker/docker-compose.yml up -d --build
```

If `HERMES_COMMAND` is blank, each container stays alive until you stop it.

## Mock partner Hermes profiles

The image bundles one profile and one mock GBrain corpus per demo partner:

| Service | Container | Profile | Mock data |
|---|---|---|---|
| `hermes-garry` | `hermes-garry-agent` | `/opt/hermes/mock-garry-profile` | `/opt/hermes/mockdata/garry` |
| `hermes-monica` | `hermes-monica-agent` | `/opt/hermes/mock-monica-profile` | `/opt/hermes/mockdata/monica` |
| `hermes-laurie` | `hermes-laurie-agent` | `/opt/hermes/mock-laurie-profile` | `/opt/hermes/mockdata/laurie` |

On startup, each container copies profile files only when the target file does
not already exist:

- `SOUL.md` -> `/root/.hermes/SOUL.md`
- `USER.md` -> `/root/.hermes/memories/USER.md`
- `MEMORY.md` -> `/root/.hermes/memories/MEMORY.md`
- `config.yaml` -> `/root/.hermes/config.yaml`

These profiles make Hermes act as delegated demo partner agents and keep
secrets out of tracked files.

Project guidance for `/workspace` lives in the committed root `AGENTS.md`; the
entrypoint does not write files into the bind-mounted repo.

Each container has its own named Docker volume mounted at `/root`, so each
partner has isolated `/root/.hermes` and `/root/.gbrain` state. The selected
mock corpus is imported into that partner's `/root/.gbrain` once on first start.
A partner-specific marker file prevents repeated imports across restarts.

Disable profile seeding with:

```env
HERMES_BOOTSTRAP_PROFILE=false
```

Disable mock data import with:

```env
GBRAIN_MOCK_IMPORT_ON_START=false
```

## Login / open shell inside a container

```bash
docker compose -f setup/docker/docker-compose.yml exec hermes-garry bash
docker compose -f setup/docker/docker-compose.yml exec hermes-monica bash
docker compose -f setup/docker/docker-compose.yml exec hermes-laurie bash
```

Check Hermes is installed:

```bash
hermes doctor
```

## Use Hermes TUI

The default model is configured as OpenRouter `moonshotai/kimi-k2.6` / Kimi K2.6.

From your host machine:

```bash
docker compose -f setup/docker/docker-compose.yml exec hermes-garry hermes
```

Or from inside the container shell:

```bash
hermes
```

First-time setup/configuration:

```bash
docker compose -f setup/docker/docker-compose.yml exec hermes-garry hermes setup
```

Choose/change model:

```bash
docker compose -f setup/docker/docker-compose.yml exec hermes-garry hermes model
```

## Use GBrain

GBrain is installed in the image using the required `git clone + bun link` path. On first container start, `gbrain init` creates a local PGLite brain at `/root/.gbrain` in that partner's persistent Docker volume. Note: GBrain treats `GBRAIN_HOME` as the parent directory, so this setup uses `GBRAIN_HOME=/root`.

Check it:

```bash
docker compose -f setup/docker/docker-compose.yml exec hermes-garry gbrain --version
docker compose -f setup/docker/docker-compose.yml exec hermes-garry gbrain doctor --json
```

Import markdown files later with:

```bash
docker compose -f setup/docker/docker-compose.yml exec hermes-garry gbrain import /workspace/path-to-markdown --no-embed
```

Search each isolated demo brain:

```bash
docker compose -f setup/docker/docker-compose.yml exec hermes-garry gbrain search "Acme"
docker compose -f setup/docker/docker-compose.yml exec hermes-monica gbrain search "Acme"
docker compose -f setup/docker/docker-compose.yml exec hermes-laurie gbrain search "Acme"
```

Vector embeddings require `OPENAI_API_KEY`; without it, keyword search still works.

## A2A company-info endpoint

Each container can expose a small unauthenticated A2A-shaped HTTP endpoint for
brain-grounded company briefings:

- `GET /healthz`
- `GET /.well-known/agent-card.json`
- `POST /message:send`

Enable it in `setup/docker/env/hermes.env`:

```env
A2A_ENABLED=true
A2A_PORT=8080
A2A_BIND=0.0.0.0
```

Every sidecar binds internal port `8080`. Compose maps the partner services to
host ports `8081`, `8082`, and `8083`. Partner-specific `A2A_PUBLIC_URL` values
live in `setup/docker/docker-compose.yml`.

This endpoint has no auth and no TLS. Do not publish it to a network you do not
fully control.

Restart after changing the env file:

```bash
docker compose -f setup/docker/docker-compose.yml up -d --build
```

Smoke check from inside the container:

```bash
docker exec hermes-garry-agent curl -s http://localhost:8080/healthz
docker exec hermes-monica-agent curl -s http://localhost:8080/healthz
docker exec hermes-laurie-agent curl -s http://localhost:8080/healthz
```

Smoke check from the host when `A2A_ENABLED=true`:

```bash
curl -s http://localhost:8081/healthz
curl -s http://localhost:8082/healthz
curl -s http://localhost:8083/healthz
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

Each service uses `restart: unless-stopped`, so Docker will restart it unless you explicitly stop it.
