---
type: person
title: David Kim (MOCK)
aliases: [David, david@acme.ai, David Kim]
tags: [synthetic-demo, fictional, acme, cto, technical, healthcare]
---

CTO of Acme. Met once, Apr 2, deep technical review, no Maya present. He is the real technical engine of the company. [Source: Meeting with David Kim, 2026-04-02]

Specifics from the Apr 2 conversation:

- Built Acme's custom inference stack on AWS. P95 latency ~300ms for clinical-notes retrieval at production scale (their projection, not measured at real volume yet). [Source: Meeting with David Kim, 2026-04-02]
- Designed the retrieval pipeline as the moat layer — not the model itself. The pipeline handles document structure, embedding caching, and a clinical-vocabulary-aware reranker. None of that is off-the-shelf. [Source: Meeting with David Kim, 2026-04-02]
- Plain English: this is not just "ChatGPT for doctors"; the hard part is retrieving the right fragment from messy clinical records quickly, safely, and with an audit trail. [Source: Meeting with David Kim, 2026-04-02]
- Thinks about HIPAA more seriously than Maya does. Has a compliance scoping doc he is working on but has not shared with the board. Suggested I might want to read it; I asked him to send it. [Source: Meeting with David Kim, 2026-04-02]

He is undersold in Acme's pitch narrative. Maya is the public face and David is the technical depth — that asymmetry is fine for fundraising messaging but should not extend to how investors are introduced to the team. He should be in more pitches. [Source: Meeting with David Kim, 2026-04-02]

---

## Timeline

- **2026-04-02** | Technical deep-dive. Custom inference stack, retrieval moat, HIPAA scoping in progress. See [Meeting w/ David, Apr 2](../meetings/2026-04-02-acme-laurie-david.md). [Source: Mock demo corpus, 2026-04-02]
