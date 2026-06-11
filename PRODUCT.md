# Product

## Register

product

## Users

Two audiences. Primary: recruiters and senior engineers evaluating the author's AI engineering skill — they arrive cold, run 1–3 searches, skim the eval dashboard, and judge both the system and the taste behind it in under five minutes. Secondary: the author, using the admin console to ingest videos and the eval page to track retrieval quality.

## Product Purpose

A multimodal video RAG platform: search long-form video by what was said (transcript) and what was shown (frames), get a grounded answer with timestamped proof, and jump the player to the exact moment. The product exists to demonstrate production-grade AI engineering end to end — ingestion, retrieval, evaluation, deployment. Success: a visitor runs one search, sees the answer + proof choreography, and concludes "this person ships real systems."

## Brand Personality

Precise, grounded, quietly confident. The interface should feel like a well-run lab instrument: every motion conveys system state (searching, retrieving, grounding), nothing decorates for its own sake. One signature moment — the search → answer reveal — is allowed to perform; everything else stays fast and calm.

## Anti-references

- Template SaaS landing pages: gradient hero text, floating blobs, scroll-triggered fade-ins on every section.
- Crypto-dashboard maximalism: glowing borders, particle backgrounds, springy bounce on every card.
- Static portfolio screenshots: instant state pops with no feedback, loading states that just swap a text label.

## Design Principles

1. **Motion is state, not garnish.** Every animation maps to a real pipeline event: searching, evidence arriving, a proof becoming active.
2. **One hero moment.** The search → answer reveal carries the choreography budget; all other motion is 150–250 ms utility.
3. **Proof-first.** Timestamps, scores, and evidence are the product; motion should direct the eye to them, never away.
4. **Honest interface.** Never fake capability (no fake streaming, no artificial delays); show real progress, real refusals, real metrics.

## Accessibility & Inclusion

WCAG 2.1 AA targets. `prefers-reduced-motion` fully honored: all entrances collapse to crossfades or instant states. Keyboard-operable result cards and expanders (already in place) must stay operable through any motion changes.
