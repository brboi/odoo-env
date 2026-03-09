# odoo-shell-aliases.sh — Odoo development shell functions
# Source this file from your ~/.bashrc or ~/.zshrc:
#
#   source /path/to/odoo-env/scripts/odoo-shell-aliases.sh
#
# Requires an active odoo-env shell (ODOO_PATH must be set).

_odoo_check_env() {
    if [ -z "$ODOO_PATH" ]; then
        echo "[odoo-aliases] Not in an odoo-env shell. Run: odoo-env activate <env>" >&2
        return 1
    fi
}

# Launch Odoo server
oo() {
    _odoo_check_env || return 1
    "$ODOO_PATH/odoo-bin" -c "$ODOO_RC" "$@"
}

# Launch Odoo with test runner
otest() {
    _odoo_check_env || return 1
    "$ODOO_PATH/odoo-bin" -c "$ODOO_RC" --test-enable --stop-after-init "$@"
}

# cd to community worktree
ocd() {
    _odoo_check_env || return 1
    cd "$ODOO_PATH"
}

# cd to enterprise worktree
ocd-e() {
    _odoo_check_env || return 1
    if [ -z "$ODOO_ENTERPRISE_PATH" ]; then
        echo "[odoo-aliases] No enterprise worktree in current env" >&2
        return 1
    fi
    cd "$ODOO_ENTERPRISE_PATH"
}

# Switch to another environment without nesting shells
oact() {
    exec odoo-env activate "$@"
}

# Print current environment summary
oenv() {
    _odoo_check_env || return 1
    echo "ODOO_VERSION:    $ODOO_VERSION"
    echo "ODOO_PATH:       $ODOO_PATH"
    echo "ODOO_PORT:       $ODOO_PORT"
    echo "ODOO_RC:         $ODOO_RC"
    [ -n "$ODOO_ENTERPRISE_PATH" ] && echo "ODOO_ENTERPRISE_PATH: $ODOO_ENTERPRISE_PATH"
    [ -n "$ODOO_EXTRA_PATHS" ] && echo "ODOO_EXTRA_PATHS: $ODOO_EXTRA_PATHS"
}

# Show odoo-env indicator in shell prompt
if [ -n "$ODOO_ENV_NAME" ]; then
    if [ -n "$ZSH_VERSION" ]; then
        PROMPT="(odoo:${ODOO_ENV_NAME}) ${PROMPT}"
    else
        PS1="(odoo:${ODOO_ENV_NAME}) ${PS1}"
    fi
fi
