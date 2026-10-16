# Development notes

## v0.15.0 — 2026-10-16

The user explicitly approved this update with "push this update please". The earlier local-only freeze was superseded for the v0.15.0 GM rework. [v0.15.0](https://github.com/Xeminas1/Storyforge/releases/tag/v0.15.0) was published through the existing main-branch workflow at commit 1e664e61943bc744d2a29d21e75c78f8101bd7a4; [run 38860433940](https://github.com/Xeminas1/Storyforge/actions/runs/38860433940) succeeded. Approval was specific to this update. No automatic Cloud continuation was created: this session has no scheduling capability. Current state and verification are recorded in [CONTINUATION_HANDOFF.md](CONTINUATION_HANDOFF.md).

Official public Fables documentation is now reachable. [FABLES_RESEARCH.md](FABLES_RESEARCH.md) distinguishes documented product architecture from observed gameplay and engineering inference. Its central lesson is targeted context research, narration and state handling, rather than an ever-longer narrator prompt. No signed-in play or proprietary implementation was inspected. The local adaptation uses deterministic retrieval and validation rather than adding a dozen serial model calls.

The old context path could send 20,393 characters for a representative campaign and 39,300 for a populated valid campaign, slice serialized objects and lose the latest scene ending or requested spell restrictions. The new composer shares a 16,000 UTF-8-byte budget across instructions, creator premise, character constraints, complete requested abilities, selected lore, recent state/history and repair reserve. It prioritizes the latest handoff before optional notes, measures complete objects, and fails before inference when essential facts cannot fit. Bytes remain an estimate, not exact tokenizer accounting.

Ollama receives a typed response schema, while the engine validates the same nested structure independently. The known qwen3:8b tag uses Qwen's documented non-thinking sampling baseline. Truncated completions are rejected. Production state changes and optional scene/NPC/event/thread memory need exact visible prose evidence; a scene header alone cannot justify a location change. The player is excluded from GM-controlled NPC memory. Resolving a pending thread requires a visible statement identifying that exact thread.

Memory is additive state JSON using existing checkpoints. Journal and Relationships controls let the player remove incorrect notes. Exact selected facts are also removed from both sides of that campaign's rewind checkpoints, so a later retry cannot resurrect them. Unrelated categories, campaigns and original story messages remain intact. Corrective requests remain within the same byte ceiling even when validation produces many findings.

A disposable ten-scenario local evaluation CLI records synthetic prompts, accepted/rejected drafts, timing and preservation checks, with explicit pending human review. Optional model metadata is limited to version/identity/capability fields and never prevents gameplay evaluation. [LOCAL_GM_EVALUATION.md](LOCAL_GM_EVALUATION.md) contains commands and model-comparison guidance. No model was downloaded, switched or proven superior. This cloud environment has no running Ollama, so live Qwen behavior and Windows/GPU performance remain unverified.

Validation: 231 tests pass on both Python 3.13.5 and 3.12.14 after the v0.15.0 version bump, including executable Node request/memory UI checks and actual localhost HTTP protocol tests. JavaScript syntax and diff checks pass. The actual published ZIP passes the v0.14.0 updater's normal verified-download path and historical v0.13.0/v0.12.1 validators. All 37 manifest files match the tested workspace; private data and repository-only documentation are excluded. Its 188,026 bytes match GitHub's SHA-256 7be1207dfd67a068bad77a97f09196972f6fd9f53e965d9821459304d81775a0. No local installation was performed.

## v0.14.0

The v0.13.0 baseline had 104 passing tests. New adversarial fixtures reproduced actor/object/negation authorization mistakes, named thoughts, passive choices, quoted-dialogue changes, unsafe journal/state claims, and a missing message-ID crash when retrying a later GM turn.

The engine now separates authoritative turn input from GM narration, checks accepted text before its transaction, and shares screened history between retrieval and generation. Saved originals are preserved; the change adds no schema migration. This remains bounded text/grammar validation, not a proof of arbitrary model semantics.

Retrieval keeps relevant creator canon ahead of public references, preserves provenance and complete-sentence excerpts, and emphasizes the active scene. Browser requests capture their campaign/view; failures retain drafts and feedback, and stale responses cannot replace another adventure. Ollama attempts share a retry budget and emit opt-in metadata diagnostics without story text.

The standard-library architecture and existing installable filenames are retained for updater compatibility. New regression modules use approved `tests/test_*.py` paths; documentation stays outside release ZIPs. GitHub Actions now explicitly installs Node 22 and checks JavaScript before running the complete suite.

Validation includes Python unit/API tests, executable Node request-state checks, a scripted local Ollama protocol, complete database snapshots on failed generations/retries, and release validation with prior updater implementations. These do not verify real Qwen output, the user's Windows installation, GPU performance, or perceptual audio quality. README includes a local acceptance checklist.

Next engineering priorities: observe real model failure cases and timing metadata, strengthen semantic ownership without blocking valid NPC narration, and introduce explicit scenario progress only with non-destructive compatibility tests. Keep player-authored canon and historical outcomes distinct from future opportunities.
