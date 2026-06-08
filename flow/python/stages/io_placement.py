"""ORFS io-placement stage — Python port of flow/scripts/io_placement.tcl.

Invocation (via `make run`):
    openroad -no_splash -python flow/python/stages/io_placement.py

Reads `3_1_place_gp_skip_io.odb` + `2_floorplan.sdc`. If pins are pre-placed
(FLOORPLAN_DEF / FOOTPRINT / FOOTPRINT_TCL), just copies the previous odb;
otherwise runs `place_pins -hor_layers -ver_layers` plus optional
PLACE_PINS_ARGS. Writes `3_2_place_iop.odb`.
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
    print(f"[io_placement.py] metrics file: {_metrics_file}", flush=True)

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

    pins_preplaced = (
        env_var_exists_and_non_empty("FLOORPLAN_DEF")
        or env_var_exists_and_non_empty("FOOTPRINT")
        or env_var_exists_and_non_empty("FOOTPRINT_TCL")
    )

    if not pins_preplaced:
        tcl("load_design 3_1_place_gp_skip_io.odb 2_floorplan.sdc")
        tcl("source_step_tcl PRE IO_PLACEMENT")

        hor = os.environ["IO_PLACER_H"]
        ver = os.environ["IO_PLACER_V"]
        extra = env_var_or_empty("PLACE_PINS_ARGS")
        log_cmd(
            f"place_pins -hor_layers {hor} -ver_layers {ver}"
            + (f" {extra}" if extra else "")
        )

        tcl("report_design_area")

        orfs_write_db(f"{RESULTS_DIR}/3_2_place_iop.odb")
        log_cmd(f"write_pin_placement {RESULTS_DIR}/3_2_place_iop.tcl")
    else:
        log_cmd(
            f"exec cp {RESULTS_DIR}/3_1_place_gp_skip_io.odb "
            f"{RESULTS_DIR}/3_2_place_iop.odb"
        )

    tcl("source_step_tcl POST IO_PLACEMENT")


if __name__ == "__main__":
    main()
