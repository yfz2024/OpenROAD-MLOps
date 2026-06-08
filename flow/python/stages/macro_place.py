"""ORFS macro-place stage — Python port of flow/scripts/macro_place.tcl.

Invocation (via `make run`):
    openroad -no_splash -python flow/python/stages/macro_place.py

Reads `2_1_floorplan.{odb,sdc}`. If the design has any BLOCK-type masters,
runs `rtl_macro_placer` with a long pipeline of env-var-driven options
(macro_place_util.tcl). Otherwise prints "No macros found" and skips.
Writes `2_2_floorplan_macro.odb` and `2_2_floorplan_macro.tcl` (macro
placement script).

For asap7/gcd this is a no-op (no macros) and writes the input ODB
forward unchanged.

Note: `mpl::MacroPlacer` doesn't have a `-py.i` SWIG file in this build,
so we route the actual `rtl_macro_placer` call through the TCL bridge —
same as we do for every other OR engine command. Adding mpl Python
bindings is tracked separately and is not blocking this stage's byte-equal
parity.

Note: macro_place_util.tcl is `source`d wholesale rather than reimplemented
in Python. It contains a `dict for` over MACRO_WRAPPERS plus `swapMaster`
ODB mutations that are awkward to bridge piecewise; sourcing keeps the
behaviour identical and avoids forking helper logic during Milestone 1.
"""
# === Stage prelude ===========================================================
# See flow/python/README.md "Required stage prelude".
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orfs.stage import (  # noqa: E402
    enable_line_buffering,
    register_design,
    resolve_metrics_file,
)

enable_line_buffering()
_metrics_file = resolve_metrics_file()
if _metrics_file:
    print(f"[macro_place.py] metrics file: {_metrics_file}", flush=True)

from openroad import Design, Tech  # noqa: E402

_tech = Tech(None, None, _metrics_file) if _metrics_file else Tech()
_design = Design(_tech)
register_design(_design)

from orfs import orfs_write_db, tcl  # noqa: E402
# === End stage prelude =======================================================

RESULTS_DIR = os.environ["RESULTS_DIR"]
SCRIPTS_DIR = os.environ["SCRIPTS_DIR"]


def main():
    tcl(f"source {SCRIPTS_DIR}/util.tcl")
    tcl(f"source {SCRIPTS_DIR}/load.tcl")

    tcl("erase_non_stage_variables floorplan")
    tcl("load_design 2_1_floorplan.odb 2_1_floorplan.sdc")
    tcl("source_step_tcl PRE MACRO_PLACE")

    tcl(f"source {SCRIPTS_DIR}/macro_place_util.tcl")

    tcl("source_step_tcl POST MACRO_PLACE")

    tcl("report_design_area")

    orfs_write_db(f"{RESULTS_DIR}/2_2_floorplan_macro.odb")
    tcl(f"write_macro_placement {RESULTS_DIR}/2_2_floorplan_macro.tcl")


if __name__ == "__main__":
    main()
