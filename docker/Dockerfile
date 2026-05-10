FROM python:3.11-slim-bookworm

# Tools required by skills (terminal tool exec)
# - curl/jq : HTTP calls to ia-commander, dealradar API
# - openssh-client : ssh to station IA (192.168.1.20)
# - wakeonlan : WoL station IA (MAC 30:56:0f:40:1e:44)
# - sshpass : non-interactive sudo on station (password 4147)
# - iputils-ping : liveness check
# - git : Hermes Agent install requires git
# - ca-certificates : HTTPS
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl \
      jq \
      openssh-client \
      wakeonlan \
      sshpass \
      iputils-ping \
      git \
      ca-certificates \
      bash \
      xz-utils \
      ripgrep \
    && rm -rf /var/lib/apt/lists/*

# uv (Python package manager required by Hermes installer)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/uv

# Hermes Agent install (skip interactive setup wizard)
ENV HERMES_SKIP_SETUP=1
RUN curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh \
      | bash -s -- --skip-setup

# Persistent state directory mounted as PVC
ENV HERMES_HOME=/root/.hermes
VOLUME ["/root/.hermes"]

# PATH for hermes binary
ENV PATH=/root/.local/bin:$PATH

# SSH key directory (mounted secret in k8s for station IA access)
RUN mkdir -p /root/.ssh && chmod 700 /root/.ssh

WORKDIR /root

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD pgrep -f "hermes" >/dev/null || exit 1

# Default command: run Hermes gateway in foreground (Telegram/Discord/etc.)
CMD ["hermes", "gateway", "run"]
