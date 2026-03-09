# odoo-shell-aliases.fish — Odoo development shell functions (Fish)
# Source this file from your ~/.config/fish/config.fish:
#
#   source /path/to/odoo-env/scripts/odoo-shell-aliases.fish
#
# Requires an active odoo-env shell (ODOO_PATH must be set).

function _odoo_check_env
    if not set -q ODOO_PATH
        echo "[odoo-aliases] Not in an odoo-env shell. Run: odoo-env activate <env>" >&2
        return 1
    end
end

# Launch Odoo server
function oo
    _odoo_check_env || return
    $ODOO_PATH/odoo-bin -c $ODOO_RC $argv
end

# Launch Odoo with test runner
function otest
    _odoo_check_env || return
    $ODOO_PATH/odoo-bin -c $ODOO_RC --test-enable --stop-after-init $argv
end

# cd to community worktree
function ocd
    _odoo_check_env || return
    cd $ODOO_PATH
end

# cd to enterprise worktree
function ocd-e
    _odoo_check_env || return
    if not set -q ODOO_ENTERPRISE_PATH; or test -z "$ODOO_ENTERPRISE_PATH"
        echo "[odoo-aliases] No enterprise worktree in current env" >&2
        return 1
    end
    cd $ODOO_ENTERPRISE_PATH
end

# Switch to another environment without nesting shells
function oact
    exec odoo-env activate $argv
end

# Print current environment summary
function oenv
    _odoo_check_env || return
    echo "ODOO_VERSION:    $ODOO_VERSION"
    echo "ODOO_PATH:       $ODOO_PATH"
    echo "ODOO_PORT:       $ODOO_PORT"
    echo "ODOO_RC:         $ODOO_RC"
    if set -q ODOO_ENTERPRISE_PATH; and test -n "$ODOO_ENTERPRISE_PATH"
        echo "ODOO_ENTERPRISE_PATH: $ODOO_ENTERPRISE_PATH"
    end
    if set -q ODOO_EXTRA_PATHS; and test -n "$ODOO_EXTRA_PATHS"
        echo "ODOO_EXTRA_PATHS: $ODOO_EXTRA_PATHS"
    end
end
