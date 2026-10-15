# Storyforge v0.7.0 — Campaign-first home & reusable characters

## Changes

- The home page displays **Recent Campaigns** at the top with an immediate **Continue** action, followed by **Discover Worlds**, based on a familiar fantasy-RPG browsing layout but using Storyforge's original styling.
- Home navigation includes Home, Discover, Campaigns, and **Characters**. The character library opens in a large overlay, separate from the per-adventure character panel.
- Any existing campaign character is **migrated once** into the character library, retaining its appearance, mannerisms, abilities and optional portrait. Existing campaigns and story messages are not changed.
- You may create and edit standalone reusable characters in the library without starting an adventure.
- Starting an adventure now offers a saved-character chooser and the option to create someone new. A character's appearance and abilities carry across; each campaign retains its own independent state and story.
- During play the left Character button opens the character overlay on the first click. Navigating Home no longer discards the loaded campaign.
- Saved campaign artwork, where generated, can appear on recent campaign covers; other cards use local themed gradients rather than fetching external artwork.
- Portraits remain saved under `data/artwork/portraits/` and are preserved by the built-in updater.

**Install**: With Storyforge v0.6.2 open, choose **Updates → Check & install latest release now** when this release is published. Backups and rollback are handled by the existing updater. After restart, refresh the browser. Never delete the `data/` folder.

**Important character editing behaviour**: A reusable character is a template. Edits to a campaign's character update that character's reusable template, but **do not rewrite other campaigns already using it**. Campaign progress and journal entries are always separate.

**Testing**: Python unit tests cover migrating old SQLite databases, reusing character profiles, preserving existing portraits, keeping campaign state isolated and updater compatibility. JavaScript syntax, a browser test of navigation/character selection, and a release package check were also run. A live Windows upgrade should be validated on your PC.

---

# Storyforge v0.6.2 — full character portraits

This patch fixes portrait images being cropped in both the small sidebar character card and the full Character menu. Portraits now use `object-fit: contain` and a taller portrait-shaped container, so the whole uploaded image remains visible. Landscape and square images will be letterboxed rather than cropped. The character editor, overlays and local saved artwork are unchanged.

**Updating:** In Storyforge v0.6.1, go to **Updates → Check & install latest release now**. Storyforge will back up saves and restart. If the automatic update does not run, use the v0.6.2 ZIP from the official GitHub release. Do not delete your `data/` folder.

**Validation:** All unit tests and portrait-specific regression checks must pass before publishing. The project uses Ollama for story generation, optional Kokoro for spoken narration, and optional ComfyUI for generated art. No ComfyUI restart or new portrait upload is required for this CSS-only layout fix.

Repository: https://github.com/Xeminas1/Storyforge

# Storyforge v0.6.1 — updater compatibility fix

**Use v0.6.1, not v0.6.0.** The initial 0.6.0 package included a new Python source file that the older v0.5.1 updater would reject. Version 0.6.1 puts the same image-generation functionality in the already-approved core module `engine.py`. It is compatible with the v0.5.1 and v0.5.0 updater file allowlists. Your saved campaigns and existing voice setup stay intact.

# Storyforge v0.6.0 — character codex & location artwork

## What's new

- The **left Character, World and Journal icons** open large overlays over the story instead of merely switching the right sidebar. Character view includes a large portrait, Character Sheet, Inventory, Spellbook, Progression, Relationships and Memories tabs. The sidebar tabs remain compact, contextual summaries.
- **Character image**: upload PNG, JPEG or WebP (max 8MB) in the character editor or full character view. Image persists in `data/artwork/portraits`, including through code updates. The portrait can also be generated with an installed ComfyUI image-generation checkpoint.
- **Scene image**: an illustration can be generated for the location under **You are here**, saved locally in `data/artwork/scenes`, and reused for the same world/location. Buttons permit regenerating from latest GM narration and locking the image. Generation is asynchronous.
- The app automatically requests scene art on entering a new location **only if a local ComfyUI with a checkpoint is already available**. Otherwise you get a graceful placeholder and a manual generate button.

## Local image generation setup (separate from Kokoro)

**Kokoro is for speech only.** To generate artwork, install and run **ComfyUI** separately on the machine hosting Storyforge, using an image checkpoint compatible with the standard CLIP / checkpoint / sampler workflow. By default Storyforge connects to `http://127.0.0.1:8188`. Put one or more checkpoints under `ComfyUI/models/checkpoints` and confirm ComfyUI sees them. You can set `STORYFORGE_COMFY_PORT` before launching Storyforge to use another local port; remote addresses are deliberately unsupported. No ComfyUI credentials, public APIs or image-generation subscription are required; a GPU-compatible ComfyUI install may need additional setup.

**Note on performance:** this calls ComfyUI with standard 1024×576 location and 640×896 portrait latent dimensions. Some older SD1.5 checkpoints may work better at 512px, and some newer model families (e.g. Flux) require different node graphs and will not work with this initial generator. On your RTX 5080 the GPU resources and first-model load may make image generation take a while; speaking through Kokoro and running Ollama also share system resources. Jobs stay in the background but performance needs real-world validation.

## Release / preservation

- The updater includes `artwork.py` in its permitted source-file manifest.
- All generated and uploaded images live under the existing `data` directory **outside release packages**, just like the SQLite database.
- Do not delete your `data` folder; update through the existing **Updates → Check & install latest release now** button after this version is published to GitHub.
- The Fables screenshots informed the *interaction pattern* (large overlays versus contextual panels); Storyforge uses its own artwork, markup, colours, and code. We cannot inspect every signed-in Fables menu without access to that live session, so this release should not be described as a pixel-identical reimplementation.

## Known limitations

- Character **Relationships** and **Progression** tabs display honest placeholder information rather than fictitious game-state tracking; adding complete engines for these is a separate development task.
- Portrait generation requires ComfyUI locally. Portrait upload works without ComfyUI.
- Existing creator-provided world imports are unchanged. Storyforge cannot directly scrape third-party community-world URLs.

---

# Storyforge v0.5.1 — one-click GitHub updates

Version 0.5.1 adds **Check & install latest release now** to the Updates dialog. Click it from the Storyforge browser running on your PC: it looks up the newest official `Xeminas1/Storyforge` release, verifies GitHub's release digest and the ZIP's internal checksums, backs up campaign data, installs and restarts immediately—**no waiting 10 minutes**. It works even when unattended updates are disabled. It does not bypass checksum verification, the publisher restrictions, or local-only browser checks. Existing automatic updates still wait for idle time. Do not close the PowerShell window running the server.

**Bootstrapping the button:** installations on v0.5.0 must first receive this v0.5.1 update through the existing unattended updater or manually through the existing Updates → Choose file → Verify → Install flow. Once on v0.5.1, future releases can be installed with one click.

# Storyforge v0.5.1 — immersive story interface

Storyforge is a locally hosted, free-form story RPG powered by an Ollama Game Master.

## What changed in v0.5.1

- A compact, icon-based navigation rail. Click **Adventures** for a floating saved-story picker, or open saved adventures directly from the library.
- An immersive three-column adventure view: narrative feed, persistent free-form composer, contextual sidebar.
- Scene / Character / World tabs. Scene shows your **recorded location**, currently controlled player character, logged developments and inventory. Character shows portrait placeholder, portrayal, optional character-sheet hit points and spells. World displays imported lore sections.
- Always-visible narration playback toolbar and separate collapsible voice engine options.
- An **Update available** highlight in the top toolbar whenever the GitHub release watcher has a **newer verified release pending** (including while it's waiting to install); the badge updates every 60 seconds.
- Narrow-screen support with a Details drawer and responsive navigation. No required action menus or tactical combat were introduced.
- The user's existing data/ folder and campaigns are preserved during updates.

**Scope limitations:** the scene panel uses an original decorative location card rather than a real map; NPC location tracking, relationship mechanics, and art import are still future projects. Optional hit points come from the character profile; they are not a live combat tracker. Natural Kokoro narration still requires a running Kokoro service. Public Friends & Fables URLs cannot currently be downloaded automatically; import world files or text shared by their creators.

## How to receive v0.5.1

- If Storyforge v0.4.0 has automatic updates enabled, leave the app running. It checks GitHub periodically and installs a verified release after 10 minutes of inactivity **only when the browser isn't actively using Storyforge**. It can be enabled or disabled under **Updates**.
- To update immediately, download `Storyforge_v0.5.1.zip` from the official GitHub release, then use **Updates → Choose file → Verify selected update → Install update**. Never extract the ZIP manually when using the updater.
- Restart or refresh Brave after Storyforge finishes. Your stories remain in your PC's local `data/storyforge.db`.

**Security:** update verification checks the GitHub-provided release checksum and package manifest, but neither replaces release signing. Only the pinned repository `Xeminas1/Storyforge` is allowed as the unattended source. Keep your GitHub account secured with MFA and minimal collaborator access.

## Notes carried forward

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