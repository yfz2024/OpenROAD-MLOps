"""orfs_write_db / orfs_write_sdc — Python port of util.tcl procs."""
import os

from .tcl import log_cmd


def _stage_writes_enabled():
    return os.environ.get("WRITE_ODB_AND_SDC_EACH_STAGE", "0") == "1"


def orfs_write_db(output_file):
    if not _stage_writes_enabled():
        return
    log_cmd(f"write_db {output_file}")


def orfs_write_sdc(output_file):
    if not _stage_writes_enabled():
        return
    log_cmd(f"write_sdc -no_timestamp {output_file}")
