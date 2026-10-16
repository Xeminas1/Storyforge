# Storyforge — Codex working instructions

Read [docs/CODEX_HANDOFF.md](docs/CODEX_HANDOFF.md) and [README.md](README.md) before changing code. The handover records status and user goals as of 2026-10-15. Review current code and GitHub releases first: documentation may age.

## Product contract
- Storyforge is a user-owned, locally hosted, open-ended fantasy **story RPG** and independent alternative to Friends & Fables; do not copy proprietary site assets, scripts, or protected content.
- The player alone decides their character's **dialogue, voluntary actions, thoughts, feelings, intentions, spells and choices**. The GM controls NPCs, the setting, sensory observations, consequences, and story initiative. Do not invent player actions even in first-person prose or journal/state updates.
- Prefer vivid, lived-in, dialogue-rich story and character relationships to combat (~80% noncombat as a creative target). Player input must be free-form, not limited to action menus.
- Lore must be selected and supplied from saved world sections AND the world description/scenario. Never treat reference articles as higher priority than creator-authored canon. Do not confuse intended future milestones with already completed events.
- A failed GM generation/retry must not lose the user's typed action, overwrite an existing GM message, or mutate campaign state. Corrections/rewinds must respect turn checkpoints; older turns may lack checkpoints.
- User saves (SQLite DB, art, portraits, preferences) are private local data under `data/`; never ship, overwrite, commit, erase or migrate them destructively. Keep externally reachable services bound to localhost.

## Architecture
- `engine.py`: SQLite, campaigns, lore selection, character/spell rules, GM prompting, output validation, retries, persistent journal, ComfyUI generation and Wikipedia reference discovery. The discovery code lives **inside engine.py** for old-updater compatibility.
- `server.py`: Python standard-library HTTP API and local web server (default `127.0.0.1:8787`).
- `static/app.js`, `static/index.html`, `static/styles.css`: browser UI, audio and ambient soundtrack.
- `narration.py`: Kokoro local voice adapter (default `127.0.0.1:7860`).
- `updater.py`, `tools/build_release.py`, `.github/workflows/release.yml`: manifest-verified ZIP installation, backups, rollback and release channel.
- `tests/`: regression and API tests. Extend these for every bugfix.

## Working and shipping
On 2026-10-16 the user said **"push this update please"**, approving the current GM rework as **v0.15.0** through the existing main-branch release workflow. This approval supersedes the earlier local-only freeze for this update. Verify publication before claiming success; it does not authorize unrelated future releases. See [docs/CONTINUATION_HANDOFF.md](docs/CONTINUATION_HANDOFF.md) for current release and scheduling status.

1. Reproduce and test the problem first. Avoid claiming a model-level fix is guaranteed merely because a regex or prompt was added.
2. Run `python -m unittest discover -s tests -v` and `node --check static/app.js`; run browser/HTTP tests when practical, disclose any unavailable verification.
3. **Crucial updater compatibility:** the installed updater accepts only an explicit set of ZIP paths (see `updater.installable`). v0.10.0 broke updates by adding `lore.py` to a ZIP; v0.10.1 had to move it to approved `engine.py`. Do not introduce new installable filenames without a tested upgrade path from the user's current installed version. Repository-only `AGENTS.md` and `docs/` are deliberately not part of the release ZIP.
4. A new GitHub release requires bumping `updater.VERSION` (and adjusting version-sensitive fixtures), building via `tools/build_release.py`, and pushing to main; GitHub Actions runs tests and publishes `Storyforge_vX.Y.Z.zip` if that tag is new. Check workflow AND published asset. Never claim it is installed on the user's Windows PC unless verified there.
5. Keep source- and test-only changes distinct from feature releases. Do not let UI changes destroy existing saved campaigns, image cache, or running playback.

Priority and known defects are in `docs/CODEX_HANDOFF.md`.
