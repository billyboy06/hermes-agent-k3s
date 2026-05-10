---
name: gpu-contention-check
description: Detect whether the station IA GPU (R9700) is already busy with another workload (ComfyUI, llama.cpp, fine-tuning) before loading a new model via ia-commander. Returns a clear verdict the caller can act on.
version: 0.1.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [infra, gpu, contention, station-ia]
    category: infra
---

# gpu-contention-check

Determines whether it's safe to switch ia-commander to a new variant on the AI station, or whether another GPU-using workload is already running.

## When to use

Right after `station-power-management` acquire, before issuing `POST /switch/<variant>` to ia-commander. Without this check, switching the variant would kill an in-progress ComfyUI render or fine-tuning job (ia-commander enforces mutual exclusion at the service level — see memory note `ia-commander-http-api.md`).

## Inputs

- `variant_target` (string) — the variant we want to switch to (e.g. `qwen36-mtp`). Used to short-circuit if it's already loaded.

## Outputs

- `verdict` — one of `"free"`, `"already-loaded"`, `"busy"`
- `reason` — human-readable explanation
- `defer_minutes` — recommended retry delay if `busy` (default 60)

## Decision logic

The skill queries three independent signals and combines them:

### Signal 1: ia-commander state

GET `http://192.168.1.20:8090/status`.

- `{"active": false}` → ia-commander has nothing loaded. Doesn't mean GPU is free (ComfyUI bypasses ia-commander) but it's necessary, not sufficient.
- `{"active": {"variant_id": <variant_target>}}` → already the right variant loaded. Verdict `already-loaded`, caller can skip the switch.
- `{"active": {"variant_id": <other>}}` → another ia-commander variant is loaded. If that variant is `comfyui/*`, treat as busy. If it's another `llamacpp/*` variant, switching is acceptable (we'll replace it).

### Signal 2: ROCm VRAM usage

SSH `rocm-smi --showmeminfo vram --json` on the station as user `mxtt` :
`ssh -o ConnectTimeout=5 mxtt@192.168.1.20 "rocm-smi --showmeminfo vram --json"`
Use the existing key at `~/.ssh/id_ed25519` (passwordless auth is configured). Never use `root@`. Never try password auth.

- VRAM used > 2 GB on GPU 0 → likely an active workload, even if ia-commander says `active:false`. Could be a ComfyUI invoked outside ia-commander, a Python script, or a fine-tuning job.
- VRAM used ≤ 2 GB → considered free.

### Signal 3: ComfyUI port liveness

SSH as user `mxtt` :
`ssh -o ConnectTimeout=5 mxtt@192.168.1.20 "curl -sS -m 2 http://localhost:8188/queue 2>&1 | jq -r '.queue_running | length'"`

- Result > 0 → a render is in progress. Verdict `busy` regardless of other signals.
- Result == 0 or connection refused → no active queue. Doesn't mean ComfyUI isn't loaded in VRAM (idle), but signals no current job.

### Combination

| ia-commander | VRAM > 2GB | ComfyUI queue | Verdict |
|---|---|---|---|
| target variant loaded | * | empty | `already-loaded` |
| other llamacpp variant | * | empty | `free` (switch is OK) |
| other comfyui variant | * | * | `busy` (don't kill render) |
| `active:false` | ≤ 2 GB | empty/none | `free` |
| `active:false` | > 2 GB | empty | `busy` (unknown workload) |
| any | any | running | `busy` |

## Constraints

- **Never kill ComfyUI**: per memory note `feedback_comfyui_no_global_kill`, the user has UI workflows in progress. A `busy` verdict from ComfyUI must always be respected.
- **Conservative by default**: if any signal returns an error/timeout, treat as `busy` rather than risking data corruption.
- **Read-only**: this skill never changes state on the station, only observes.

## Tools used

- `terminal` — for `ssh`, `curl`, `jq`.

## Defer signal

When verdict is `busy`, the parent skill should:

1. Log the reason (which signal flagged).
2. Reschedule the task in `defer_minutes` (default 60).
3. If the station was woken up by the parent (`we_powered_it=true` from `station-power-management`), shut it down before deferring (don't waste energy on an idle wake).

## See also

- [[station-power-management]] — call before this skill
- Memory: `ia-commander-http-api.md`, `feedback_comfyui_no_global_kill.md`, `feedback_rocm_expandable_segments.md`
