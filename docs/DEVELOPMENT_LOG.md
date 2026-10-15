# Development notes

## v0.14.0

The v0.13.0 baseline had 104 passing tests. New adversarial fixtures reproduced actor/object/negation authorization mistakes, named thoughts, passive choices, quoted-dialogue changes, unsafe journal/state claims, and a missing message-ID crash when retrying a later GM turn.

The engine now separates authoritative turn input from GM narration, checks accepted text before its transaction, and shares screened history between retrieval and generation. Saved originals are preserved; the change adds no schema migration. This remains bounded text/grammar validation, not a proof of arbitrary model semantics.

Retrieval keeps relevant creator canon ahead of public references, preserves provenance and complete-sentence excerpts, and emphasizes the active scene. Browser requests capture their campaign/view; failures retain drafts and feedback, and stale responses cannot replace another adventure. Ollama attempts share a retry budget and emit opt-in metadata diagnostics without story text.

The standard-library architecture and existing installable filenames are retained for updater compatibility. New regression modules use approved `tests/test_*.py` paths; documentation stays outside release ZIPs. GitHub Actions now explicitly installs Node 22 and checks JavaScript before running the complete suite.

Validation includes Python unit/API tests, executable Node request-state checks, a scripted local Ollama protocol, complete database snapshots on failed generations/retries, and release validation with prior updater implementations. These do not verify real Qwen output, the user's Windows installation, GPU performance, or perceptual audio quality. README includes a local acceptance checklist.

Next engineering priorities: observe real model failure cases and timing metadata, strengthen semantic ownership without blocking valid NPC narration, and introduce explicit scenario progress only with non-destructive compatibility tests. Keep player-authored canon and historical outcomes distinct from future opportunities.
