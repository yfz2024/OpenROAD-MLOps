"""ORFS density-fill stage — Python port of flow/scripts/density_fill.tcl.

Invocation (via `make run`):
    openroad -no_splash -python flow/python/stages/density_fill.py

Reads `5_route.odb` + `5_route.sdc`. If USE_FILL=1 runs `density_fill -rules
$FILL_CONFIG` + writes a debug verilog; otherwise just copies the input
forward. Writes `6_1_fill.odb`.
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
    print(f"[density_fill.py] metrics file: {_metrics_file}", flush=True)

from openroad import Design, Tech  # noqa: E402

_tech = Tech(None, None, _metrics_file) if _metrics_file else Tech()
_design = Design(_tech)
register_design(_design)

from orfs import log_cmd, orfs_write_db, tcl  # noqa: E402
# === End stage prelude =======================================================

RESULTS_DIR = os.environ["RESULTS_DIR"]
SCRIPTS_DIR = os.environ["SCRIPTS_DIR"]


def main():
    tcl(f"source {SCRIPTS_DIR}/util.tcl")
    tcl(f"source {SCRIPTS_DIR}/load.tcl")

    tcl("erase_non_stage_variables final")
    tcl("load_design 5_route.odb 5_route.sdc")
    tcl("source_step_tcl PRE DENSITY_FILL")

    if os.environ.get("USE_FILL", "0") != "0":
        tcl("set_propagated_clock [all_clocks]")
        tcl(f"density_fill -rules {os.environ['FILL_CONFIG']}")
        # Debug .v output — not a stage product, used only for inspection.
        tcl(f"write_verilog {RESULTS_DIR}/6_1_fill.v")
        orfs_write_db(f"{RESULTS_DIR}/6_1_fill.odb")
    else:
        log_cmd(f"exec cp {RESULTS_DIR}/5_route.odb {RESULTS_DIR}/6_1_fill.odb")

    tcl("source_step_tcl POST DENSITY_FILL")


if __name__ == "__main__":
    main()
