---
name: station-power-management
description: Wake the AI station (192.168.1.20) via WoL if it's off, run a task, then shut it down only if we were the ones who woke it up. Reusable by any skill needing the station GPU (dealradar, Frankie pipeline, etc.).
version: 0.1.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [infra, power, wol, station-ia]
    category: infra
required_environment_variables:
  - STATION_SUDO_PASSWORD
---

# station-power-management

Manages power lifecycle of the AI station (Ubuntu host at 192.168.1.20, R9700 32GB GPU) so callers can use it on-demand without leaving it running 24/7.

## When to use

Any time a skill needs the station IA GPU (ComfyUI, llama.cpp via ia-commander) and wants to leave the host in the same state it found it. Typical callers:

- `dealradar-triage` — Phase A inference cycle every 15 min in time windows
- Frankie content pipeline — Wan 2.2 video generation, Flux image batch
- Future: ad-hoc inference, fine-tuning sessions

## Inputs

- `task_id` (string, optional) — for logging the wake/shutdown transitions, useful if multiple skills share the station

## Outputs

- `state_before` — `"on"` or `"off"` (the state observed at entry)
- `we_powered_it` — `true` if WoL was triggered, `false` otherwise
- `success` — boolean

## Procedure (acquire phase)

1. Probe SSH liveness on `mxtt@192.168.1.20` with a 3-second timeout (BatchMode, no password prompt).
2. If alive → set `state_before = "on"`, `we_powered_it = false`, return success.
3. If not alive →
   - Send a magic packet via `wakeonlan 30:56:0f:40:1e:44`.
   - Poll SSH every 5 seconds for up to 120 seconds.
   - On success → set `state_before = "off"`, `we_powered_it = true`.
   - On timeout → return failure (caller should defer the task).

## Procedure (release phase)

Called explicitly by the parent skill at the end of its work, with `we_powered_it` from the acquire phase.

1. If `we_powered_it = true` → SSH `sudo shutdown -h now` using `sshpass -p $STATION_SUDO_PASSWORD`. Don't wait for confirmation; the connection drops as the host powers off.
2. If `we_powered_it = false` → leave the station alone (the user may be using it).

## Constraints

- **Never shutdown unconditionally**: if the user was already on the station (e.g. doing ComfyUI work), shutting it down would interrupt them. The `we_powered_it` flag is the authoritative signal.
- **Never WoL more than once per cycle**: if the wake fails after 120 s, escalate to the caller (likely a hardware/network issue).
- **Idempotent acquire**: calling acquire when station is already on returns `we_powered_it = false`, no side effect.
- **Sudo password from secret**: never hardcoded; sourced from `STATION_SUDO_PASSWORD` env var injected by k8s secret.

## Tools used (Hermes runtime)

- `terminal` — for `ssh`, `wakeonlan`, `sshpass` shell invocations.

## Failure modes & defer signals

| Symptom | Caller action |
|---|---|
| WoL sent, host still unreachable after 120 s | Defer task by 1 hour, log the wake-failure |
| SSH connects but shutdown command fails | Continue; the station stays on, user can shut down manually |
| Station physically off and WoL not configured at BIOS | Out of scope, infra issue |

## Example invocation flow

A caller (`dealradar-triage`) executes this skill in two phases. Acquire at the start of the cycle, release at the end. The state from acquire is passed back to release.

## See also

- [[gpu-contention-check]] — call after acquire, before loading a model, to detect if another GPU workload is already running
- Memory note: `~/.claude/projects/-Users-matthi/memory/flywheel-master-plan.md` for the broader station/k3s topology
