# Small-Org AI Multiplayer Mode

## Goal

Run `collab-brain` for a 5-20 person org where every teammate has an AI agent
with private local memory, but agents can collaborate through shared skills and
policy-controlled brain requests.

This is the production wedge behind the hackathon demo: AI stops being a
single-player assistant and becomes a multiplayer team surface.

GBrain is the durable representation of a teammate's facts, taste, judgment,
and working context. The agent is the encapsulation over that brain. The router
is the collaboration and protection boundary between agents.

## Operating Model

Each teammate runs:

- Hermes Agent or another GStack-compatible agent runtime.
- A local GBrain storing their own notes, meetings, docs, CRM exports, and
  working memory.
- A small A2A sidecar exposing approved skills over HTTP.
- A local or team-managed MCP router that knows the org policy.

The org shares:

- A skill bundle with common workflows.
- Router policy that defines allowed collaboration paths.
- Router protections for PII redaction, prompt-injection filtering, and
  source-aware audit logs as the system moves beyond a trusted local demo.
- Team-level docs such as `AGENTS.md`, onboarding instructions, and demo-safe
  fixture data.
- Optional dashboard visibility for agent cards, access routes, and recent
  collaboration events.

The org does not need to start with one giant shared brain. The first useful
mode is multiple private brains that can answer narrow questions for each other.

## Shared Skills

Start with a small, explicit skill set:

| Skill | Purpose | Example caller |
|---|---|---|
| `company-info` | What does your brain know about this company? | founder meeting prep, sales, investing |
| `customer-context` | What happened with this customer or account? | support, success, sales |
| `hiring-context` | What do we know about this candidate or role? | recruiting, hiring managers |
| `deal-review` | What risks or commitments exist around this deal? | sales leadership, legal, finance |
| `follow-up-draft` | Draft a follow-up grounded in your notes. | anyone after a meeting |

Each skill should have:

- a narrow input shape
- a required `purpose`
- an output contract that cites or summarizes only retrieved brain context
- policy rules for who may call it

The current repo implements the first skill, `company-info`, as the proof point.

## Brain Collaboration Flow

```text
1. User asks their agent for help.
2. Agent searches its own GBrain first.
3. If more context is needed, agent calls the collab router.
4. Router checks caller, target, skill, and purpose.
5. Allowed peer agents query their own local GBrains.
6. Peer agents return narrow skill answers, not raw database access.
7. Caller agent merges the results into one answer for the user.
8. Dashboard records the route and outcome for observability.
```

This gives the org shared intelligence without pretending everyone should share
one memory boundary.

## Example Org Rollout

Day 1:

- Pick one workflow where missing context costs time, such as customer prep,
  founder diligence, or incident follow-up.
- Install GBrain for 3-5 teammates.
- Import markdown notes with `gbrain import`.
- Run the Docker setup from this repo as the reference environment.
- Configure one shared skill, usually `company-info` or `customer-context`.

Week 1:

- Add real team roles to router policy.
- Add a dashboard view for the team demo.
- Keep all brain data local to each teammate.
- Collect 5-10 examples where cross-brain context changed the answer.

Month 1:

- Add more skills only where repeated requests prove the need.
- Move sidecars behind authenticated endpoints.
- Add audit logging for calls, purpose, target, skill, status, and duration.
- Decide whether any data belongs in a true shared org brain, instead of a
  personal brain.

## Policy Shape

The useful default is role-based and skill-specific:

```yaml
policy:
  require_purpose: true
  deny_self_calls: true
  callers:
    sales:
      can_ask: [support, founder, product]
      skills: [customer-context, company-info, follow-up-draft]
    support:
      can_ask: [product]
      skills: [customer-context]
    founder:
      can_ask: [sales, support, product, recruiting]
      skills: [company-info, customer-context, hiring-context, deal-review]
```

Do not make every agent able to ask every other agent for every skill. The
product value is controlled collaboration, not a global memory leak.

## Demo Upgrade From This Repo

The current Acme demo maps directly to a small org:

- Garry becomes the exec or founder brain.
- Monica becomes GTM or sales.
- Laurie becomes product or engineering.
- `company-info` becomes the first shared skill.
- The access matrix becomes the org's collaboration policy.
- The dashboard becomes the multiplayer control plane.

Next feature additions should be:

- Add a second skill, `customer-context`, backed by the same A2A and router
  pattern.
- Add a `skills` section to the dashboard so judges can see that the system is
  skill-extensible.
- Add one more mock corpus representing a real small-org workflow, such as a
  customer escalation split across sales, support, and product.
- Add authenticated router-to-sidecar calls before running outside a local
  trusted network.

## Success Criteria

An org has AI multiplayer mode working when:

- a teammate's agent can answer from its own brain first
- the agent can request context from allowed peer brains
- peer agents answer through narrow skills
- private notes are not copied into one global database
- the final answer is materially better than any single brain's answer
- the org can inspect who asked what, why, and whether policy allowed it
