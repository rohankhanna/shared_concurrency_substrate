#!/usr/bin/env python3
import json
import os
import shutil
import stat
import sys
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("/etc/terminal-sudo-guard/allowlist.json")
LEGACY_CONFIG_PATH = Path("/etc/sudo-allow/allowlist.json")
ENV_CONFIG_PATH = "SUDO_ALLOWLIST_PATH"
PROG = Path(sys.argv[0]).name


def _fail(message: str, code: int = 1) -> None:
    print(f"{PROG}: {message}", file=sys.stderr)
    sys.exit(code)


def _usage() -> None:
    print(
        "Usage:\n"
        f"  {PROG} mount -t nfs4 -o vers=4,proto=tcp,port=<port> <remote> <mount>\n"
        f"  {PROG} umount <mount>\n",
        file=sys.stderr,
    )


def _config_path() -> Path:
    override = os.environ.get(ENV_CONFIG_PATH)
    if override:
        return Path(override)
    if DEFAULT_CONFIG_PATH.exists():
        return DEFAULT_CONFIG_PATH
    if LEGACY_CONFIG_PATH.exists():
        return LEGACY_CONFIG_PATH
    return DEFAULT_CONFIG_PATH


def _load_config() -> dict:
    config_path = _config_path()
    if not config_path.exists():
        _fail(f"allowlist not found at {config_path}")
    if config_path.is_symlink():
        _fail("allowlist must not be a symlink")
    st = config_path.stat()
    if not stat.S_ISREG(st.st_mode):
        _fail("allowlist must be a regular file")
    if st.st_uid != 0:
        _fail("allowlist must be owned by root")
    if st.st_mode & 0o022:
        _fail("allowlist must not be group/other writable")
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        _fail(f"invalid JSON in allowlist: {exc}")
    if not isinstance(data, dict):
        _fail("allowlist must be a JSON object")
    return data


def _get_str_list(data: dict, key: str) -> list[str]:
    value = data.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        _fail(f"allowlist field {key!r} must be a list of strings")
    return value


def _get_int_list(data: dict, key: str, default: list[int]) -> list[int]:
    value = data.get(key, default)
    if not isinstance(value, list) or not all(isinstance(item, int) for item in value):
        _fail(f"allowlist field {key!r} must be a list of integers")
    return value


def _resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if not path.is_absolute():
        _fail(f"path must be absolute: {path_str}")
    return path.resolve(strict=False)


def _is_allowed_path(path_str: str, prefixes: list[str]) -> bool:
    path = _resolve_path(path_str)
    for prefix in prefixes:
        prefix_path = _resolve_path(prefix)
        try:
            common = os.path.commonpath([str(path), str(prefix_path)])
        except ValueError:
            continue
        if common == str(prefix_path):
            return True
    return False


def _parse_mount_opts(opts: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in opts.split(","):
        if "=" not in item:
            _fail(f"unsupported mount option {item!r}")
        key, value = item.split("=", 1)
        parsed[key] = value
    return parsed


def _validate_mount(argv: list[str], cfg: dict) -> list[str]:
    if len(argv) != 7:
        _fail("unsupported mount invocation (expected 6 args)")
    cmd, type_flag, fs_type, opts_flag, opts_value, remote, mount_path = argv
    if cmd != "mount" or type_flag != "-t" or fs_type != "nfs4" or opts_flag != "-o":
        _fail("only 'mount -t nfs4 -o ...' is allowed")
    opts = _parse_mount_opts(opts_value)
    if set(opts.keys()) != {"vers", "proto", "port"}:
        _fail("mount options must be exactly: vers, proto, port")
    if opts["vers"] != "4" or opts["proto"] != "tcp":
        _fail("mount options must include vers=4 and proto=tcp")
    try:
        port = int(opts["port"])
    except ValueError:
        _fail("port must be an integer")
    allowed_ports = _get_int_list(cfg, "allowed_nfs_ports", [2049])
    if port not in allowed_ports:
        _fail(f"port {port} not in allowlist")
    allowed_remotes = _get_str_list(cfg, "allowed_remotes")
    if remote not in allowed_remotes:
        _fail(f"remote {remote!r} not in allowlist")
    allowed_mounts = _get_str_list(cfg, "allowed_mount_prefixes")
    if not allowed_mounts:
        _fail("allowed_mount_prefixes is empty")
    if not _is_allowed_path(mount_path, allowed_mounts):
        _fail(f"mount path {mount_path!r} not under an allowed prefix")
    return argv


def _validate_umount(argv: list[str], cfg: dict) -> list[str]:
    if len(argv) != 2:
        _fail("only 'umount <path>' is allowed")
    cmd, mount_path = argv
    if cmd != "umount":
        _fail("only 'umount' is allowed")
    allowed_mounts = _get_str_list(cfg, "allowed_umount_prefixes")
    if not allowed_mounts:
        allowed_mounts = _get_str_list(cfg, "allowed_mount_prefixes")
    if not allowed_mounts:
        _fail("allowed_mount_prefixes is empty")
    if not _is_allowed_path(mount_path, allowed_mounts):
        _fail(f"umount path {mount_path!r} not under an allowed prefix")
    return argv


def _exec(argv: list[str]) -> None:
    cmd_path = shutil.which(argv[0])
    if cmd_path is None:
        _fail(f"command not found: {argv[0]}")
    os.execvp(cmd_path, argv)


def main() -> None:
    if os.geteuid() != 0:
        _fail("this wrapper must be run as root (use sudo)", code=2)
    if len(sys.argv) < 2:
        _usage()
        _fail("missing command")
    cfg = _load_config()
    argv = sys.argv[1:]
    if argv[0] == "mount":
        _exec(_validate_mount(argv, cfg))
    elif argv[0] == "umount":
        _exec(_validate_umount(argv, cfg))
    else:
        _usage()
        _fail(f"unsupported command {argv[0]!r}")


if __name__ == "__main__":
    main()
