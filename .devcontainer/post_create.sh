#!/usr/bin/env bash
set -eux

# System dependencies
sudo apt update -y
xargs sudo apt install -y < apt-system-deps.txt

# Bootstrapping mise
mise trust && mise install
SNIPPET_ZSH="eval \"\$(mise activate zsh)\""
echo "$SNIPPET_ZSH" >> /root/.zshrc
mise run bootstrap
mise use node

# Other sys deps
npm install -g rtlcss
install-wkhtmltopdf

# Install Claude Code
curl -fsSL https://claude.ai/install.sh | bash