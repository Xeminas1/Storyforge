# Storyforge v0.4.0 — automatic GitHub updates

Storyforge is a locally hosted AI story RPG. Version **0.4.0** adds an unattended
update watcher that looks for verified new releases in the dedicated
`Xeminas1/Storyforge` GitHub repository. The GitHub update channel becomes active once the repository has published its first official release.
The updater does not require any stored GitHub access token when the repository
and its release files are public.

## Install v0.4.0 from the Storyforge v0.3.0 browser interface

1. Download `Storyforge_v0.4.0.zip` to the PC that runs Storyforge.
2. Visit http://127.0.0.1:8787 in Brave. Click **Updates** (top right).
3. Click **Choose file**, select the entire downloaded ZIP *without extracting it*,
   then **Verify selected update**.
4. Click **Install update & restart Storyforge**. The updater backs up your
   SQLite database and existing app files, restarts the server and attempts to
   roll back program files if the replacement fails its health check.
5. When the page reloads, the Updates button should show **v0.4.0**. Open it
   to see the new **Automatically install trusted updates when idle** option.

**Important:** v0.3.0's older, manual installer still requires the button press
for this one upgrade. The ZIP was explicitly tested against the v0.3.0 updater's
file allowlist and checksum verification. Do not overwrite or delete `data/`.

## Automatic updates after GitHub releases are configured

- This version is pinned to `https://github.com/Xeminas1/Storyforge` and
  `https://api.github.com/repos/Xeminas1/Storyforge/releases/latest`.
- When enabled (initial default), it checks approximately every **4 hours**,
  also checking shortly after startup. GitHub release checks are read-only.
- It only uses normal, stable newer versions, with the exact expected ZIP name
  `Storyforge_vX.Y.Z.zip`. It verifies the SHA-256 release asset digest supplied
  by GitHub, ZIP path rules and SHA-256 file hashes in the internal manifest.
- New releases **install without asking again**, but only once Storyforge has
  detected **10 minutes without a visible game session or interaction**.
  A visible browser tab regularly sends an activity heartbeat.
- New releases are staged in `data/updates/staging`. Backups, update status and
  logs are in `data/updates`. Your existing `data/storyforge.db` is retained.
- You can disable automatic installation under **Updates** whenever you want.
  The old manual ZIP method also remains available.
- The first missing-GitHub-repository or no-release result is informational,
  not a failure of your installed Storyforge application.

**Security limitations:** the internal ZIP checksum manifest alone is not a
publisher signature. The release channel relies on GitHub HTTPS, the pinned
repository identity and the GitHub-published SHA-256 asset digest. Someone who
gains control of the designated GitHub repository could publish malicious code;
therefore protect it with MFA and restricted collaborators. Never expose
Storyforge's unauthenticated localhost server directly to the internet.

## Official development and update channel

Source repository: https://github.com/Xeminas1/Storyforge

The GitHub Actions workflow runs the unit tests and creates a release when a
newer version reaches the main branch. Releases are built from the checked-in
source, not from saved campaign data. The first release is `v0.4.0`.

To publish future updates, increment `VERSION` in `updater.py`, update the
changelog and tests, and commit the tested changes to `main`. The release
workflow builds `Storyforge_vX.Y.Z.zip` and publishes it as a GitHub release.
Do not publish personal world exports, game saves or secrets to GitHub.

Creating a repository alone is not enough to activate unattended updates:
there must be a successful GitHub Actions run and a real release asset. A
running Storyforge v0.4.0 installation can automatically install **future**
releases, after the update watcher verifies the asset and detects an idle session.

## Compatibility and testing

- Python 3.11+ and Ollama for game narration; Docker is only needed for optional
  Kokoro voice generation. No new Python packages are required for the updater.
- 32 automated tests cover story storage, character editing, manual updater,
  release metadata validation, checksum tampering, and idle/disabled behaviour.
- JavaScript syntax was verified and the ZIP was validated with v0.3.0's updater.
- Windows unattended restart and a live GitHub release upgrade **have not yet
  been tested**; the private test runs do not prove those environments.

## Character creation changes

- Identity: character name, pronouns, race/species, class/role, alignment/outlook, aliases/titles.
- Separate **appearance, personality, mannerisms, backstory, motivations, weaknesses, factions, starting location**.
- Free-form spells/abilities, plus optional D&D-style stats and initial possessions.
- Select **Edit** in a campaign's character card to modify a pre-existing character without losing its messages, state, or other saves.
- All the character properties are included in Game Master context, not just a combined description. Mannerisms describe the player's established style, **not** actions the AI may force the player to take.

The editor takes inspiration from RPG character-sheet features, but is **not yet exact Fables character-form parity**: character portraits, AI-generated sheets, feats and saving throw validation are not implemented.

## Narration controls

- Visible at the top of the story (instead of buried in the right-hand sidebar): **Pause/Resume, Stop, and Volume**.
- Stop cancels active browser speech or playing neural audio and interrupts pending neural voice requests.
- Replay the last Game Master message or play a specific GM message via `▶ Listen`.
- Neural/Browser voice selection, rate control and settings persist in your browser.
- For browser/Windows speech, changing the volume affects the next spoken chunk; neural audio volume changes immediately.

### Optional: natural local narration with KokoroTTS

The browser's built-in voice is still available, but **it will still sound like Windows/Brave speech synthesis**. To get a different, generally more natural voice, you must also run a **local KokoroTTS service**. Storyforge talks to it only through your own PC at `127.0.0.1:7860` and does not send campaign text to a commercial cloud TTS API. This is not yet multi-character / NPC voice switching.

**Using Docker Desktop on Windows (easiest supported route):**

1. Install and start [Docker Desktop](https://www.docker.com/products/docker-desktop/) if you don't have it. It normally uses WSL2 on Windows. Docker images are large and the first run may take time to download.
2. In PowerShell, run this **CPU-compatible** version first (it works without Docker GPU configuration):

   ```powershell
   docker run --name storyforge-kokoro -d -p 127.0.0.1:7860:7860 -v kokorotts_data:/app/persistent hangrylabs/kokorotts:v1.0
   ```

   If this is already created from a previous run, use `docker start storyforge-kokoro`. To view logs: `docker logs storyforge-kokoro`.

   You can optionally run it on an NVIDIA GPU if Docker Desktop/WSL2 and NVIDIA GPU container support are set up. Start a **new** container with `--gpus all` and the same localhost port. Since your GPU also runs Ollama, benchmark the memory use first; CPU mode is a safer initial test.
3. Visit `http://127.0.0.1:7860/health`. You should see a healthy response. If it isn't up yet, wait for Kokoro's startup.
4. Restart/refresh Storyforge and choose **Kokoro neural (local)** under **Narration → Voice Engine**. Try **George · British male** and click `▶ Replay last`. You can choose other voices from the dropdown.
5. Test the **Stop, Pause, Resume, and Volume** controls at the top of the story.

The speech server's local endpoint follows KokoroTTS's documented OpenAI-compatible `POST /v1/audio/speech` protocol. If the server isn't running, Storyforge reports an error and you can switch to the browser voice; there is no automatic silent fallback. **Kokoro generation quality and speed have not been verified on your hardware**, and the third-party Docker image is not bundled with Storyforge.

Service code reference: https://github.com/hangry-labs/kokoroTTS#openai-compatible-api

## Community world importing

Still unchanged from v0.1: manual lore paste and **creator-supplied** CDF-style ZIPs with `.md` and `.json` material. **Pasting a Friends & Fables public-world link does not download it.** The importer does not scrape third-party worlds or bypass access controls. Keep the creator attribution and obtain transferable world data with their permission.

## Tests and data

Run: `py -m unittest discover -s tests -v`

- 23 automated regression tests for imports, campaigns, new and legacy character editing, and the neural audio adapter.
- Persistent saves remain at `data/storyforge.db`.
- Storyforge binds to `127.0.0.1:8787` by default and KokoroTTS is meant to bind only to `127.0.0.1:7860`. **Don't port-forward these unauthenticated local services to the public internet.**

## Known gaps

- Full Friends & Fables-form parity and community-world one-click import are not complete.
- Neural speech currently uses **one selected narrator voice**; assigning distinct voice models to NPC dialogue needs a dialogue segmentation pass and per-NPC state.
- The browser controls cannot change the built-in TTS voice mid-utterance and automatic neural playback can be limited by a browser's autoplay policies.
- `data/storyforge.db` needs regular backups; there is no cloud sync or migration tooling yet.

## Packaging future Storyforge releases (for maintainers)

Use `python tools/build_release.py X.Y.Z` to generate a `Storyforge_vX.Y.Z.zip` containing an update manifest and hashes. Bump the version string in both `server.py` / `updater.py` as appropriate, and run the unit and HTTP integration tests before publishing. The version in the manifest must match the code shipped.