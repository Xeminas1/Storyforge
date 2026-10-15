# Storyforge — engineering handover to Codex
**Prepared:** 2026-10-15  
**Repository:** https://github.com/Xeminas1/Storyforge  
**Baseline:** main at commit `4cc967c78e2ed9171a7f8794f155bab21c737f8f` before this documentation-only handover; latest published app release **v0.13.0** (https://github.com/Xeminas1/Storyforge/releases/tag/v0.13.0). The GitHub Actions release run at this baseline succeeded. No evidence here that the user's Windows installation has already advanced to v0.13.0.

## Your role
Take over implementation, debugging, regression testing and GitHub release engineering for Storyforge. Read `AGENTS.md` first and inspect current `README.md` plus sources/tests. Work on the repository, propose concrete, testable fixes, make commits and verify releases; tell the user when their local Windows app must install the release. Do not merely reiterate suggestions. Keep claims grounded in test results and actual user observations.

## What the user is building
A locally hosted, story-first, free-form fantasy RPG, influenced by the experience of play.fables.gg / Friends & Fables but independently implemented. The user chooses or imports community-created worlds; can research and import world reference lore; creates and reuses custom characters; types unrestricted actions; and receives a reactive AI Game Master's prose, spoken aloud. Combat is subordinate to social scenes and fiction: abilities are described and respected, rather than restricting the player to a fixed command list. A Fables-like dark, artwork-rich browser layout is desired, but do not copy protected code or assets.

The recurrent test character is **Xeminas**, a High Elf Dark Monarch (godlike necromancer with platinum hair, purple eyes, regal dark robes and living shadows). The user must be able to choose what Xeminas says, does, believes or casts. The GM must **never** supply unrequested PC dialogue, deliberate motions, thoughts or decisions, whether in second person, first person, by name, or in structured campaign history.

A frequent test campaign is **Harry Potter: Wizarding World**. The user's World Atlas premise says: "Attend Hogwarts, choose your house, attend class, learn spells, and fight monsters and evil wizards Start at Hogsmeade Station for the introduction and being able to sit through the Sorting Hat selection." The GM should distinguish arrival at the station from the later Sorting Ceremony at Hogwarts, let it play out, and not assume the character has already chosen a house. The word "Fantastic Beasts" was also requested as associated setting material.

## Current stack and user's environment (last reported)
- Windows desktop, running Storyforge from `C:\Storyforge` at `http://127.0.0.1:8787`. Python server; vanilla JS/CSS browser frontend; SQLite under `data/storyforge.db`.
- Local **Ollama**, most often model `qwen3:8b`, API default `127.0.0.1:11434`. Qwen's small local model can struggle with long prompts, JSON, player agency and repeated passages. Do not assume a stronger model has been installed.
- Optional **Kokoro** neural speech in Docker at `127.0.0.1:7860`; pause/stop, speech volume and automatic playback; narrator strips literal asterisks/emphasis markup. The user wants low-latency speech.
- Optional **ComfyUI** at `127.0.0.1:8188`, RTX 5080 with 16GB VRAM, roughly 64GB RAM. Desktop originally failed to keep its backend reachable. Launching ComfyUI's Python backend manually succeeded. SDXL checkpoint `sd_xl_base_1.0.safetensors` was downloaded into ComfyUI Desktop shared checkpoint directory; a copy was used for the manually launched backend. Scene art subsequently visibly generated. Do not assume ComfyUI is persistently running after a reboot.
- Browser Brave, local character portrait and scene art persisted outside install files.
- Updater UI allows automatic releases when idle and an explicit **Check & install latest release now** button. Installing a release is separate from publishing it to GitHub. No credentials, secrets or the user's local saves are present in the repository.

## Features delivered through v0.13.0
1. **Worlds / campaigns:** local world library, sample world, import from creator-provided files/ZIPs, campaign persistence, recent campaigns and Fables-inspired home/navigation. World lore is stored as sections plus a creator description.
2. **Characters:** independent reusable character library and selectable character on campaign creation, portrait upload or locally generated portrait, character details and editable ability/spellbook with effects, limits, costs, appearance and optional images.
3. **Story UI:** central messages with GM header `[Location - Parent Area - Time of Day]`, translucent cards over cached scene-image backgrounds, right Scene/Character/World panel, larger artwork and full-image view, location image generation/reuse/locking.
4. **Voice and music:** Kokoro TTS adapter (and browser TTS fallback), segmented narration and speech controls. Optional browser Web Audio ambient instrument tones with Auto/Exploration/Tavern/Mystery/Danger/Peace moods; separate volume and ducking when speech plays. This is synthetic ambience, not licensed soundtrack streaming.
5. **Message controls:** delete GM/player messages; retry GM replies or resend player actions with optional natural-language feedback; correction history saved locally and offered as context to the GM. Rewind uses per-turn state snapshots on newer messages, rolling back future dependent turns. Older campaigns may have no checkpoints and must show limitations. Feedback does **not** train Qwen weights.
6. **GM safety and continuity:** response JSON parser, retries for invalid responses, heuristic player-agency and repetition validation, and validation of `journal_entry` / Story Developments. Suspicious older notes can be manually removed. New local Ollama call is limited to at most two attempts with ~70-second per-attempt timeout; source may have evolved.
7. **Lore discovery:** a manual preview/import workflow for concise public Wikipedia article intros with attribution. Search presets for Harry Potter / Wizarding World / Fantastic Beasts. Not exhaustive canon, not a scraper of Fables or a commercial franchise database. Lore discovery resides in `engine.py` because of updater path restrictions.
8. **v0.13.0 lore fix:** creator's world description is always included in the GM context, contextual lore retrieval is more focused, and the UI exposes **What lore does the GM see?**. Specific Hogwarts Sorting scenario guidance accompanies matching creator descriptions. This was verified with mock/unit/local API tests, NOT a guarantee that user's installed Qwen run always understands canon.

## Unresolved issues: tackle these first
### P0: Agency violations still happened in real play
The user typed only "i smile knowing that voldemort seeks me, i continue on". Qwen nonetheless narrated **"I raise my hand"** and attributed unchosen beliefs to Xeminas. A saved Story Development had **"but I made it clear I am the Dark Monarch"**, although the player never said that. Subsequent v0.12.1 code expanded heuristic checks for first/third person and journal updates; real-world guarantees are unverified. Implement a more reliable explicit separation of NPC/world events from user-authorised PC actions and state changes. Build adversarial tests for first person, named PC, indirect speech, invented thoughts, and state/journal updates. Prefer a fail-safe response that asks for a corrected generation while preserving the turn to storing false canon. Avoid overly aggressive false positives: actual user-given actions are permitted and NPC speech in first person remains permissible.

### P0: World premises and lore are inconsistently understood
Before v0.13.0 the premise was not always injected into the GM prompt. Qwen repeatedly treated the Hogwarts Sorting Hat as an immediate whisper/prophecy and replayed Hogwarts Express arrivals. Validate against a user-supplied world containing the quoted opening premise and a selection of canonical setting facts. Verify what **is actually sent** to Ollama, not just what a preview UI displays; ensure retrieved passages are grounded, concise, correctly prioritised, and not mistaken for already-completed story milestones. Keep player choice of house intact. Consider a structured scenario/milestone record rather than brittle special-cased franchise strings.

### P1: Inference responsiveness and failure handling
The user saw "The AI returned an empty narration" and **Ollama HTTP 500: prediction aborted, token repeat limit reached**; Retry / Feedback sometimes took minutes. v0.12.0 reduced attempts and timeouts and added repetition detection. Gather timing/error diagnostics, context length and token usage (without logging private data indiscriminately). On failure, return an actionable status quickly and do not lose or consume the user's action or rewrite/deletion target.

### P1: Repeated scenes and drift
The GM repeated train arrival text after the player only looked at a figure. Regression tests should cover story progression, replay, retrying earlier turns, and avoiding accidental recaps while still allowing callbacks to important NPCs/places. Distinguish text duplication from necessary canon continuity.

### P1: On-device usability verification
Check Kokoro first-sentence latency, narration pause/stop and speech ducking, ambient sound quality, and ComfyUI connectivity on Windows. Unit tests cannot establish perceptual audio quality. Evaluate whether optional settings should be enhanced without subscriptions.

### P2: Richer optional lore and world state
User wants comprehensive character/location/creature/history imports from relevant public/creator-authorised sources, sources and attribution, and consistent NPC/relationship/world memory. Wikipedia intros are incomplete. Research legally usable source integrations; allow users to bring their own lore packs. Do not suggest there is a one-click guarantee of complete copyrighted universe lore or scrape restricted/proprietary content.

## Code map
- `engine.py`: `open_db`, `make_world`, `new_campaign`, `select_lore_entries`, `world_scenario_context`, `preview_campaign_lore`, `GAME_MASTER_POLICY`, `ollama_chat`, `player_agency_violations`, `gm_repetition_violations`, `_generate_turn`, `play_turn`, `retry_message`, `delete_message`, `apply_patch`, `remove_journal_entry`, image generation and public Wikipedia query functions.
- `server.py`: local HTTP API; default `127.0.0.1:8787`. Health, worlds, characters, lore, campaigns, messages, corrections, artworks, updater and TTS endpoints.
- `static/app.js`, `static/index.html`, `static/styles.css`: client-side app, modal/editor, image panels, voice, music and update controls.
- `narration.py`: fixed-localhost Kokoro adapter.
- `updater.py`: `VERSION`, `installable()` allowlist, package validation, release poll and restart/rollback.
- `tools/build_release.py` plus `.github/workflows/release.yml`: ZIP build and GitHub Actions publication.
- `tests/`: structured unit/integration regressions. Read all for baseline; include model stub tests and HTTP tests.

## Safe development workflow
1. Clone/open `Xeminas1/Storyforge` and start from main. Read `AGENTS.md` and this file. Check release and branch HEAD before making assumptions.
2. Install/setup any test Python version supported by project (GitHub Actions currently Python **3.13**). Run `python -m unittest discover -s tests -v` and `node --check static/app.js`. v0.13.0 was reported with **104** local unit tests and a successful CI run; recount when running locally.
3. For a GM bug, create a fixture with the exact action, narration and `state_updates` that previously failed, plus allowable controls (NPC says "I..." but player does not). Test that invalid replies leave SQLite unchanged, a retry preserves existing text on failure, and state checkpoints stay consistent.
4. In addition to offline fake-model tests, request a manual live Ollama test on the user's PC: inspect actual request/context from the revised code (sanitised), observed first-token/complete-turn latency, and response. Do not imply you have access to the user's running services.
5. Keep user data under `data/` untouched by release packages. If schema changes are necessary, make non-destructive migrations and add rollback/backup tests.
6. **Legacy ZIP allowlist trap:** the user's installed updater only accepts paths from its own `installable()` function. In v0.10.0 adding `lore.py` made the package fail with **"Update includes a disallowed file: lore.py"**. The v0.10.1 fix put that code into allowed `engine.py`. Any new source file required at runtime needs a staged compatible updater migration, not merely an expanded allowlist in the *new* release. `AGENTS.md` and `docs/` stay repository-only.
7. For releases: bump `updater.VERSION`, amend fixture versions, verify build and manifest against **the currently installed updater** as well as the new updater, push changes, then check `.github/workflows/release.yml` succeeded and a new `Storyforge_vX.Y.Z.zip` asset exists on GitHub. The workflow will not create a new release if that version's tag already exists. State exactly whether GitHub publication or user's PC installation has been confirmed.
8. Avoid introducing new paid APIs, external dependencies, cloud calls, model-weight training, or broad background automation without discussing the tradeoffs with the user. Make user-visible controls and error messages clear; user specifically dislikes vague instructions and long waits.

## User acceptance examples
- Action: `I turn to look at the figure.` Expected: NPC/world events and character dialogue only; no PC speech, no invented PC spells, gestures, motives, decisions or historical actions; journal does not assert any.
- Action: `I smile knowing that Voldemort seeks me, I continue on.` Expected: acknowledge **only** authorised smile and continuing, describe NPC response and surroundings, not "I raise my hand" or "I make it clear I am the Dark Monarch".
- Setting: Hogwarts/Hogsmeade premise above. Expected: station intro, journey to Hogwarts and later Sorting Ceremony in correct order; GM introduces characters and gives user agency instead of assigning a house or moving them without permission.
- Correction: retry a problematic GM message with "you repeated what you said" or "you acted for Xeminas". Expected: faster understandable result; if Ollama fails or repeats, preserve old reply and saved state. Later dependent turns are not left inconsistent.
- Art/voice/music: saved SDXL-generated scene image displays as sidebar illustration and background; Kokoro voice can be stopped; ambient music has separate volume, fades under narration, does not autoplay in violation of browser rules.

## Communication and handoff expectations
Document reproducible symptoms, expected vs actual, diff, tests and uncertainty. Prompt the user only for actual local tests or files unavailable in GitHub (e.g. their game log, screenshot or exported campaign) when essential. Respect user preference for practical instructions rather than telling them *what* needs installing without specifying *how*. Keep a short change log in the repo for future Codex/ChatGPT sessions.

**Handover limitation:** This is a code/repo handoff, not a transfer of the user's private Windows files, installed models, campaign DB or a running process. The repo and v0.13.0 release were inspected on 2026-10-15. Actual gameplay bugs above were seen in user screenshots before/around recent fixes and require fresh live verification.
