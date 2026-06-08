"""ORFS tapcell stage — Python port of flow/scripts/tapcell.tcl.

Invocation (via `make run`):
    openroad -no_splash -python flow/python/stages/tapcell.py

Reads `2_2_floorplan_macro.odb` + `2_1_floorplan.sdc`, runs `cut_rows` (or
sources a custom TAPCELL_TCL), writes `2_3_floorplan_tapcell.odb`.
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
    print(f"[tapcell.py] metrics file: {_metrics_file}", flush=True)

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

    tcl("erase_non_stage_variables floorplan")
    tcl("load_design 2_2_floorplan_macro.odb 2_1_floorplan.sdc")
    tcl("source_step_tcl PRE TAPCELL")

    if env_var_exists_and_non_empty("TAPCELL_TCL"):
        log_cmd(f"source {os.environ['TAPCELL_TCL']}")
    else:
        log_cmd("cut_rows")

    tcl("source_step_tcl POST TAPCELL")

    tcl("report_design_area")

    orfs_write_db(f"{RESULTS_DIR}/2_3_floorplan_tapcell.odb")


if __name__ == "__main__":
    main()
