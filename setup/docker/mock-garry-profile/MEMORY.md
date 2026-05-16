# Hermes Mock Garry Agent Memory

This Hermes container is part of the `collab-brain` demo. It combines Hermes Agent with GBrain so a Docker-hosted agent can answer from persistent local knowledge.

## Demo Goal

The main demo is a collaborative company briefing flow. Multiple partner-style brains hold partial context about the same company. A peer agent can ask this Hermes instance what its local brain knows, and the answer should be grounded in the local notes.

## Local Brain Behavior

- GBrain is installed in the Docker image from `https://github.com/garrytan/gbrain`.
- In this container, `GBRAIN_HOME=/root` stores the default persistent brain under `/root/.gbrain`.
- The image contains importable Garry mock data under `/opt/hermes/mockdata/garry`.
- The repository also contains importable mock data under `/workspace/setup/mockdata/` when the default Compose bind mount is active.

## Briefing Defaults

When asked about a company or founder:

- Search or query GBrain before answering when available.
- Answer only from retrieved notes and explicit context.
- If notes are sparse, say they are sparse.
- Include dates, people, company names, and unresolved risks when known.
- Keep the output useful for a meeting prep workflow.
