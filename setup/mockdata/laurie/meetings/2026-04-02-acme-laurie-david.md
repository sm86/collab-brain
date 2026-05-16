---
type: meeting
title: Technical deep-dive with David Kim (Acme CTO) — Apr 2 (MOCK)
tags: [synthetic-demo, fictional, acme, technical-deep-dive, inference-stack, retrieval, hipaa]
---

Technical deep-dive with David Kim, CTO of Acme. ~75 minutes, video call. 1-on-1, no Maya present. I had asked for this specifically after the Mar 18 product walkthrough because I felt Maya was underselling him. [Source: Mock demo corpus, 2026-04-02]

## What David covered

- **Inference stack.** Custom on AWS. Not using a managed inference vendor — they built their own serving layer to control batching and prefix caching against the clinical-notes workload. Claims p95 latency ~300ms for their target query shape. Honest caveat: this is projected at expected production volume, not measured against real traffic yet. [Source: Meeting with David Kim, 2026-04-02]
- **Retrieval pipeline.** This is the moat layer, in his framing — not the model itself. Handles document structure (sections of a clinical note are not interchangeable), embedding caching, and a clinical-vocabulary-aware reranker. None of those three are off-the-shelf. [Source: Meeting with David Kim, 2026-04-02]
- **Why custom.** He walked through three off-the-shelf options they evaluated and rejected. The reasoning was specific and credible, not pattern-matched. [Source: Meeting with David Kim, 2026-04-02]

## HIPAA / compliance

- David is taking HIPAA more seriously than Maya was on Mar 18. He has a compliance scoping doc in draft covering BAA architecture, de-identification of training data, audit-log retention, and breach-notification flow. [Source: Meeting with David Kim, 2026-04-02]
- He has not shared the doc with the board yet. Asked me whether I thought he should — I said yes, and asked him to send me the doc. He said he would. (Not yet received as of this note.) [Source: Meeting with David Kim, 2026-04-02]
- This is a clear gap between David's view and Maya's. Worth flagging in any conversation with Maya about technical posture. [Source: Mock demo corpus, 2026-04-02]

## My read

- David is real. Solid systems work, honest about what is measured vs projected, taking compliance seriously. [Source: Meeting with David Kim, 2026-04-02]
- He is undersold in Acme's narrative. Maya should put him in more pitches. [Source: Meeting with David Kim, 2026-04-02]
- The Maya/David HIPAA gap is the most concrete artifact of "Maya undersells David" — he is doing the compliance scoping she said was a checkbox. [Source: Mock demo corpus, 2026-04-02]

## Entities touched

- David Kim, Acme (CTO)
- Maya Patel, Acme (CEO, discussed)
- Acme (company)

---

## Timeline

- **2026-04-02** | Technical deep-dive with David Kim. Custom inference stack + retrieval moat + HIPAA scoping in progress. [Source: Mock demo corpus, 2026-04-02]
