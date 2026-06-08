"""ORFS PDN stage — Python port of flow/scripts/pdn.tcl.

Invocation (via `make run`):
    openroad -no_splash -python flow/python/stages/pdn.py

Reads `2_3_floorplan_tapcell.odb` + `2_1_floorplan.sdc`, sources the
platform's PDN_TCL DSL, runs `pdngen`, walks supply nets (currently a
no-op — `check_power_grid` is commented out due to CI issues, kept here
for parity), writes `2_4_floorplan_pdn.odb`.
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
    print(f"[pdn.py] metrics file: {_metrics_file}", flush=True)

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
    tcl("load_design 2_3_floorplan_tapcell.odb 2_1_floorplan.sdc")
    tcl("source_step_tcl PRE PDN")

    tcl(f"source {os.environ['PDN_TCL']}")
    tcl("pdngen")

    tcl("source_step_tcl POST PDN")

    # Supply-net walk — currently no-op (check_power_grid disabled for CI).
    # Kept as a pure-TCL block for parity with pdn.tcl line 11-20.
    tcl(
        """
        set block [ord::get_db_block]
        foreach net [$block getNets] {
          set type [$net getSigType]
          if { $type == "POWER" || $type == "GROUND" } {
            # check_power_grid -net [$net getName]
          }
        }
        """
    )

    tcl("report_design_area")

    orfs_write_db(f"{RESULTS_DIR}/2_4_floorplan_pdn.odb")


if __name__ == "__main__":
    main()
