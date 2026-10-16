# Public Fables research and Storyforge implications

Researched: **2026-10-16**. Scope: Friends & Fables' public homepage, help articles, blog and patch notes. This is an independent product/architecture analysis; no account login, private campaign access, client-code inspection, proprietary prompts, downloaded artwork, or copying of their implementation was used. No release or remote changes are authorized by this research.

## What was actually verified

Read-only HTTPS requests to `fables.gg`, `play.fables.gg` and `help.fables.gg` succeeded after the cloud network policy became enforced. The homepage links the help center as its official Documentation. The public play page returned an application shell; no signed-in gameplay, actual model quality, response latency, or player-agency behavior was tested.

The findings below describe **official documentation claims**, not a guarantee that the deployed product always behaves that way. Dates refer to dated articles where available, rather than assuming that older patch notes describe today's system. The earlier access blocker is resolved.

## The core lesson: a managed game engine around the narrator

[How Franz works](https://fables.gg/blog/how-franz-works) (2025-10-30) describes separate research, narration and state-update processes. A single player message may produce about a dozen requests to purpose-specific models, each receiving appropriate game-state context. Narration is only one stage. State postprocessing examines the current state, player input and narration before updating location, inventory and similar records.

This article explicitly argues for “the right context at the right time” rather than sending the entire world and transcript. It also acknowledges model and state-update mistakes, and describes a mixture of medium-size models chosen for speed and cost. Fables' documented architecture therefore does **not** support the conclusion that giving Qwen a longer system prompt will reproduce its behavior.

**Storyforge implication, not a Fables claim:** separate ownership of player input, retrieved facts, active scene and proposed state changes. Prefer a compact, validated generation path appropriate to a local model. Copying a cloud service's number of model calls onto one local GPU would need a latency justification; deterministic retrieval and validation can supply some of these responsibilities without extra inference calls.

## Grounding, memory and continuity

| Concern | Officially documented behavior | Independent Storyforge direction |
| --- | --- | --- |
| Working context | [Working Context Blocks](https://help.fables.gg/en/articles/8560008-working-context-blocks) describes a shared, editable notepad, researched before narration. Typed blocks can be active, idle or archived. Priorities, expiration and soft budgets select what fits. Sources and researched topics are visible. | Show the precise facts selected for the next turn, with sources and reasons; separate immediate scene, remembered events, creator canon and instructions. Keep retrieval and narration within a measured local context budget. |
| Lore research | The same article and [Lore](https://help.fables.gg/en/articles/7231815-lore) say the research system first sees folder titles, page titles and headings, then chooses relevant pages/sections. Structured entities hold character/item/location facts; lore holds other world information. | Index descriptive headings and complete passages. Retrieve narrowly from the creator's world and retain provenance. A large encyclopedic paste is not a substitute for scene-relevant facts. |
| Current scene | [Current Scene](https://help.fables.gg/en/articles/1999565-current-scene) says every request includes world/location information and nearby characters, items and monsters. Closer characters receive more detailed context. Editing the underlying entity fields changes this scene context. | Build an explicit active-scene record from accepted state, rather than repeatedly injecting an opening premise as if it were current history. Give present NPCs and unresolved exchanges priority. |
| Current plot | [Plot and Plan](https://help.fables.gg/en/articles/4217496-plot-and-plan) describes a running summary of important recent events, visible/editable by the player. | Maintain a bounded record of accepted events, with authorizations preserved. Planned milestones remain pending until supported by actual play. Do not turn a rejected draft into memory. |
| Long-term memory | [Memories](https://help.fables.gg/en/articles/2838157-memories) says memories are created every five turns, linked to locations and related characters, and retrieved into working context when relevant. Players can explicitly include a memory if retrieval misses it. The article acknowledges retrieval is imperfect and explains why all memories are not sent every turn. | Retrieve earlier accepted events by scene, entities and meaning; retain source turn IDs. Make missed or incorrect facts inspectable and correctable without deleting private originals. |
| NPC continuity | [Patch Notes 25.41 — NPC Memory + Planning](https://fables.gg/patch-notes/patch-notes-2541-npc-memory-planning) (2025-10-08) says memories are tagged to characters who should know them. Direct conversation retrieves that NPC's most recent 20 memories into a character-specific planning step. It acknowledges that context blocks alone had not solved NPC forgetting. | Track which NPC witnessed or learned a fact, rather than letting every NPC know the whole campaign. Test return visits and ongoing relationships. The documented number 20 is an implementation detail, not an appropriate default proven for a local 8B model. |
| Explicit references | [Mentions](https://help.fables.gg/en/articles/8309909-mentions) describes `@` mentions that force an entity's details into the request. | Preserve unrestricted prose input while offering an optional way to disambiguate an NPC, place or spell. Explicit reference should complement automatic retrieval. |

[Memories V2](https://fables.gg/patch-notes/memories-v2) (2025-06-03) documents text embeddings/vector search and character/location links. Some of its other rules were later superseded: for example, it said memories were not editable, while [Franz 2.0](https://fables.gg/patch-notes/franz-20-working-context-lore-improved-planning-and-more) (2025-08-28) introduced editable long-term memories and a rewritten plot. Old notes should not be combined into an imaginary single feature set.

## Player agency and story pacing

[Patch Notes 25.39 — Plot & Plan Changes](https://fables.gg/patch-notes/patch-notes-2540-plot-and-plan-changes) (2025-10-06; the URL contains `2540` but the article is titled 25.39) moved planning to **after the player's current message**, immediately before narration. The plan is regenerated and discarded each turn. Their stated goal is to make Franz feel less railroady. This supersedes the August 2.0 description of an editable plan written at the end of the previous turn.

[Narration Module Upgrade 1.0 → 1.1](https://fables.gg/patch-notes/narration-module-upgrade-10-greater-11) (2025-02-16) describes livelier independent NPC interactions, more natural dialogue and situation-dependent length: longer when introducing a new place, shorter when an NPC is waiting for the player's answer. These are documented design goals, not measured results from our session.

[Pacing Mode](https://help.fables.gg/en/articles/9016188-pacing-mode) distinguishes Adventure, which encourages exploration and quests, from Downtime, which supports relaxed slice-of-life play. [A World Builder's Guide on Quest Building](https://help.fables.gg/en/articles/5272490-a-world-builders-guide-on-quest-building) describes authored scenes, locations, GM instructions, triggers and branching outcomes based on player choices. That guide contains older references to on-the-fly quest generation; the later 2.0 release explicitly says that feature was removed in favor of authored quests and narrative plot handling.

**No public source reviewed establishes that Fables never invents the player's speech, thoughts or voluntary actions.** Its general claims about adaptation and reduced railroading do not constitute that guarantee. Storyforge's stronger player-ownership contract comes from this project's user and `AGENTS.md`.

**Storyforge direction:** react to exactly what the player submitted; let NPCs and external events create initiative; stop before the next unchosen PC response or decision. Keep opening setup, pending goals and completed events distinct. For the Hogwarts regression, arriving at Hogsmeade is accepted scene state; future Sorting is a pending event, and the player's house choice remains open. No recurring plan may silently decide it.

## Repetition, corrections and apparent model misbehavior

[ACE 1.5.4 — Style Adjustments](https://fables.gg/patch-notes/ace-154-style-adjustments) (2025-08-19) confirms the reference already mentioned in Storyforge's README: model output tends to repeat patterns from recent messages; their advice was to edit the unwanted pattern out of recent messages or retry. Its claim that corrections were not saved is historical and was changed by later releases.

[Franz 2.0.1](https://fables.gg/patch-notes/franz-201-better-ooc-correction-handling-lore-sync) (2025-09-18) and [How to fix Franz and get your campaign back on track](https://help.fables.gg/en/articles/1581604-how-to-fix-franz-and-get-your-campaign-back-on) describe correction handling that updates context and relevant state. The help article recommends inspecting plot/context for incorrect facts, checking scene descriptions that provoke repetition, and editing/deleting prolonged arguments because those arguments displace useful recent story context.

That help article also says different language models have tendencies that may resist prompting. [Custom Instructions](https://help.fables.gg/en/articles/8680638-custom-instructions) distinguishes narration style instructions from implemented mechanics/tools: text instructions cannot create database lookup capabilities or reliable state tracking that the engine lacks. It recommends concise, focused positive instructions.

**Storyforge direction:** diagnose repeated scene facts, rejected drafts and stale context as well as repeated text. Store correction intent separately from the narrative, exclude rejected output from future canon, preserve drafts on failure, and make correction/rewind atomic. More negative prompt rules alone are unlikely to solve the Qwen issues.

## Model choices and the local-only requirement

[What models do you use?](https://help.fables.gg/en/articles/5728392-what-models-do-you-use) describes multiple model families plus custom fine-tunes and says the selection changes over time. [Available LLM Models](https://help.fables.gg/en/articles/3993355-available-llm-models), as retrieved, lists Fenix and MiMo as standard narration options and GLM 4.7/Gemini 3 Pro as premium options. These lists are dated public documentation, not a live provider inventory. That article explicitly says switching narration model does **not** change research or game mechanics.

The transferable lesson is a clean local model interface and evidence-based model selection, not a requirement to subscribe to a cloud model or assume access to Fables' internal models. Benchmark available local candidates against the same player-agency, scene-replay, lore-conflict, correction, NPC-return and malformed-output fixtures. Record latency and output quality separately. Successful mocked HTTP/unit tests cannot establish real Qwen storytelling quality or GPU responsiveness.

## Scope of incorporation

For the current GM/continuity priority, the strongest independently implementable ideas are:

1. Compact, inspectable working context with explicit scene/accepted-history/lore boundaries and source provenance.
2. Response generation conditioned on the latest player input, with no persistent plan that dictates PC choices.
3. Durable, source-linked scene/NPC memory built only from accepted turns, with safe rewind behavior.
4. Model-specific structured output, measured local evaluation and bounded correction attempts.
5. Varying narrative length with the situation and allowing NPC/world initiative without performing the player's next action.

The [homepage](https://fables.gg/) also advertises maps, tactical 5e combat, multiplayer, authored quests, travel, character voices and image generation. These are broader product features; they do not need to be added to solve the user's current GM problems. Storyforge already has free-form play, worlds/characters, lore import/preview, message corrections, saved artwork, narration and ambience. Preserve these features and private saved data while improving the engine. Full parity, a recreated proprietary narrator, and identical live behavior have not been demonstrated or promised.
