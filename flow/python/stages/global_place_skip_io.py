"""ORFS global-place-skip-io stage — Python port of
flow/scripts/global_place_skip_io.tcl.

Invocation (via `make run`):
    openroad -no_splash -python flow/python/stages/global_place_skip_io.py

Reads `2_floorplan.odb` + `2_floorplan.sdc`. If pins are not pre-placed and
no explicit floorplan DEF is given, runs `global_placement -skip_io`.
Writes `3_1_place_gp_skip_io.odb`.
"""
# === Stage prelude ===========================================================
# See flow/python/README.md "Required stage prelude" — Tech()/Design() must be
# constructed at the lexical AND runtime module top. Do NOT refactor.
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
    print(f"[global_place_skip_io.py] metrics file: {_metrics_file}", flush=True)

from openroad import Design, Tech  # noqa: E402

_tech = Tech(None, None, _metrics_file) if _metrics_file else Tech()
_design = Design(_tech)
register_design(_design)

from orfs import (  # noqa: E402
    env_var_exists_and_non_empty,
    env_var_or_empty,
    log_cmd,
    orfs_write_db,
    tcl,
)
# === End stage prelude =======================================================

RESULTS_DIR = os.environ["RESULTS_DIR"]
SCRIPTS_DIR = os.environ["SCRIPTS_DIR"]


def main():
    tcl(f"source {SCRIPTS_DIR}/util.tcl")
    tcl(f"source {SCRIPTS_DIR}/load.tcl")

    tcl("erase_non_stage_variables place")
    tcl("load_design 2_floorplan.odb 2_floorplan.sdc")
    tcl("source_step_tcl PRE GLOBAL_PLACE_SKIP_IO")

    if env_var_exists_and_non_empty("FLOORPLAN_DEF"):
        print("FLOORPLAN_DEF is set. Skipping global placement without IOs")
    elif tcl("all_pins_placed") == "1":
        print("All pins are placed. Skipping global placement without IOs")
    else:
        pad = os.environ["CELL_PAD_IN_SITES_GLOBAL_PLACEMENT"]
        # place_density_with_lb_addon is a TCL proc from util.tcl — call it
        # through tcl() and use the returned string in the command.
        density = tcl("place_density_with_lb_addon")
        extra = env_var_or_empty("GLOBAL_PLACEMENT_ARGS")
        log_cmd(
            f"global_placement -skip_io -density {density} "
            f"-pad_left {pad} -pad_right {pad}"
            + (f" {extra}" if extra else "")
        )

    tcl("source_step_tcl POST GLOBAL_PLACE_SKIP_IO")

    tcl("report_design_area")

    orfs_write_db(f"{RESULTS_DIR}/3_1_place_gp_skip_io.odb")


if __name__ == "__main__":
    main()
