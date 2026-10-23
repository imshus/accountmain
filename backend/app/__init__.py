"""Accounts.ai backend."""

import sys

# Checked here, before any module with 3.10+ syntax loads, so an old server Python gets a clear message
# instead of "unsupported operand type(s) for |". pandas 3 and the OpenAI SDK need 3.11 / 3.10 too.
if sys.version_info < (3, 11):
    raise SystemExit(
        f"Accounts.ai needs Python 3.11 or newer, but this is Python {sys.version.split()[0]}. "
        "Create the backend's venv with python3.11 (or newer), e.g. `python3.11 -m venv venv`, "
        "then run `venv/bin/python -m pip install -r requirements.txt`."
    )
