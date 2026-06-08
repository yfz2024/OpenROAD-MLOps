"""Stage prelude helpers.

⚠ IMPORTANT: this module DOES NOT (and CANNOT) construct Tech / Design
in a helper function. On this build, `Tech()` triggers a SIGSEGV inside
`evalTclString` whenever it's called from a non-empty Python stack frame
— i.e. from inside any function. Construction must happen at the
**lexical AND runtime** module top level of the running stage script.

This file therefore only provides:
  * `enable_line_buffering()`   — must be the first call in a stage
  * `resolve_metrics_file()`    — returns the JSON path or None
  * `register_design(design)`   — equivalent to `orfs.tcl.set_design`

The actual `Tech(...)` and `Design(...)` calls must appear in each
stage file at module top. The prelude template is in
`flow/python/README.md` under "Required stage prelude".
"""
import os
import sys


def enable_line_buffering():
    """Force line-buffered stdout.

    Required because `make run | tee` defaults Python's stdout to block
    buffering — without this, mid-flow crashes look like the script
    crashed on line 1 (every `log_cmd` print is stuck in the buffer).
    """
    sys.stdout.reconfigure(line_buffering=True)


def resolve_metrics_file():
    """Return a metrics-output JSON path from env, or None.

    Resolution order:
      1. `ORFS_METRICS_FILE`           — explicit override
      2. `$LOG_DIR/$RUN_LOG_NAME_STEM.json` — `make run` exports both
      3. None — stage runs without metric emission
    """
    explicit = os.environ.get("ORFS_METRICS_FILE")
    if explicit:
        return explicit
    log_dir = os.environ.get("LOG_DIR")
    stem = os.environ.get("RUN_LOG_NAME_STEM")
    if log_dir and stem:
        return f"{log_dir}/{stem}.json"
    return None


def register_design(design):
    """Register the Design with `orfs.tcl` so `tcl(...)` knows what to call."""
    from .tcl import set_design
    set_design(design)
