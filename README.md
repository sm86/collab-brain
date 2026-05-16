# collab-brain

## Hermes agent Docker container

Docker setup files are in `setup/docker/`:

- `setup/docker/Dockerfile` installs Hermes Agent from `https://github.com/NousResearch/hermes-agent` and GBrain from `https://github.com/garrytan/gbrain`
- `setup/docker/docker-compose.yml`
- `setup/docker/entrypoint.sh`
- `setup/docker/env/hermes.env` for local secrets/env vars
- `setup/docker/env/hermes.env.example` as a template

`setup/docker/env/hermes.env` is gitignored. Put your API keys there, for example:

```env
NOUS_API_KEY=...
OPENAI_API_KEY=...
OPENROUTER_API_KEY=...
HERMES_HOME=/root/.hermes
HERMES_DEFAULT_PROVIDER=openrouter
HERMES_DEFAULT_MODEL=moonshotai/kimi-k2.6
GBRAIN_HOME=/root
GBRAIN_INIT_ON_START=true
GBRAIN_SEARCH_MODE=conservative
HERMES_COMMAND=
```

## Build and start persistent container

```bash
docker compose -f setup/docker/docker-compose.yml up -d --build
```

If `HERMES_COMMAND` is blank, the container stays alive until you stop it.

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

Vector embeddings require `OPENAI_API_KEY`; without it, keyword search still works.

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
