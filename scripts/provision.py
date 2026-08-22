# /// script
# requires-python = ">=3.12"
# ///
"""Mint this project's machine-creatable credentials (op-project-bootstrap
provision contract: --list prints mintable field names; --field NAME prints
ONLY the secret to stdout, progress on stderr).

Modal API tokens cannot be minted via any API (`modal token new` is
browser-only), so "minting" here = copying the canonical workspace token
from the AI Agent vault item that the machine-wide `modal` wrapper already
injects (single source of truth; nothing ever touches disk). Runs under
whatever `op` auth the caller has; needs read access to the AI Agent vault.
Idempotent per field.
"""

import subprocess
import sys

# AI Agent vault / "AI Agent Modal Token" item, by stable IDs (names mutate, IDs don't)
OP_MODAL_TOKEN_ITEM = "op://4eeyrkqibibn7k4j6rz2fbzvxm/2sfxybjpv3c3ohzxhf5qeken4a"
FIELDS = {"token-id": "token_id", "token-secret": "token_secret"}


def op_read(ref: str) -> str:
    return subprocess.run(
        ["op", "read", ref], capture_output=True, text=True, check=True
    ).stdout.strip()


def main() -> None:
    match sys.argv[1:]:
        case ["--list"]:
            print("\n".join(FIELDS))
        case ["--field", name] if name in FIELDS:
            print("· copying Modal workspace token from the AI Agent vault", file=sys.stderr)
            print(op_read(f"{OP_MODAL_TOKEN_ITEM}/{FIELDS[name]}"))
        case _:
            sys.exit("usage: provision.py --list | --field <name>")


if __name__ == "__main__":
    main()
