# odoo-shell-aliases.fish — Odoo development shell functions (Fish)
# Source this file from your ~/.config/fish/config.fish:
#
#   source /path/to/odoo-env/scripts/odoo-shell-aliases.fish
#
# Requires an active odoo-env shell (ODOO_PATH must be set).

function _odoo_check_env
    if not set -q ODOO_PATH
        echo "[odoo-aliases] Not in an odoo-env shell. Run: odoo-env <env-name>" >&2
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

# Run git in community worktree
function ogit
    _odoo_check_env || return
    git -C $ODOO_PATH $argv
end

# Tail Odoo log (reads log_file from odoorc)
function olog
    _odoo_check_env || return
    set logfile (python3 -c "
import configparser, os
c = configparser.ConfigParser()
c.read(os.environ['ODOO_RC'])
print(c.get('options', 'logfile', fallback=''))
" 2>/dev/null)
    if test -n "$logfile"
        tail -f $logfile
    else
        echo "[odoo-aliases] No logfile configured in \$ODOO_RC" >&2
    end
end

# psql with Odoo DB settings
function odb
    _odoo_check_env || return
    python3 -c "
import configparser, os
c = configparser.ConfigParser()
c.read(os.environ['ODOO_RC'])
opts = c['options'] if 'options' in c else {}
host = opts.get('db_host', 'localhost')
port = opts.get('db_port', '5432')
user = opts.get('db_user', 'odoo')
pw   = opts.get('db_password', '')
db   = os.environ.get('argv1', opts.get('db_name', ''))
import subprocess, os as _os
env = _os.environ.copy()
env['PGPASSWORD'] = pw
subprocess.run(['psql', '-h', host, '-p', port, '-U', user, db], env=env)
" argv1=(test (count $argv) -gt 0; and echo $argv[1]; or echo '')
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
