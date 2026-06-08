"""Python equivalents of util.tcl's env_var_* helpers."""
import os


def env_var_exists_and_non_empty(name):
    return name in os.environ and os.environ[name] != ""


def env_var_equals(name, value):
    return os.environ.get(name) == str(value)


def env_var_or_empty(name):
    return os.environ.get(name, "")


def append_env_var(args, env_var, flag, has_arg):
    """Mirror util.tcl::append_env_var.

    has_arg=False: append `flag` to args if env var is exactly "1".
    has_arg=True:  append `flag value` to args if env var is non-empty.
    """
    if not has_arg:
        if env_var_equals(env_var, "1"):
            args.append(flag)
    else:
        if env_var_exists_and_non_empty(env_var):
            args.extend([flag, os.environ[env_var]])
