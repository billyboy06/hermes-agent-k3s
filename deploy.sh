#!/usr/bin/env bash
# Deploy Hermes Agent to k3s namespace ai
# Usage: TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=xxx ./deploy.sh

set -euo pipefail

KUBE="${KUBECONFIG:-$HOME/.kube/k3s-proxmox-config.yaml}"
NS=ai

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
  echo "ERROR: set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars"
  exit 1
fi

# Claude Code Server key — pour le moment Hermes utilise qwen36 via ia-commander.
# Cette clé sert au mode test/fallback uniquement.
CLAUDE_KEY=$(grep '^CLAUDE_CODE_SERVER_API_KEY' "$HOME/.secrets.env" | cut -d= -f2-)

# 1. Secret SSH (clé privée pour mxtt@192.168.1.20)
echo "==> creating hermes-ssh-key secret"
kubectl --kubeconfig="$KUBE" create secret generic hermes-ssh-key \
  -n "$NS" \
  --from-file=id_ed25519="$HOME/.ssh/id_ed25519" \
  --from-file=id_ed25519.pub="$HOME/.ssh/id_ed25519.pub" \
  --from-file=known_hosts="$HOME/.ssh/known_hosts" \
  --dry-run=client -o yaml | kubectl --kubeconfig="$KUBE" apply -f -

# 2. Secret runtime (Telegram + Claude + SSH password)
echo "==> creating hermes-secrets secret"
kubectl --kubeconfig="$KUBE" create secret generic hermes-secrets \
  -n "$NS" \
  --from-literal=TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
  --from-literal=TELEGRAM_CHAT_ID="$TELEGRAM_CHAT_ID" \
  --from-literal=STATION_SUDO_PASSWORD="4147" \
  --from-literal=CLAUDE_CODE_SERVER_API_KEY="$CLAUDE_KEY" \
  --from-literal=OPENAI_API_KEY="$CLAUDE_KEY" \
  --dry-run=client -o yaml | kubectl --kubeconfig="$KUBE" apply -f -

# 3. Helm install
echo "==> helm upgrade --install hermes"
helm --kubeconfig="$KUBE" upgrade --install hermes \
  "$HOME/k3s-media-charts/ai/hermes-agent/" \
  --namespace "$NS" \
  --set "secrets.telegramBotToken=__from_secret__" \
  --set "secrets.telegramChatId=__from_secret__" \
  --set "image.repository=ghcr.io/billyboy06/hermes-agent" \
  --set "image.tag=0.13.0" \
  --wait --timeout=5m

# 4. Wait for pod ready
echo "==> waiting for hermes pod ready"
kubectl --kubeconfig="$KUBE" wait --for=condition=ready pod \
  -l app=hermes -n "$NS" --timeout=180s

# 5. Push the 16 skills into PVC
echo "==> copying 16 custom skills into PVC"
HERMES_POD=$(kubectl --kubeconfig="$KUBE" get pod -l app=hermes -n "$NS" -o jsonpath='{.items[0].metadata.name}')
kubectl --kubeconfig="$KUBE" exec -n "$NS" "$HERMES_POD" -- mkdir -p /root/.hermes/skills/business
for skill in "$HOME/.hermes/skills/business"/*; do
  name=$(basename "$skill")
  kubectl --kubeconfig="$KUBE" cp "$skill" "$NS/$HERMES_POD:/root/.hermes/skills/business/$name"
  echo "  + $name"
done

# 6. Verify gateway running + skills detected
echo "==> verify deployment"
kubectl --kubeconfig="$KUBE" exec -n "$NS" "$HERMES_POD" -- hermes skills list 2>&1 | grep -E "dealradar|station-power|gpu-cont" | head

echo
echo "OK — Hermes deployed. Send a message to your bot to test."
