"""TCL bridge for ORFS Python flow.

OpenSTA has no Python binding, and most OpenROAD top-level TCL commands
(`clock_tree_synthesis`, `initialize_floorplan`, ...) are TCL procs that
parse flags and dispatch to C++. The simplest correct path is to call them
through `Design.evalTclString()`.
"""
import os
import time

from openroad import Design, Tech

_design = None
_TRACE = os.environ.get("ORFS_PY_TRACE", "") not in ("", "0", "false")


def get_design():
    """Return the singleton Design, creating it if needed.

    Inside `openroad -python`, constructing `Tech()` returns the existing
    OpenRoad singleton's Tech, so `Design(Tech())` gives us a handle bound
    to the same underlying database that any TCL command would mutate.
    """
    global _design
    if _design is None:
        _design = Design(Tech())
    return _design


def set_design(design):
    global _design
    _design = design


def tcl(cmd):
    """Run a TCL command. Returns the command's TCL return value.

    Raises RuntimeError if the TCL command errors. `Design.evalTclString`
    itself never raises — it just returns whatever the interpreter's result
    string ended up being, error or not. To detect errors, we wrap the
    user command in `catch` and inspect the return code. Without this,
    a failing OR command (e.g. an `[ERROR ...]` log from a TCL proc) is
    silently swallowed and the stage keeps running on broken state.
    """
    if _TRACE:
        print(f"[orfs.tcl] {cmd}", flush=True)
    design = get_design()
    # `catch { body } result` puts the command's return (or error message)
    # into the variable named in the third arg, and itself returns "0" on
    # success, "1" on error. Stash both in script-local vars so we don't
    # collide with anything the inner command sets.
    wrapper = (
        "set ::__orfs_rc [catch {\n" + cmd + "\n} ::__orfs_result]; "
        "set ::__orfs_rc"
    )
    rc = design.evalTclString(wrapper)
    if rc.strip() == "1":
        err = design.evalTclString("set ::__orfs_result")
        raise RuntimeError(f"TCL error running {cmd!r}: {err}")
    return design.evalTclString("set ::__orfs_result")


def log_cmd(cmd):
    """TCL command with timing — mirrors util.tcl::log_cmd.

    Prints the command, runs it, prints elapsed time if >= 5s.
    """
    print(cmd, flush=True)
    t0 = time.time()
    result = tcl(cmd)
    elapsed = time.time() - t0
    if elapsed >= 5:
        print(f"Took {int(elapsed)} seconds: {cmd}", flush=True)
    return result
