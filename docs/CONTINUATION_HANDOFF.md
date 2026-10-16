# Storyforge v0.15.0 — release continuation handoff

Updated: 2026-10-16. Implementation and automated verification are complete locally. The user approved pushing this update; final v0.15.0 release verification and live-model acceptance remain pending.

## Authorization and scheduling

The user now says **"push this update please"**. This explicitly authorizes pushing the current GM rework and publishing **v0.15.0** through the existing main-branch GitHub release workflow, superseding the earlier local-only freeze for this update. Complete the final version-sensitive checks, package validation and publication verification without requesting duplicate approval. This is specific approval for the current update; it does not grant blanket permission for unrelated future releases.

The user requested an automatic continuation of this exact Cloud conversation at 11:10 PM UK time. No scheduling/automation tool is available in this session. **No scheduled continuation was created.** A shell timer, cron entry or reminder is not a substitute for resuming this conversation and must not be described as one.

## Goal

Investigate official public Fables behavior and independently improve Storyforge, prioritizing GM behavior and continuity. The user wants local-only inference and is willing to replace Qwen if measured testing supports it. Do not copy proprietary prompts, scripts, assets or private campaign material.

## Starting point and current work

The last confirmed published release is v0.14.0, commit c537c8c99323ba9de267cc4e463917ac5c81178a. The current GM rework is being prepared as v0.15.0 under the approval above; retain all existing changes. This record does not yet confirm a release commit, successful workflow or published asset.

Changes currently in engine.py, server.py, static/app.js and tests:

- Budgeted GM context (16,000 UTF-8 bytes with repair reserve), complete serialized objects, full required premise/ability constraints, newest journal and ending scene handoff, shared lore-preview selection.
- Typed Ollama JSON Schema, Qwen3:8b non-thinking sampling baseline from official Qwen docs, incomplete completion rejection.
- Evidence-bound production state changes; optional NPC/event/pending-thread working memory with checkpoint-compatible storage and player removal controls.
- Disposable synthetic model comparison CLI: `py server.py --evaluate-model qwen3:8b --repeat 1 --report data/model-check-qwen-v015.json`. No model download/switch, no access to personal saves, reports refuse overwrite, and automatic guard passes require human story review. Essential commands also appear in README because docs are excluded from release ZIPs.

New tests: test_gm_context.py, test_gm_schema.py, test_scene_memory.py, test_gm_evaluation.py, test_gm_review_regressions.py and test_scene_memory_ui.py. Existing test_gm_http.py fixtures were updated to the evidence/schema protocol and now exercise memory removal through HTTP.

## Evidence and completed verification

The original representative request was 20,393 characters and a valid populated request reached 39,300 against an 8,192-token configured context. Serialized JSON and recent scene endings were cut; requested spell limits could disappear. The new representative request measured about 13,003 characters and preserved those missing facts. UTF-8-byte sizing remains an estimate, not exact model tokenization.

The final full suite passes **231 tests on Python 3.13.5 and Python 3.12.14**. Node v24.19.0 executes the browser-control tests; JavaScript syntax and git diff whitespace checks pass. Tests include scripted local HTTP/Ollama requests and disposable SQLite campaigns, not live model inference. No personal campaign data was opened or modified.

Independent review found and reproduced six issues; their regression cases now pass: optional notes starving the latest handoff, oversized repair requests, removed memories returning through rewind checkpoints, whitespace bypassing the PC/NPC boundary, unrelated evidence resolving a thread, and policy wording allowing header-only state evidence. Thirteen review cases cover fixes and valid controls. Nine browser tests cover memory escaping, exact payloads, stale responses, cancellation, duplicates and failures. HTTP tests also confirm removed NPC facts do not reappear after a later retry.

Optional evaluator metadata records selected-model version/digest/quantization/context/capabilities, omitting templates, system prompts and other installed model names. Bounded loopback requests fail independently of the gameplay evaluation. The focused evaluator suite passes 19 cases.

The previous public Fables access blocker is resolved. Official help/blog/patch notes were researched and documented in [FABLES_RESEARCH.md](FABLES_RESEARCH.md). The play site exposes only an unauthenticated shell; no signed-in gameplay quality or latency was observed. [LOCAL_GM_EVALUATION.md](LOCAL_GM_EVALUATION.md) records official Ollama/Qwen sources, implementation limits and exact PowerShell evaluation commands.

The final v0.15.0 ZIP validates with the current updater and historical v0.14.0/v0.13.0/v0.12.1 updaters. All 37 manifest files match the workspace. It contains only approved application/test paths, excluding docs, AGENTS.md and private data. No local installation was performed. The earlier same-version v0.14.0 review artifact must not be published as this release.

## Release completion and local acceptance

1. Version-sensitive tests and final package validation pass. Use the approved main-branch workflow, then verify its success and the actual release ZIP before recording publication. The current update already has push/release approval.
2. Ask the user to install through the updater after publication and run the disposable evaluation on their local Ollama installation, following [LOCAL_GM_EVALUATION.md](LOCAL_GM_EVALUATION.md) or README. This cloud machine has no running Ollama: one real request failed to connect and nine scenarios were explicitly unrun. Automated acceptance does not prove Qwen story quality, semantic player agency, lore accuracy or responsiveness. No replacement model has been selected.
3. Review accepted and rejected attempts, costs/limits, Hogwarts continuity and retry preservation. Check existing Windows campaigns, artwork and voice/music on the user's machine. The new memory feature does not fabricate or backfill old campaign memories. Do not claim the user's PC installed a release without local confirmation.

The approved release allowlist accepts existing engine/server/static files and tests/test_*.py; new runtime module filenames or tools/evaluation files would break older updaters. Keep implementation within existing approved files.
