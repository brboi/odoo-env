FROM debian:bookworm-slim

# Dépendances de base
RUN apt-get update && apt-get install -y \
    git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Installer mise
RUN curl https://mise.run | sh
ENV PATH="/root/.local/bin:$PATH"
ENTRYPOINT ["sleep", "infinity"]
