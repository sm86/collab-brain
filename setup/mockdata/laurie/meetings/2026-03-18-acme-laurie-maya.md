---
type: meeting
title: Product walkthrough with Maya Patel (Acme) — Mar 18 (MOCK)
tags: [synthetic-demo, fictional, acme, product-walkthrough, clinical-notes, hipaa]
---

Product walkthrough with Maya Patel, CEO of Acme. ~60 minutes, video call. Maya led the walkthrough; David Kim (CTO) was not present. [Source: Mock demo corpus, 2026-03-18]

## Product detail covered

- Fine-tuned model on clinical notes. Base model is open-weights; fine-tuning corpus is a mix of public clinical-notes datasets and licensed hospital data. [Source: Meeting with Maya, 2026-03-18]
- Retrieval pipeline over hospital record corpora, with clinical-vocabulary-aware reranking. Maya described this as the architectural decision she is proudest of. [Source: Meeting with Maya, 2026-03-18]
- Near-term roadmap: extend the model to discharge summaries and operative notes. Reasonable scope. [Source: Meeting with Maya, 2026-03-18]
- Maya casually referenced 4 design partners closing during the GTM-status portion. I did not push on this — it was not the focus of the meeting. [Source: Meeting with Maya, 2026-03-18]

## Compliance / HIPAA discussion

- I asked how they were thinking about HIPAA, BAA structure, and de-identification of training data. [Source: Mock demo corpus, 2026-03-18]
- Maya's framing was "it's a checkbox, our hosting provider handles BAAs and we're de-identifying inputs." That is not enough at this product layer. The training-data side specifically is months of compliance work that she did not appear to have scoped. [Source: Meeting with Maya, 2026-03-18]
- I suggested she pull David into a follow-up specifically on compliance. (See Apr 2 meeting — David is taking this seriously, but it is not flowing back to Maya yet.) [Source: Mock demo corpus, 2026-03-18]

## My read

- Technically credible founder. Real depth on the model and pipeline architecture. [Source: Meeting with Maya, 2026-03-18]
- Underestimates HIPAA. Single biggest gap I saw in the walkthrough. [Source: Meeting with Maya, 2026-03-18]
- The CTO is doing more than the pitch implies. Worth meeting him alone. (Did that on Apr 2.) [Source: Mock demo corpus, 2026-03-18]

## Entities touched

- Maya Patel, Acme (CEO)
- David Kim, Acme (CTO, discussed)
- Acme (company)

---

## Timeline

- **2026-03-18** | Product walkthrough with Maya. Clinical-notes model, retrieval pipeline, HIPAA gap flagged. [Source: Mock demo corpus, 2026-03-18]
