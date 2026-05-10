# Mock ia-commander

Mini serveur FastAPI qui mime le daemon Rust ia-commander (192.168.1.20:8090) pour permettre les tests Hermes en **local Mac (path A)** sans dépendre de la station IA.

## À quoi ça sert

Path A des tests Hermes (`TEST-LOCAL.md`) = Hermes installé en bare-metal sur Mac, avec config pointant vers `claude-code-server` pour le LLM. Mais les **skills** dealradar appellent ia-commander via curl pour `/switch/<variant>`, `/status`, `/v1/chat/completions`, etc. Ce mock répond comme le vrai daemon, sans charger un modèle local.

## Installation

```bash
cd ~/projects/hermes-agent-k3s/mock-ia-commander
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Lancement

```bash
export CLAUDE_CODE_SERVER_URL=https://openai-claude.fripp.fr
export CLAUDE_CODE_SERVER_KEY=$(grep '^CLAUDE_CODE_SERVER_API_KEY' $HOME/.secrets.env | cut -d= -f2-)

uvicorn server:app --host 0.0.0.0 --port 8090
```

Endpoints exposés :
- `GET /health`
- `GET /status` → `{"active": false}` au boot, `{"active": {variant_id,...}}` après switch
- `GET /variants` → liste statique avec `qwen36-mtp` inclus
- `POST /switch/<variant>` → met à jour le state local (instantané, pas de vrai chargement)
- `GET /v1/models` → liste OpenAI-compat
- `POST /v1/chat/completions` → **forward vers claude-code-server** (nettoyage du `model` field)
- `POST /v1/completions` / `POST /v1/embeddings` → idem forward

## Config Hermes pointant vers ce mock

Édit `~/.hermes/config.yaml` :

```yaml
model:
  provider: main
  model: qwen36-mtp
  base_url: http://localhost:8090/v1
  request_timeout_seconds: 600

auxiliary:
  vision:
    provider: main
    model: qwen36-mtp
    base_url: http://localhost:8090/v1
```

Hermes appelle le mock, qui forward Claude par-derrière. Du point de vue des skills (qui parlent à `http://localhost:8090`), tout est strictement compatible avec le vrai ia-commander.

## Variables d'env utiles

- `CLAUDE_CODE_SERVER_URL` (requis) — URL du serveur Claude (default: `https://openai-claude.fripp.fr`)
- `CLAUDE_CODE_SERVER_KEY` (requis) — API key
- `MOCK_DEFAULT_VARIANT` (optionnel, default `qwen36-mtp`) — variant default retourné par `/variants`
- `MOCK_GPU_BUSY` (optionnel, set à `1`) — simule un GPU busy : `/switch/...` retourne 503. Utile pour tester le fallback `dealradar-triage` (defer +1h).

## Cas de test

| Scénario | Action | Résultat attendu |
|---|---|---|
| Boot normal | `curl http://localhost:8090/status` | `{"active": false}` |
| Switch | `curl -X POST http://localhost:8090/switch/qwen36-mtp` | `{"status":"ready","variant_id":"qwen36-mtp"}` |
| Re-status après switch | `curl http://localhost:8090/status` | `{"active":{"variant_id":"qwen36-mtp",...}}` |
| Inférence | `curl -X POST http://localhost:8090/v1/chat/completions -d '{"model":"qwen36-mtp","messages":[{"role":"user","content":"hello"}]}'` | Réponse Claude (forwardée) |
| GPU busy simulé | `MOCK_GPU_BUSY=1 uvicorn ...` puis `curl -X POST http://localhost:8090/switch/qwen36-mtp` | HTTP 503 |

## Limites

- **Pas de vrai chargement modèle** : `switch` est instantané. Pour tester le timing de chargement réel (10–30s), utiliser le vrai ia-commander sur la station IA.
- **Pas de vraie vision** : Claude (Opus 4) supporte la vision via image_url comme Qwen, donc les skills vision-aware fonctionnent. Mais le comportement exact peut différer (Claude vs Qwen vision).
- **Pas de mutual exclusion réelle** : le mock n'arrête pas ComfyUI (puisqu'il n'y en a pas en local). Pour tester `gpu-contention-check`, utiliser `MOCK_GPU_BUSY=1`.
- **Pas de Vulkan/MTP timing** : le mock ne reproduit pas la latence MTP (+20-50% throughput). Pour bencher, attendre le vrai déploiement.

## Quand l'arrêter / le retirer

Une fois qwen36-mtp opérationnel sur la station IA et la station accessible depuis le pod Hermes (via cluster network), retirer le mock et pointer Hermes config vers `http://192.168.1.20:8090/v1` (le vrai). Ce mock reste utile pour les tests offline et regression.
