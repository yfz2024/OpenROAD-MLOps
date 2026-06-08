"""ORFS global-place stage — Python port of flow/scripts/global_place.tcl.

Invocation (via `make run`):
    openroad -no_splash -python flow/python/stages/global_place.py

Reads `3_2_place_iop.odb` + `2_floorplan.sdc`. Optionally removes buffers
(GPL_TIMING_DRIVEN), buffers ports, runs `global_placement` with all
configured args, then estimates parasitics and optionally clusters flops.
Writes `3_3_place_gp.odb`.
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
    print(f"[global_place.py] metrics file: {_metrics_file}", flush=True)

from openroad import Design, Tech  # noqa: E402

_tech = Tech(None, None, _metrics_file) if _metrics_file else Tech()
_design = Design(_tech)
register_design(_design)

from orfs import (  # noqa: E402
    env_var_exists_and_non_empty,
    env_var_or_empty,
    log_cmd,
    orfs_write_db,
    set_metrics_stage,
    tcl,
)
# === End stage prelude =======================================================

RESULTS_DIR = os.environ["RESULTS_DIR"]
SCRIPTS_DIR = os.environ["SCRIPTS_DIR"]


def do_placement(global_placement_args):
    """Mirror of the do_placement proc in global_place.tcl."""
    pad = os.environ["CELL_PAD_IN_SITES_GLOBAL_PLACEMENT"]
    density = tcl("place_density_with_lb_addon")
    all_args = [
        "-density",
        density,
        "-pad_left",
        pad,
        "-pad_right",
        pad,
    ] + list(global_placement_args)

    extra = env_var_or_empty("GLOBAL_PLACEMENT_ARGS")
    if extra:
        all_args += extra.split()

    log_cmd("global_placement " + " ".join(all_args))


def main():
    set_metrics_stage("globalplace__{}")

    tcl(f"source {SCRIPTS_DIR}/util.tcl")
    tcl(f"source {SCRIPTS_DIR}/load.tcl")
    tcl(f"source {SCRIPTS_DIR}/report_metrics.tcl")

    tcl("erase_non_stage_variables place")
    tcl("load_design 3_2_place_iop.odb 2_floorplan.sdc")
    tcl("source_step_tcl PRE GLOBAL_PLACE")

    tcl("set_dont_use $::env(DONT_USE_CELLS)")

    gpl_timing_driven = os.environ.get("GPL_TIMING_DRIVEN", "0") != "0"

    if gpl_timing_driven:
        log_cmd("remove_buffers")

    # Buffer chip-level ports unless DONT_BUFFER_PORTS=1 or FOOTPRINT set.
    if not env_var_exists_and_non_empty("FOOTPRINT"):
        if os.environ.get("DONT_BUFFER_PORTS", "0") == "0":
            print("Perform port buffering...", flush=True)
            buffer_args = env_var_or_empty("BUFFER_PORTS_ARGS")
            log_cmd("buffer_ports" + (f" {buffer_args}" if buffer_args else ""))

    global_placement_args = []

    # Routability — append_env_var with has_arg=False (the env var being "1"
    # flips a bare flag on, no value follows).
    if os.environ.get("GPL_ROUTABILITY_DRIVEN", "0") == "1":
        global_placement_args.append("-routability_driven")

    if gpl_timing_driven:
        global_placement_args.append("-timing_driven")
        if "GPL_KEEP_OVERFLOW" in os.environ:
            global_placement_args += [
                "-keep_resize_below_overflow",
                os.environ["GPL_KEEP_OVERFLOW"],
            ]

    min_phi = float(os.environ["MIN_PLACE_STEP_COEF"])
    max_phi = float(os.environ["MAX_PLACE_STEP_COEF"])
    if min_phi > max_phi:
        # utl::error matches the TCL flow's error path; it raises a TCL error
        # which our tcl() wrapper turns into RuntimeError.
        tcl(
            f'utl::error GPL 200 "MIN_PLACE_STEP_COEF ({min_phi}) cannot be '
            f'greater than MAX_PLACE_STEP_COEF ({max_phi})"'
        )

    global_placement_args.append("-force_center_initial_place")
    global_placement_args += ["-min_phi_coef", os.environ["MIN_PLACE_STEP_COEF"]]
    global_placement_args += ["-max_phi_coef", os.environ["MAX_PLACE_STEP_COEF"]]

    try:
        do_placement(global_placement_args)
    except RuntimeError as e:
        orfs_write_db(f"{RESULTS_DIR}/3_3_place_gp-failed.odb")
        raise RuntimeError(str(e)) from e

    log_cmd("estimate_parasitics -placement")

    if os.environ.get("CLUSTER_FLOPS", "0") != "0":
        cluster_args = env_var_or_empty("CLUSTER_FLOPS_ARGS")
        log_cmd("cluster_flops" + (f" {cluster_args}" if cluster_args else ""))
        log_cmd("estimate_parasitics -placement")

    tcl('report_metrics 3 "global place" false false')

    tcl("source_step_tcl POST GLOBAL_PLACE")

    orfs_write_db(f"{RESULTS_DIR}/3_3_place_gp.odb")


if __name__ == "__main__":
    main()
