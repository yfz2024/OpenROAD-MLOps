"""ORFS fillcell stage — Python port of flow/scripts/fillcell.tcl.

Invocation (via `make run`):
    openroad -no_splash -python flow/python/stages/fillcell.py

Reads `5_2_route.odb` + `5_1_grt.sdc`. If FILL_CELLS is set runs
`filler_placement` + `check_placement`; otherwise just copies the input
forward. Writes `5_3_fillcell.odb`.
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
    print(f"[fillcell.py] metrics file: {_metrics_file}", flush=True)

from openroad import Design, Tech  # noqa: E402

_tech = Tech(None, None, _metrics_file) if _metrics_file else Tech()
_design = Design(_tech)
register_design(_design)

from orfs import env_var_exists_and_non_empty, log_cmd, orfs_write_db, tcl  # noqa: E402
# === End stage prelude =======================================================

RESULTS_DIR = os.environ["RESULTS_DIR"]
SCRIPTS_DIR = os.environ["SCRIPTS_DIR"]


def main():
    tcl(f"source {SCRIPTS_DIR}/util.tcl")
    tcl(f"source {SCRIPTS_DIR}/load.tcl")
    tcl("erase_non_stage_variables route")

    if env_var_exists_and_non_empty("FILL_CELLS"):
        tcl("load_design 5_2_route.odb 5_1_grt.sdc")
        tcl("source_step_tcl PRE FILLCELL")

        tcl("set_propagated_clock [all_clocks]")

        # FILL_CELLS is a space-separated list — wrap in TCL braces so
        # filler_placement sees it as a single list argument.
        log_cmd(f"filler_placement {{{os.environ['FILL_CELLS']}}}")
        tcl("check_placement")

        tcl("report_design_area")
        orfs_write_db(f"{RESULTS_DIR}/5_3_fillcell.odb")
    else:
        log_cmd(
            f"exec cp {RESULTS_DIR}/5_2_route.odb {RESULTS_DIR}/5_3_fillcell.odb"
        )

    tcl("source_step_tcl POST FILLCELL")


if __name__ == "__main__":
    main()
