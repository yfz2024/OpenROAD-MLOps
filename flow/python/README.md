# ORFS Python flow

Python port of `flow/scripts/*.tcl`. **Does NOT replace** the TCL flow yet — TCL
scripts in `flow/scripts/` remain authoritative. This directory is the
experimental Python-side surface.

## Layout

- `orfs/` — helper package
  - `tcl.py` — TCL bridge (`tcl()`, `log_cmd()`, `get_design()`)
  - `env.py` — Python equivalents of `util.tcl`'s env var helpers
  - `io.py` — `orfs_write_db` / `orfs_write_sdc`
  - `metrics.py` — `utl::set/push/pop_metrics_stage` thin wrappers
  - `stage.py` — `bootstrap()` for stage entry points (line-buffered
    stdout + eager Tech/Design construction with metrics file)
- `stages/` — per-stage Python ports of `flow/scripts/<stage>.tcl`
  - `cts.py` — first stage proven byte-equal to the TCL version
- `_diag/` — sandbox / smoke scripts for triaging future SIGSEGV-class
  bugs. Not part of the flow. See `_diag/README.md`.

## Required stage prelude

Every stage **must** open with this exact prelude. `Tech()` / `Design()`
MUST be constructed at the **lexical AND runtime module top** — wrapping
them inside any helper function (even one called from module top)
triggers SIGSEGV inside `evalTclString` on this build. This was tested:
moving the construction into `orfs.stage.bootstrap()` crashed; keeping
them inline kept working. Do not refactor.

```python
import os, sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from orfs.stage import (
    enable_line_buffering, register_design, resolve_metrics_file,
)

enable_line_buffering()
_metrics_file = resolve_metrics_file()

from openroad import Design, Tech   # noqa: E402

_tech = Tech(None, None, _metrics_file) if _metrics_file else Tech()
_design = Design(_tech)
register_design(_design)

from orfs import tcl, log_cmd, ...   # then helpers
```

Why each line:

- `enable_line_buffering()` — `make run | tee` defaults Python's stdout
  to block buffering. Without this, mid-flow crashes look like the
  script crashed on line 1, because every `log_cmd` print is stuck in
  the buffer.
- `resolve_metrics_file()` — picks up `$LOG_DIR/$RUN_LOG_NAME_STEM.json`
  (exported by `make run`) or `ORFS_METRICS_FILE` (explicit override).
  The Python-side `Tech()` creates a fresh `OpenRoad` instance with its
  own `utl::Logger`; if the logger isn't given the metrics filename,
  every `utl::metric_int` call from TCL is silently dropped, and the
  resulting JSON has only generic `flow__*` counters.
- `Tech(None, None, _metrics_file)` + `Design(_tech)` —
  constructs the SAME singleton-style pair that
  `tools/OpenROAD/test/*.py` use. The signature is
  `Tech(interp=None, log_filename=None, metrics_filename=None)`.
- `register_design(_design)` — tells `orfs.tcl.tcl()` which Design's
  `evalTclString` to call.

## Design rules

1. **STA / SDC / `report_*` commands** route through `tcl()` (OpenSTA has no
   Python binding in this build).
2. **OpenROAD engine commands** (e.g. `clock_tree_synthesis`,
   `detailed_placement`, `estimate_parasitics`) also currently route through
   `tcl()` for the experiment — direct C++ method calls are a follow-up.
3. **Control flow, env var access, argument list construction** are written in
   Python. That is what justifies the port at all.
4. **Helper procs in `util.tcl` / `load.tcl` / `report_metrics.tcl` /
   `lec_check.tcl`** are NOT re-implemented in Python — instead the stage
   `source`s them once and calls them via `tcl()`. This avoids forking helper
   logic while we stabilize the architecture.

## Invocation

The stage scripts need the full ORFS env (`SCRIPTS_DIR`, `RESULTS_DIR`,
`DESIGN_NAME`, all `CTS_*` etc.) which is set up by the Makefile. The
simplest way to get that env without modifying the Makefile is to use the
existing generic `run` target:

```
cd flow
make DESIGN_CONFIG=./designs/<platform>/<design>/config.mk \
     RUN_SCRIPT=$PWD/python/stages/<stage>.py \
     RUN_LOG_NAME_STEM=<stage>_py \
     run
```

Example for asap7/gcd CTS:

```
cd flow
make DESIGN_CONFIG=./designs/asap7/gcd/config.mk \
     RUN_SCRIPT=$PWD/python/stages/cts.py \
     RUN_LOG_NAME_STEM=4_1_cts_py \
     run
```

The `run` target (`flow/Makefile:843-846`) auto-detects `.py` and adds
`-python` to the OpenROAD invocation. Pre-requisite: the stage's input
(`3_place.odb` / `3_place.sdc`) must already exist under
`results/<platform>/<design>/base/`. Build it with `make` up to the
previous stage first.
