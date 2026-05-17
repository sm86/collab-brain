# GStack Hackathon Submission

## One-Liner

`collab-brain` is a multiplayer memory layer for AI agents: your AI can ask
your teammate's AI for a narrow, policy-gated answer without merging everyone's
private notes into one shared brain.

## Novel Idea

GBrain captures a person's facts, taste, judgment, and working context. An
agent is the encapsulation over that brain. The missing layer is multiplayer:
agents should collaborate across brains with consent, purpose, and policy.

The router is that layer. It will become the protection surface for PII
redaction, prompt-injection filtering, audit logs, and skill-scoped answers.
Today it already enforces caller, target, skill, and required `purpose`.

## Demo

Garry is meeting Maya from Acme in 30 minutes.

- Garry has one sparse bridge-round email.
- Monica knows 2 of 4 "closing" design partners are stalled in procurement.
- Laurie knows HIPAA is not actually handled and the undersold CTO is the real
  systems asset.

One peer-brain request turns three partial memories into one diligence-ready
meeting brief.

## Run

```bash
cp setup/docker/env/hermes.env.example setup/docker/env/hermes.env
# add a model provider key, for example OPENROUTER_API_KEY
docker compose -f setup/docker/docker-compose.yml up -d --build
```

Then open `http://localhost:8095` and click **Run demo request**.

For the full live MCP request and expected output, see the root README and
`docs/gbrain-acme-demo-workflow.md`.

## What Is Real

- separate persistent GBrain stores per partner container
- real `gbrain import` from committed markdown fixture data
- A2A-shaped sidecars backed by local GBrain retrieval
- MCP router with policy-gated cross-brain calls
- dashboard showing agent cards, policy, events, and source notes
- Garry-only `/collab` operator command MVP for Telegram company brain access

## What Is Synthetic

Acme, Maya, David, Nina, Monica, and Laurie are public demo constructs. The
point is the collaboration pattern, not private YC data.

The dashboard's **Run demo request** button creates synthetic timeline events
for stage clarity. The README also includes the real MCP request.

## Small-Org Path

Run this for a 5-20 person org:

- one GBrain per teammate
- shared skills such as `company-info`, `customer-context`, and `deal-review`
- router policy for who can ask which agent for which skill
- future router protections for PII redaction, prompt-injection defense, and
  audit logs

See `docs/small-org-ai-multiplayer.md`.
