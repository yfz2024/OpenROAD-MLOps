"""ORFS CTS stage — Python port of flow/scripts/cts.tcl.

Invocation (set up by `make run`):
    openroad -no_splash -python flow/python/stages/cts.py

Requires the same env vars `flow.sh` provides: SCRIPTS_DIR, RESULTS_DIR,
DONT_USE_CELLS, CELL_PAD_IN_SITES_DETAIL_PLACEMENT, plus optional
CTS_BUF_DISTANCE / CTS_CLUSTER_SIZE / CTS_CLUSTER_DIAMETER / CTS_BUF_LIST /
CTS_LIB_NAME / CTS_ARGS / USE_NEGOTIATION / DETAILED_METRICS / CTS_SNAPSHOTS /
SKIP_CTS_REPAIR_TIMING / LEC_CHECK / WRITE_ODB_AND_SDC_EACH_STAGE.

util.tcl / load.tcl / lec_check.tcl / report_metrics.tcl are sourced once via
`tcl()` and reused.
"""
# === Stage prelude ===========================================================
# Tech() / Design() MUST be constructed at the lexical AND runtime module top.
# Wrapping them in any helper function (even one called from module top)
# triggers SIGSEGV inside evalTclString on this build. Do NOT refactor these
# six construction lines into orfs/stage.py — that was tried and crashed.
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
    print(f"[cts.py] metrics file: {_metrics_file}", flush=True)

from openroad import Design, Tech  # noqa: E402

_tech = Tech(None, None, _metrics_file) if _metrics_file else Tech()
_design = Design(_tech)
register_design(_design)

from orfs import (  # noqa: E402
    append_env_var,
    env_var_exists_and_non_empty,
    log_cmd,
    orfs_write_db,
    orfs_write_sdc,
    pop_metrics_stage,
    push_metrics_stage,
    set_metrics_stage,
    tcl,
)
# === End stage prelude =======================================================

SCRIPTS_DIR = os.environ["SCRIPTS_DIR"]
RESULTS_DIR = os.environ["RESULTS_DIR"]


def save_progress(stage):
    print(f"Run 'make gui_{stage}.odb' to load progress snapshot")
    orfs_write_db(f"{RESULTS_DIR}/{stage}.odb")
    orfs_write_sdc(f"{RESULTS_DIR}/{stage}.sdc")


def main():
    set_metrics_stage("cts__{}")

    # Bring in the helper procs the rest of the flow expects.
    tcl(f"source {SCRIPTS_DIR}/util.tcl")
    tcl(f"source {SCRIPTS_DIR}/load.tcl")
    tcl(f"source {SCRIPTS_DIR}/lec_check.tcl")
    tcl(f"source {SCRIPTS_DIR}/report_metrics.tcl")

    tcl("erase_non_stage_variables cts")
    tcl("load_design 3_place.odb 3_place.sdc")
    tcl("source_step_tcl PRE CTS")

    log_cmd("repair_clock_inverters")

    cts_args = ["-sink_clustering_enable", "-repair_clock_nets"]
    append_env_var(cts_args, "CTS_BUF_DISTANCE", "-distance_between_buffers", True)
    append_env_var(cts_args, "CTS_CLUSTER_SIZE", "-sink_clustering_size", True)
    append_env_var(cts_args, "CTS_CLUSTER_DIAMETER", "-sink_clustering_max_diameter", True)
    append_env_var(cts_args, "CTS_BUF_LIST", "-buf_list", True)
    append_env_var(cts_args, "CTS_LIB_NAME", "-library", True)

    if env_var_exists_and_non_empty("CTS_ARGS"):
        cts_args = os.environ["CTS_ARGS"].split()

    # set_dont_use takes a TCL list; pull it straight from the env var to keep
    # the same parsing as the TCL flow.
    tcl("set_dont_use $::env(DONT_USE_CELLS)")

    log_cmd("clock_tree_synthesis " + " ".join(cts_args))

    push_metrics_stage("cts__{}__pre_repair_timing")
    log_cmd("estimate_parasitics -placement")
    if env_var_exists_and_non_empty("DETAILED_METRICS") and os.environ["DETAILED_METRICS"] != "0":
        tcl('report_metrics 4 "cts pre-repair-timing"')
    pop_metrics_stage()

    pad = os.environ["CELL_PAD_IN_SITES_DETAIL_PLACEMENT"]
    log_cmd(f"set_placement_padding -global -left {pad} -right {pad}")

    dpl_args = []
    append_env_var(dpl_args, "USE_NEGOTIATION", "-use_negotiation", False)
    dpl_cmd = "detailed_placement " + " ".join(dpl_args)

    try:
        log_cmd(dpl_cmd)
    except RuntimeError as e:
        save_progress("4_1_error")
        raise RuntimeError(f"Detailed placement failed in CTS: {e}") from e

    log_cmd("estimate_parasitics -placement")

    if env_var_exists_and_non_empty("CTS_SNAPSHOTS") and os.environ["CTS_SNAPSHOTS"] != "0":
        save_progress("4_1_pre_repair_hold_setup")

    skip_repair = (
        env_var_exists_and_non_empty("SKIP_CTS_REPAIR_TIMING")
        and os.environ["SKIP_CTS_REPAIR_TIMING"] != "0"
    )
    if not skip_repair:
        lec_on = env_var_exists_and_non_empty("LEC_CHECK") and os.environ["LEC_CHECK"] != "0"
        if lec_on:
            tcl("write_lec_verilog 4_before_rsz_lec.v")

        tcl("repair_timing_helper")

        if lec_on:
            tcl("write_lec_verilog 4_after_rsz_lec.v")
            tcl("run_lec_test 4_rsz 4_before_rsz_lec.v 4_after_rsz_lec.v")

        try:
            log_cmd(dpl_cmd)
        except RuntimeError as e:
            save_progress("4_1_error")
            raise RuntimeError(f"Detailed placement failed in CTS: {e}") from e

        log_cmd("check_placement -verbose")

    tcl('report_metrics 4 "cts final"')

    tcl("source_step_tcl POST CTS")

    orfs_write_db(f"{RESULTS_DIR}/4_1_cts.odb")
    orfs_write_sdc(f"{RESULTS_DIR}/4_cts.sdc")


if __name__ == "__main__":
    main()
