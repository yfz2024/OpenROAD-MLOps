"""ORFS detail-place stage — Python port of flow/scripts/detail_place.tcl.

Invocation (set up by `make run`):
    openroad -no_splash -python flow/python/stages/detail_place.py

Reads `3_4_place_resized.odb` + `2_floorplan.sdc`, runs detailed placement
plus optional DPO and mirror optimisation, then writes `3_5_place_dp.odb`.

util.tcl / load.tcl / report_metrics.tcl are sourced once via `tcl()` and
reused.
"""
# === Stage prelude ===========================================================
# Tech() / Design() MUST be constructed at the lexical AND runtime module top.
# Wrapping them in any helper function — even one called from module top —
# triggers SIGSEGV inside evalTclString on this build. Do NOT refactor these
# six construction lines into orfs/stage.py. See README "Required stage
# prelude" for the gory details.
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
    print(f"[detail_place.py] metrics file: {_metrics_file}", flush=True)

from openroad import Design, Tech  # noqa: E402

_tech = Tech(None, None, _metrics_file) if _metrics_file else Tech()
_design = Design(_tech)
register_design(_design)

from orfs import (  # noqa: E402
    append_env_var,
    env_var_exists_and_non_empty,
    env_var_or_empty,
    log_cmd,
    orfs_write_db,
    set_metrics_stage,
    tcl,
)
# === End stage prelude =======================================================

SCRIPTS_DIR = os.environ["SCRIPTS_DIR"]
PLATFORM_DIR = os.environ["PLATFORM_DIR"]
RESULTS_DIR = os.environ["RESULTS_DIR"]


def do_dpl():
    """Mirror of the do_dpl proc in detail_place.tcl."""
    if env_var_exists_and_non_empty("BALANCE_ROWS") and os.environ["BALANCE_ROWS"] != "0":
        log_cmd("balance_row_usage")

    pad = os.environ["CELL_PAD_IN_SITES_DETAIL_PLACEMENT"]
    log_cmd(f"set_placement_padding -global -left {pad} -right {pad}")

    dpl_args = env_var_or_empty("DETAIL_PLACEMENT_ARGS").split()
    append_env_var(dpl_args, "USE_NEGOTIATION", "-use_negotiation", False)
    log_cmd("detailed_placement " + " ".join(dpl_args))

    if env_var_exists_and_non_empty("ENABLE_DPO") and os.environ["ENABLE_DPO"] != "0":
        if env_var_exists_and_non_empty("DPO_MAX_DISPLACEMENT"):
            # DPO_MAX_DISPLACEMENT may be "5 1" — two values for {disp_x disp_y}.
            # Wrap in TCL braces so the interpreter sees it as a single list
            # argument; otherwise the two tokens become separate positional
            # args and improve_placement rejects them (STA-0564). The original
            # TCL flow gets this right because `$::env(...)` substitution
            # happens after word splitting — `args` keeps "5 1" as one element
            # of the proc args list, then `{*}$args` re-expands it as a list.
            log_cmd(
                "improve_placement -max_displacement "
                f"{{{os.environ['DPO_MAX_DISPLACEMENT']}}}"
            )
        else:
            log_cmd("improve_placement")

    log_cmd("optimize_mirroring")

    # check_placement returns the violation count as a string — wrap in utl::info
    # exactly like the TCL version so the log message is identical.
    tcl('utl::info FLW 12 "Placement violations [check_placement -verbose]."')

    log_cmd("estimate_parasitics -placement")


def main():
    set_metrics_stage("detailedplace__{}")

    tcl(f"source {SCRIPTS_DIR}/util.tcl")
    tcl(f"source {SCRIPTS_DIR}/load.tcl")
    tcl(f"source {SCRIPTS_DIR}/report_metrics.tcl")

    tcl("erase_non_stage_variables place")
    tcl("load_design 3_4_place_resized.odb 2_floorplan.sdc")
    tcl("source_step_tcl PRE DETAIL_PLACE")

    tcl(f"source {PLATFORM_DIR}/setRC.tcl")

    try:
        do_dpl()
    except RuntimeError as e:
        orfs_write_db(f"{RESULTS_DIR}/3_5_place_dp-failed.odb")
        raise RuntimeError(str(e)) from e

    tcl('report_metrics 3 "detailed place" true false')

    tcl("source_step_tcl POST DETAIL_PLACE")

    orfs_write_db(f"{RESULTS_DIR}/3_5_place_dp.odb")


if __name__ == "__main__":
    main()
