# hermes-agent-k3s

Hermes Agent (NousResearch, MIT) packaged for k3s with custom skills for the dealradar pipeline.

## Image

`ghcr.io/billyboy06/hermes-agent:0.13.0` — built by GitHub Actions on push.

## Layout

```
docker/Dockerfile               Base image: Python 3.11 + Hermes Agent + ssh/curl/jq/wakeonlan/sshpass
skills/                         16 custom skills (agentskills.io format)
mock-ia-commander/              FastAPI mock for local Hermes tests
test/acp-client.py              ACP JSON-RPC client to drive Hermes scripted
deploy.sh                       k3s install: secrets + helm + skills push
.github/workflows/build.yml     CI build amd64 image, push ghcr.io
```

The Helm chart lives separately in `~/k3s-media-charts/ai/hermes-agent/`.

## Deploy to k3s

```
TELEGRAM_BOT_TOKEN=8xxxxx:ABC... TELEGRAM_CHAT_ID=12345 ./deploy.sh
```

The script creates secrets, helm-installs, copies skills into PVC, verifies pod ready.

## Backend models

- **Main**: `qwen36` on station IA via ia-commander (`http://192.168.1.20:8090/v1`)
- **Fallback**: claude-code-server (configured in `chart/values-test.yaml`)

## See also

- Source: `github.com/billyboy06/dealradar` — backend FastAPI + scrapers
- Helm chart: `github.com/billyboy06/k3s-media-charts/tree/master/ai/hermes-agent`
- Spec: `~/projects/firesale-detector/spec/v2.8-extensions.md`
