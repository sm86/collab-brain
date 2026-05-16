# collab-brain Hermes Docker Guidance

This workspace runs a Hermes Agent container with GBrain installed. Use the local repo and GBrain as the source of truth before giving company, founder, or meeting-prep answers.

## GBrain

- Default persistent brain: `/root/.gbrain` with `GBRAIN_HOME=/root`.
- Bundled Garry mock data: `/opt/hermes/mockdata/garry`.
- Repo mock data is also available at `/workspace/setup/mockdata/` when using the default Compose bind mount.
- Import Garry mock data with:

```bash
GBRAIN_HOME=/root gbrain import /opt/hermes/mockdata/garry --no-embed
```

- Query before briefing:

```bash
gbrain search "Acme Maya founder context"
```

## Workflow

- For company briefings, retrieve notes first, then synthesize.
- For product/startup questions, force clarity on user urgency, wedge, distribution, technical risk, and next action.
- For code changes, inspect before editing, keep diffs narrow, and verify with the smallest meaningful test.
- For reviews, lead with bugs and risks rather than summaries.

## Boundaries

- Do not treat the mock profile as private Garry knowledge.
- Do not overwrite user-edited Hermes profile files in `/root/.hermes`.
- Keep secrets in `setup/docker/env/hermes.env`, not in tracked profile files.
