FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    HERMES_HOME=/root/.hermes \
    GBRAIN_HOME=/root \
    BUN_INSTALL=/usr/local/bun \
    PATH=/root/.local/bin:/usr/local/bin:/usr/local/bun/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        bash \
        python3 \
        python3-pip \
        python3-venv \
        build-essential \
        pkg-config \
        ripgrep \
        ffmpeg \
        nodejs \
        npm \
        unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Hermes Agent from https://github.com/NousResearch/hermes-agent.
# --skip-setup avoids the interactive wizard during image build; run `hermes setup`
# manually from an interactive shell after adding env vars/API keys.
RUN curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh \
    | bash -s -- --skip-setup --skip-browser

# Install GBrain from https://github.com/garrytan/gbrain.
# Use the documented git clone + bun link flow; do not use bun global install.
RUN curl -fsSL https://bun.sh/install | bash \
    && ln -sf /usr/local/bun/bin/bun /usr/local/bin/bun \
    && git clone https://github.com/garrytan/gbrain.git /usr/local/lib/gbrain \
    && cd /usr/local/lib/gbrain \
    && bun install \
    && bun link \
    && ln -sf /usr/local/bun/bin/gbrain /usr/local/bin/gbrain

WORKDIR /workspace

COPY setup/docker/entrypoint.sh /usr/local/bin/hermes-entrypoint.sh
RUN chmod +x /usr/local/bin/hermes-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/hermes-entrypoint.sh"]
