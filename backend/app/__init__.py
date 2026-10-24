"""Accounts.ai backend."""

import sys

# Checked here, before any other module loads, so an old server Python gets a clear message instead of a
# syntax error. 3.9 and 3.10 get older but compatible library versions (see requirements.txt).
if sys.version_info < (3, 9):
    raise SystemExit(
        f"Accounts.ai needs Python 3.9 or newer, but this is Python {sys.version.split()[0]}. "
        "Create the backend's venv with python3.9 (or newer), e.g. `python3.9 -m venv venv`, "
        "then run `venv/bin/python -m pip install -r requirements.txt`."
    )

from . import compat  # noqa: E402,F401  (pandas 3 behaviour on pandas 2, set before any module uses pandas)
