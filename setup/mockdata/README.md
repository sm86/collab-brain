# Acme Mock Data

Synthetic GBrain fixture data for `docs/gbrain-acme-demo-workflow.md`.

This data is fake. Acme, Maya, David, Nina, and the notes here are invented for the collaborative-brain demo.

## Structure

Each top-level folder is a separate YC partner's brain, independently importable. The owner (Garry) plus two YC partners (Monica, Laurie) each hold private memory; the demo merges all three at query time.

- `garry/` — Garry Tan (YC President). Founder judgment, strategy, and category concerns.
- `monica/` — Monica Hall (YC partner, GTM lens). Sales, ICP, buyer urgency, go-to-market context.
- `laurie/` — Laurie Bream (YC partner, product/technical lens). Product, retrieval, technical depth, HIPAA, and compliance context.

Monica and Laurie are character names borrowed from HBO's *Silicon Valley* — used here as obviously-fictional YC partners so screenshots cannot be mistaken for real partner notes.

The files use the same GBrain markdown pattern as the upstream fixtures:

- YAML frontmatter for structured metadata.
- A compiled-truth section above `---`.
- A timeline/evidence section below `---`.

## Demo Shape

The corpus has 6 prior Acme touchpoints: 5 meetings and 1 sparse bridge-round email.

No single brain has the full picture:

- Garry only has Maya's bridge-round email.
- Monica has the GTM evolution and the hidden pipeline discrepancy.
- Laurie has the product, retrieval, CTO, and compliance read.

The merged briefing should surface two cross-brain demo payoffs:

- Maya is pitching "4 design partners closing," while Nina privately told Monica that 2 of the 4 are stalled in procurement.
- Maya tells Monica HIPAA is handled, while David separately tells Laurie he is still scoping months of compliance work.

## Import

Use `--no-embed` for deterministic local demo setup. GBrain treats `GBRAIN_HOME` as the parent directory for `.gbrain`, so each command below creates an isolated brain under a separate parent folder.

```bash
GBRAIN_HOME=/workspace/brains/garry gbrain init
GBRAIN_HOME=/workspace/brains/garry gbrain import /workspace/setup/mockdata/garry --no-embed

GBRAIN_HOME=/workspace/brains/monica gbrain init
GBRAIN_HOME=/workspace/brains/monica gbrain import /workspace/setup/mockdata/monica --no-embed

GBRAIN_HOME=/workspace/brains/laurie gbrain init
GBRAIN_HOME=/workspace/brains/laurie gbrain import /workspace/setup/mockdata/laurie --no-embed
```

## Test Queries

```bash
GBRAIN_HOME=/workspace/brains/garry gbrain search "Acme Maya category founder judgment"
GBRAIN_HOME=/workspace/brains/monica gbrain search "Acme ICP buyer urgency Nina"
GBRAIN_HOME=/workspace/brains/laurie gbrain search "Acme HIPAA compliance retrieval David"
```

Expected separation:

- Garry's brain has strategy and founder-judgment context.
- Monica's brain has sales, ICP, urgency, and buyer context.
- Laurie's brain has product, retrieval, HIPAA, and compliance context.
