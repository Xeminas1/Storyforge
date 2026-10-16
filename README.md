# Storyforge v0.15.0 — focused GM context and persistent story memory

This update gives the local Game Master a focused view of the current story, validates proposed state changes and adds inspectable campaign memory.

- **Focused context:** one 16,000 UTF-8-byte budget replaces independently truncated prompts. Complete required world premises and requested ability effects, costs and limits survive; recent developments and the latest scene ending take priority over optional older detail. Essential context that cannot fit produces a clear error before inference. Byte counts estimate context pressure, not exact model tokens.
- **Grounded story memory:** optional NPC facts, observed events and pending threads persist with campaign checkpoints. Production state changes and memory need exact visible narration evidence. Journal and Relationships controls remove incorrect notes from current state and rewind snapshots without deleting story messages.
- **Model reliability:** typed JSON Schema, independent structure/evidence validation, incomplete-response rejection and bounded repair requests. The known `qwen3:8b` tag uses Qwen's documented non-thinking sampling baseline; this does not change or download your model.
- **Local evaluation:** compare installed models through ten disposable synthetic scenarios covering player agency, spell limits, Hogwarts continuity, lore priority, repetition and retry preservation.

Campaigns, characters, spellbooks, artwork, voice and music remain supported. Memory uses additive state JSON with existing checkpoints; this update adds no SQLite schema migration or third-party Python dependencies. It does not backfill invented memories into older campaigns.

Local verification currently passes **231 tests on Python 3.13 and 3.12**, including scripted HTTP/Ollama and executable browser-control checks. These safeguards cannot prove semantic player agency, story quality or Fables parity. Live Qwen behavior and Windows/GPU performance remain unverified; local gameplay testing remains necessary.

## Install and evaluate v0.15.0

After GitHub publishes v0.15.0, use **Updates → Check & install latest release now**, then refresh the browser. Your private `data/` directory is retained.

Start Ollama as usual. From your updated Storyforge folder in PowerShell, run:

```powershell
py server.py --evaluate-model qwen3:8b --repeat 1 --report data/model-check-qwen-v015.json
```

This uses disposable campaigns, leaves personal saves untouched, and does not start the server/updater, download a model or change your selected model. Reports include synthetic prompts, generated/rejected prose and timings. Existing reports are never overwritten; choose a new filename for another run. Open the JSON report and review each case's manual-review questions: `completed` means the pipeline accepted it, not that storytelling or player agency is proven correct. A transport failure leaves later cases explicitly unrun.

To compare models already installed on your PC, first run `ollama list`, then repeat `--evaluate-model` with those exact names. For example, **only if both tags are installed**:

```powershell
py server.py --evaluate-model qwen3:8b --evaluate-model qwen3:14b --repeat 3 --report data/model-comparison-v015.json
```

No replacement model has been selected. Check an existing campaign's player agency, Hogwarts scene progression, a later-turn retry, saved artwork and audio controls after updating. Maintainers run `python -m unittest discover -s tests -v` and `node --check static/app.js` before publication. Extended evaluation and research notes live under `docs/` in GitHub; they are excluded from installed ZIPs.

---

# Storyforge v0.14.0 — player ownership, grounded lore and reliable corrections

This release strengthens the boundary between the player's submitted action and the GM's world/NPC narration, and fixes several ways a failed or delayed request could damage continuity.

- **Player ownership:** action checks now distinguish the acting character, negation and objects. Watching an NPC raise a hand, refusing to raise a hand, or raising an eyebrow does not authorize the GM to raise the player's hand. Named-character thoughts, passive choices, compound actions and player dialogue have additional checks. Acknowledged dialogue must retain the player's actual words.
- **Protect story state:** the GM's scene heading, journal, location/time labels and inventory strings are checked before saving. Rejected drafts are excluded from the corrective prompt. Suspect old GM messages and journal entries are withheld from model context and lore retrieval, while the saved originals remain available for explicit correction.
- **Lore and continuity:** relevant creator canon takes priority over imported public references. References retain their provenance/source, matching complete passages replace blind article-opening excerpts, and the active scene receives more retrieval weight than a planned opening. The complete saved world premise remains in context. Lore preview shows creator/reference labels.
- **Reliable corrections:** retrying later turns now retains the message IDs needed to restore context. Failed sends retain edited drafts. Delayed sends, feedback and campaign loads cannot replace another adventure's visible state. Submitted corrections keep their controls disabled until the server finishes; closing a dialog cannot cancel a running model request.
- **Bounded generation and diagnostics:** at most two generations share a 95-second retry budget, with each Ollama socket timeout capped at 70 seconds. A slow server can still exceed a strict wall-clock deadline; this is not GPU/process cancellation. Ollama failures provide actionable guidance without including response bodies. Optional diagnostics report timings, token counts, model and request ID without logging prompts, story text or generated prose.

The checks are conservative text/grammar safeguards, **not a guarantee that every possible model hallucination is detectable**. Live Qwen quality, false rejections and latency still need testing with your installed Ollama model. The game remains free-form and story-focused; NPC dialogue, written documents, externally caused effects, voice, ambient music and artwork remain supported.

## Install and local verification

Use **Updates → Check & install latest release now** after GitHub publishes v0.14.0. Saved campaigns, characters, artwork and preferences under `data/` are retained. This release adds no schema migration or third-party Python dependencies.

Run `python -m unittest discover -s tests -v` and `node --check static/app.js`. The release workflow also runs the executable browser-request checks through Node. Local HTTP/model-protocol tests use a scripted localhost model, not a real Qwen generation.

After updating on your PC:

1. In an existing campaign, try `I turn to look at the figure.` and `I smile knowing that Voldemort seeks me, I continue on.` The GM should advance NPCs/world events without adding your character's speech, gestures, decisions or private beliefs.
2. Retry a later GM message with feedback. Confirm earlier context is preserved. If Ollama fails, the old reply, later dependent turns and your draft must remain intact.
3. In the Hogwarts campaign, check **What lore does the GM see?**, then verify the current scene continues without replaying the arrival or treating a future Sorting Ceremony as completed.
4. Check saved portraits/scene art and narration/music controls in Brave. These cloud tests do not establish Windows audio or GPU behavior.

For optional timing diagnostics in PowerShell, set `STORYFORGE_DIAGNOSTICS` before launch:

```powershell
$env:STORYFORGE_DIAGNOSTICS = '1'
py server.py
```

Keep these diagnostics local. They contain request metadata and model names, not the story text. Remove the variable or close that PowerShell session to return to normal logging.

---

# Storyforge v0.13.0 — world premise and contextual lore grounding

World Atlas description is now **always** included in Game Master instructions. This repairs a bug where the description was stored and displayed but was omitted from the local model's actual context whenever the world contained separate lore entries.

- Treat creator-provided starting location and future milestones as a scenario to progress through without skipping scenes or commandeering the PC.
- A short scenario clarification for worlds explicitly referencing Hogwarts and Sorting distinguishes the arrival at Hogsmeade Station from the later Great Hall Sorting Ceremony. The PC must choose their own participation and house decisions.
- Select a compact, relevant subset of saved world lore using the overview, current location, player action and recent player actions. Long lore excerpts are capped so the 8,192-token local model context is less likely to be crowded out.
- World tab and World Atlas now provide **What lore does the GM see?**. It displays the always-included premise and selected saved entries. The displayed selection is based on the current scene; it may change with your next action.
- This feature **does not import new lore by itself**. Use **Discover lore** to add specific characters, places, or settings. The model should not pretend unspecified events have already occurred.

Previously generated GM messages and old journal entries are not rewritten by an update. Use Retry/Feedback to correct a past scene; older turn state checkpoints still apply.

## Tests

`python -m unittest discover -s tests -v` and `node --check static/app.js`. Verify the ZIP with the installed v0.12.1 updater. Saved campaign database is not replaced by the update.

---

# Storyforge v0.12.1 — Player agency and journal integrity hotfix

Fixes GM first-person and third-person player action hallucinations, and validates Story Developments as well as narration. Existing suspect journal entries are excluded from GM context and can be removed by the player from the Story Developments panel. This does not silently rewrite old messages.

# Storyforge v0.12.0 — Scene-aware ambient music and GM response reliability

## Ambient soundtrack

The adventure's right sidebar now has **Ambient music** with a play/stop button, volume independent of narrator volume, and a scene mood menu: Auto, Exploration, Tavern, Mystery, Danger, Peace. Auto mode chooses a mood based on recent location or prose (heuristic, not story state). Music is synthesised on-device using the browser's Web Audio API: it is a modest, evolving instrumental drone and chime melody, **not** an external music service or commercial soundtrack. It doesn't download or stream music, require an account, or include copyrighted music recordings. Music ducks to about 32% of its chosen volume during speech and returns afterward.

Due to browser autoplay restrictions, press **Play music** once per browser session. Music is off by default and never starts automatically without permission. The optional preference is saved locally in your browser.

## Repetition and slow retry corrections

The GM checks whether a new response repeats substantial passages from earlier GM messages or repeats a paragraph inside its own answer. It asks for a fresh reply rather than storing obvious copies. Very short or appropriately recurrent details are allowed. Checks are heuristic and won't prevent every thematic repetition.

The GM now makes **at most two** generation attempts rather than three. Local Ollama inference has a 70-second per-call network timeout and an approximate 1050-token cap, and Qwen3's optional thinking mode is disabled for the structured narration task. Failure returns a clear message without consuming the player action or deleting an older reply. If the local GPU is overloaded or a long lore context causes slow inference, choose a faster installed Ollama model or shorten the action.

## Data / compatibility

No changes to the persistent SQLite schema. The new music feature is browser-only; existing saved characters, scene artwork, spellbooks and message history are preserved. The release ZIP is checked against the installed v0.11.0 updater before publication.

## Tests

Run `python -m unittest discover -s tests` and `node --check static/app.js`. The local audio controls are not a guarantee about audio performance on every Windows sound device; test in Brave with Kokoro.

---

# Storyforge v0.11.0 — message correction, rewind and feedback

**Hotfix:** v0.10.0 accidentally included `lore.py`, which Storyforge v0.9.0 rejects as an unapproved update path. Version 0.10.1 moves the lore functionality into the existing approved `engine.py` module and removes the incompatible file from the release archive. No saved campaigns or art are affected. The original v0.9.0 updater can now install this release without relaxing its path restrictions.

## New features

- **Public lore discovery**: Create World → Discover universe lore, an existing world's **Discover lore** button, or World Atlas → Discover lore. Enter “Harry Potter” or “Wizarding World”; Storyforge expands related searches to include Fantastic Beasts, characters, magical places and more. Optional additional series are comma-separated.
- **Opt-in, source-attributed import**: Review and select Wikipedia introduction extracts. Import to a new or existing world with article URLs and CC BY-SA 4.0 attribution recorded in each lore section. Duplicate entries are skipped. This is **not** a complete fictional universe data dump or an import of copyright-restricted Fables community worlds; encyclopaedia coverage is incomplete. Community-supplied canonical lore still takes precedence.
- **Player agency**: GM policy explicitly prohibits inventing the protagonist's dialogue, thoughts, choices, spell use or physical actions. A second check detects obvious violations and retries the model twice. The action and GM turn are only committed after a valid response. Detection is deliberately conservative and cannot guarantee catching every improper PC action.
- **Model response robustness**: Malformed JSON gets correction requests. If the GM fails three times, no action is consumed and an actionable error is returned. Ollama connection/timeout errors are clearer.

## Limits and safety

Lore discovery uses the public Wikimedia MediaWiki API over HTTPS. Requires a working internet connection; VPN or network policies may block it. Storyforge does not crawl creator-owned Fables worlds, fan-wiki sites, or private accounts. Wikipedia snippets are factual summaries that may be incomplete or differ from an adaptation; users decide which entries belong in the campaign. Stored reference lore is source data, **never instructions to the Game Master**.

The game still uses a local Ollama model and the existing SQLite campaign saves. The update is compatible with the preceding version and does not alter `data/` when installed.

## Tests

Run `python -m unittest discover -s tests`. Build release with `python tools/build_release.py 0.10.0`.

---

# Storyforge v0.10.0 — immersive scene backgrounds and story-led Game Master

## Highlights

- The *same locally cached Scene artwork* now fills the adventure's story column behind readable frosted-glass narrative panels, with blur and dark overlays for contrast. The image and background update when the location changes; without art, the existing dark background remains.
- New GM messages begin with `[Location - Parent Area - Time of Day]` on its own line and a blank line before narration; unknown details use a non-invented fallback until established. New story-state fields preserve parent area and time of day.
- Written documents and text are shown in *italics*, shouts in **bold**, safely rendered without enabling arbitrary HTML. The speech adapter strips formatting and the scene heading before Kokoro synthesis.
- The GM is now guided to sustain lived-in, dialogue-heavy stories, natural relationships and political rumours, roughly 80% plot/social scenes versus 20% combat, with darker fictional consequences, lasting cause-and-effect and independent NPCs. The GM drives events **without narrating the player's decisions or thoughts**.
- Kokoro voice begins with a shorter first sentence and prefetches the next chunk while current audio plays. This can reduce initial delay and gaps, but real speed depends on the installed Kokoro service and GPU load. Stop and pause controls remain.

## Install

On v0.8.1, select **Updates → Check & install latest release now**. Your data directory, saved games, character portraits and cached artwork are not replaced.

## Validation

Run `python -m unittest discover -s tests -v`. The repo's GitHub workflow creates releases from committed code; no personal campaign data should be pushed.

## Notes

This is still an offline-first, single-player local app. The new header applies to **new** GM responses; old saves are displayed as originally stored. The current small Ollama model may not follow every creative constraint perfectly. The art background appears only after a location image has been cached. The sidebar art remains full-detail and can be enlarged independently.

---

# Storyforge v0.8.1 — artwork-led sidebar

The adventure's right column is wider and its Scene panel gives location artwork a much larger, uninterrupted frame. Scene and World tabs, character information, location controls and campaign saves remain supported.

- Scene title is shown above the illustration instead of covering it.
- The image fills the larger frame, with **View full** to inspect the entire uncropped generated image. Close with the button, backdrop click or Escape.
- Generate, Regenerate and Lock controls remain beneath the image.
- Responsive sizes retain the existing mobile sidebar behaviour and preserve the story composer.

To update from v0.8.0, use **Storyforge → Updates → Check & install latest release now** after GitHub publishes v0.8.1.

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
## v0.8.0 — spellbook definitions, spell artwork, and speakable narration

- Open **Characters → choose a character → Abilities & spells**, then **Edit ability** or **Add spell or ability**. In an adventure, open the **Character** full overlay, select **Spellbook**, and do the same. Spell entries have an effect, visual description, range, target, cost, limitations, type and flavour. Older one-line spell names are retained with stable IDs and blank descriptions ready to fill in. This is a reusable character feature; editing abilities during a campaign updates that character's library template without overwriting other campaign saves.
- Each spell can use a PNG/JPEG/WebP image (up to 8 MB). Images are stored in `data/artwork/spells/` and survive updates. You can optionally check **Generate artwork** when saving. It uses the same local ComfyUI service and simple checkpoint sampler workflow as scene art. The art generation job runs in the background; images appear on the spell card after reopening it or refreshing the character. Image generation needs a compatible model; uploads never need ComfyUI.
- The Game Master receives the actual spell rules as structured context, not just their names. It must judge attempted use fairly and obey declared limitations. Abilities do not become guaranteed successes.
- The Game Master is told to avoid asterisks, escaped Markdown and other markup. The narration response is also normalised before storage, and the speech adapters clean **old** saved messages before sending text to Kokoro or browser TTS. For example `\\* wrong \\*` is spoken as `wrong`. Spell names/descriptions are not removed.

### Getting local artwork generation running

1. Install **ComfyUI** from its official project: https://www.comfy.org/ (Windows Desktop or portable/NVIDIA package).
2. Run it locally with a compatible **full Stable Diffusion image checkpoint**. Storyforge's current standard generator uses the CheckpointLoaderSimple/CLIPTextEncode/KSampler graph, not the specialized FLUX/SD3 loaders. Put the `.safetensors` checkpoint in the ComfyUI `models/checkpoints` folder (the location depends on which ComfyUI install you chose) and restart/reload ComfyUI.
3. Check that `http://127.0.0.1:8188/system_stats` is reachable on the host PC. Storyforge also checks `/object_info/CheckpointLoaderSimple` and requires that at least one checkpoint is listed. If ComfyUI runs on another local port, set `STORYFORGE_COMFY_PORT` to that port before launching Storyforge and restart it.
4. Return to the **Scene** tab to generate a location image, or the **Spellbook** to generate a spell image. Choose a supported checkpoint when asked. Background image jobs can be slower when Ollama and Kokoro share GPU/CPU resources.

**Security:** keep ComfyUI, Storyforge, Ollama and Kokoro bound to localhost, not exposed to the public internet. Generated imagery is not included with GitHub source or release ZIPs; your images remain in `data/`.


## Message controls (v0.11.0)

Every Game Master message offers **Listen**, **Retry / Feedback**, and **Delete**. Every player action offers **Resend / Feedback** and **Delete**. Retry asks for optional correction notes and regenerates the reply from the prior conversation context. Deleting a GM reply leaves the preceding player action in the feed so you can resend it. Rewinding from an older turn removes all later dependent messages; confirm the warning before proceeding. Generation errors do not erase the original messages.

New GM turns record exact before-and-after snapshots for locations, inventory, journal, time and other campaign state, so rewinds restore the state from before that turn. Earlier stories from v0.10.1 and older did **not** store snapshots. Older replies can be retried or deleted, but their original inventory/journal/location effects cannot be completely reversed: the existing state is preserved and a warning is shown. These are local database operations and the release preserves your database under `data/`.

Correction feedback is saved in the local `gm_feedback` table, and the three most recent non-empty feedback instructions are supplied in later GM context. This is in-context guidance, **not** automatic model weight training or a promise of permanent learning. Player agency validation and rejection of unsupported PC actions remain enabled. A change to an older turn invalidates later story text rather than retaining contradicted consequences. Future editing of individual messages or branching timelines can be developed as a separate feature.

Reference: Friends & Fables' official ACE 1.5.4 note recommends editing or retrying messages instead of arguing with the GM out-of-character; Storyforge's controls are independently implemented rather than a reproduction of proprietary code or styling.
