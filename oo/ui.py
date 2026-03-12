"""Terminal output utilities."""
import sys

RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
NC = "\033[0m"


def hyperlink(text: str, url: str) -> str:
    """Wrap text as an OSC 8 terminal hyperlink (ctrl-click in most modern terminals)."""
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"


def log_info(msg: str) -> None:
    print(f"{BLUE}[INFO]{NC} {msg}", file=sys.stderr)


def log_ok(msg: str) -> None:
    print(f"{GREEN}[OK]{NC} {msg}", file=sys.stderr)


def log_warn(msg: str) -> None:
    print(f"{YELLOW}[WARN]{NC} {msg}", file=sys.stderr)


def log_error(msg: str) -> None:
    print(f"{RED}[ERROR]{NC} {msg}", file=sys.stderr)
