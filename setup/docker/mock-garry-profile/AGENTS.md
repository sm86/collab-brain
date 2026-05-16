# collab-brain Hermes Docker Guidance

This workspace runs multiple Hermes Agent containers with GBrain installed: one container per demo partner. Use the local repo and each partner's GBrain as the source of truth before giving company, founder, or meeting-prep answers.

## GBrain

- Default persistent brain inside each container: `/root/.gbrain` with `GBRAIN_HOME=/root`.
- Each partner container has its own Docker volume mounted at `/root`.
- Bundled mock data:
  - Garry: `/opt/hermes/mockdata/garry`
  - Monica: `/opt/hermes/mockdata/monica`
  - Laurie: `/opt/hermes/mockdata/laurie`
- Repo mock data is also available at `/workspace/setup/mockdata/` when using the default Compose bind mount.
- Import mock data manually with the matching partner path, for example:

```bash
GBRAIN_HOME=/root gbrain import /opt/hermes/mockdata/garry --no-embed
```

- Query before briefing:

```bash
gbrain search "Acme Maya founder context"
```

## Docker services

- Garry: `docker compose -f setup/docker/docker-compose.yml exec hermes-garry bash`
- Monica: `docker compose -f setup/docker/docker-compose.yml exec hermes-monica bash`
- Laurie: `docker compose -f setup/docker/docker-compose.yml exec hermes-laurie bash`

## Workflow

- For company briefings, retrieve notes first, then synthesize.
- For product/startup questions, force clarity on user urgency, wedge, distribution, technical risk, and next action.
- For code changes, inspect before editing, keep diffs narrow, and verify with the smallest meaningful test.
- For reviews, lead with bugs and risks rather than summaries.

## Boundaries

- Do not treat mock profiles as private partner knowledge.
- Do not overwrite user-edited Hermes profile files in `/root/.hermes`.
- Keep secrets in `setup/docker/env/hermes.env`, not in tracked profile files.
