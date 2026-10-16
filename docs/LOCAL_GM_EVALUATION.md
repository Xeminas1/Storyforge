# Local GM evaluation — v0.15.0

The user approved pushing this update with "push this update please" on 2026-10-16, superseding the earlier local-only freeze for v0.15.0. Release preparation is underway; publication is not yet confirmed here. Run these commands from the updated checkout or installed v0.15.0 after publication; the older v0.14.0 ZIP does not contain them. README includes the essential instructions because this document is excluded from release ZIPs. This approval covers the current update, not unrelated future releases.

## What changed

Storyforge previously allowed independent slices of character, ability, state and history text to exceed its configured 8,192-token window. It also cut JSON strings mid-field and kept the beginning of an old reply while losing its final scene outcome. A populated valid campaign reached about 39,300 characters before output; a representative campaign sent 20,393.

The new composer builds complete JSON objects and uses a 16,000 UTF-8-byte message budget with space reserved for one corrective request. Full creator premise, identity/weaknesses, complete explicitly requested ability rules and the latest scene handoff precede optional biography, inventory and older history. The byte count is a conservative portable estimate, not exact model tokenization. Essential records that cannot fit cause a clear pre-request error rather than silent loss of rules.

The model receives a typed JSON Schema. Proposed location, inventory and journal changes need exact supporting text from the visible prose body; a header or unrelated sentence is insufficient. Optional scene/NPC/event/pending-thread working memory also requires visible evidence. It shares existing state checkpoints, so retries restore the correct working memory. Removing a remembered fact also removes that exact fact from rewind snapshots, preserving unrelated history.

The Journal and Relationships views expose remembered facts with removal controls. These are observed notes, not automatic numeric relationship scores. Removing a note leaves story messages unchanged; retry the source turn to change the story.

These checks enforce code boundaries and evidence links. They cannot prove that arbitrary generated prose is semantically correct or fully honors player agency. Live model evaluation remains necessary.

## Run without touching saves

Start Ollama as usual. In PowerShell, from the updated Storyforge checkout:

```powershell
py server.py --evaluate-model qwen3:8b --repeat 1 --report data/model-check-qwen-v015.json
```

The command uses disposable synthetic campaigns and does not launch Storyforge's server/updater, open personal campaign data, install a model or change the selected model. It refuses to overwrite an existing report; choose a new filename on another run.

There are ten fixtures: player observation, authorized smile/continuation, player dialogue, NPC dialogue, spell limitations, Hogwarts opening, established Hogwarts scene, creator/reference conflict, scene repetition and later-turn retry. A forced failure probe separately verifies preservation of a disposable campaign.

Reports include generated synthetic prose, rejected drafts, exact synthetic prompts, timings and numeric transport diagnostics. Read the manual-review questions for each case. `completed` means the pipeline accepted the response, not that the story quality or player agency was proven correct. Transport failures stop the remaining cases for that model, which are marked `not_run`.

When supported by the local Ollama APIs, reports also record its version and the selected model's digest, quantization, parameter size, declared context length and capabilities. Metadata lookup is bounded and optional; unavailable endpoints do not suppress the gameplay cases. It excludes model templates, system prompts and the names of other installed models. The declared maximum context is distinct from the 8,192-token context configured for a Storyforge request.

With no Ollama in the cloud machine, a real attempt correctly reported a connection failure and left the remaining nine scenarios unrun. No claim of successful live Qwen behavior follows from unit or scripted-HTTP tests.

## Compare installed models

First identify actual local versions and GPU use:

```powershell
ollama --version
ollama list
ollama show qwen3:8b
ollama ps
nvidia-smi
```

To compare another model already installed on your machine:

```powershell
py server.py --evaluate-model qwen3:8b --evaluate-model qwen3:14b --repeat 3 --report data/model-comparison-v015.json
```

This is an example, not an instruction to download or use an unavailable model. Three repeats across two models can take many minutes. Compare the same fixtures and review both accepted and rejected attempts. Separate cold model load, prompt processing and generation time. Keep optional image-generation jobs idle while establishing a baseline so GPU competition does not obscure the result.

A quantized 14B model is a reasonable quality-comparison candidate on a 16GB GPU when other jobs are idle; it has not been proven better for this campaign. A model's active-parameter count does not equal weight-storage requirements: a 30B MoE can still exceed practical fully resident memory after weights, KV cache and runtime overhead. System RAM permits offload but does not provide GPU-like inference speed.

## Sources and decisions

- [Official Ollama structured outputs](https://github.com/ollama/ollama/blob/d919272e53593d1d55d40e1180eaa06dfbede3ac/docs/capabilities/structured-outputs.mdx): `format` can be a JSON Schema; returned data still needs validation.
- [Official Qwen3 quickstart](https://github.com/QwenLM/Qwen3/blob/7a2f61ffc7a20d47efcd2bf97f6f2bf52729042e/docs/source/getting_started/quickstart.md): original non-thinking baseline is temperature 0.7, top_p 0.8, top_k 20 and min_p 0; greedy decoding can worsen repetition. This baseline is applied to the known `qwen3:8b` tag, not silently to every variant.
- [Official Qwen3 model/mode documentation](https://github.com/QwenLM/Qwen3/blob/7a2f61ffc7a20d47efcd2bf97f6f2bf52729042e/README.md): aliases and thinking support vary; verify exact model identity.
- [Official Ollama context documentation](https://github.com/ollama/ollama/blob/d919272e53593d1d55d40e1180eaa06dfbede3ac/docs/context-length.mdx) and [memory/concurrency guidance](https://github.com/ollama/ollama/blob/d919272e53593d1d55d40e1180eaa06dfbede3ac/docs/faq.mdx): configured context and parallelism affect memory and latency.
- [Fables research](FABLES_RESEARCH.md): official product documentation supports targeted context, entity-linked memory and separate state processing. This is independent adaptation for a local GPU, not a reproduction of Fables' private narrator or a promise of identical behavior.
