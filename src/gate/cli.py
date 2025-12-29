"""Command-line interface for Gate (broker and FUSE mount)."""

from __future__ import annotations

import argparse
import errno
import os
import shlex
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import signal
from pathlib import Path
from typing import Iterable

from .broker import LockBrokerServer
from .client import BrokerEndpoint, LockBrokerClient
from .config import BrokerConfig
from .version import get_version

GATE_ENV_TEMPLATE = """# Shared concurrency substrate environment (Gate).
GATE_STATE_DIR=/var/lib/gate
GATE_REPO_DIR=/opt/gate
GATE_MOUNT_DIR=/mnt/gate
GATE_BROKER_HOST=127.0.0.1
GATE_BROKER_PORT=8787
GATE_LEASE_MS=3600000
GATE_MAX_HOLD_MS=3600000
GATE_FUSE_ALLOW_OTHER=0
"""

GATE_BROKER_SERVICE_TEMPLATE = """[Unit]
Description=Gate Lock Broker (Shared Concurrency Substrate)
After=network.target

[Service]
Type=simple
EnvironmentFile=/etc/gate/gate.env
WorkingDirectory=${GATE_REPO_DIR}
ExecStart=/bin/sh -c 'if [ -x /opt/gate/bin/gate ]; then /opt/gate/bin/gate broker --state-dir "${GATE_STATE_DIR}" --host "${GATE_BROKER_HOST}" --port "${GATE_BROKER_PORT}" --lease-ms "${GATE_LEASE_MS}" --max-hold-ms "${GATE_MAX_HOLD_MS}"; else /usr/bin/python3 "${GATE_REPO_DIR}/scripts/gate_broker.py" --state-dir "${GATE_STATE_DIR}" --host "${GATE_BROKER_HOST}" --port "${GATE_BROKER_PORT}" --lease-ms "${GATE_LEASE_MS}" --max-hold-ms "${GATE_MAX_HOLD_MS}"; fi'
Restart=always
User=gate
Group=gate

[Install]
WantedBy=multi-user.target
"""

GATE_FUSE_SERVICE_TEMPLATE = """[Unit]
Description=Gate FUSE Mount (Shared Concurrency Substrate)
After=network.target gate-broker.service
Requires=gate-broker.service

[Service]
Type=simple
EnvironmentFile=/etc/gate/gate.env
WorkingDirectory=${GATE_REPO_DIR}
ExecStartPre=/bin/mkdir -p ${GATE_MOUNT_DIR}
ExecStartPre=/bin/chown gate:gate ${GATE_MOUNT_DIR}
ExecStart=/bin/sh -c 'ALLOW_OTHER=""; [ "${GATE_FUSE_ALLOW_OTHER}" = "1" ] && ALLOW_OTHER="--allow-other"; if [ -x /opt/gate/bin/gate ]; then /opt/gate/bin/gate mount --root "${GATE_REPO_DIR}" --mount "${GATE_MOUNT_DIR}" --broker-host "${GATE_BROKER_HOST}" --broker-port "${GATE_BROKER_PORT}" --max-hold-ms "${GATE_MAX_HOLD_MS}" ${ALLOW_OTHER}; else /usr/bin/python3 "${GATE_REPO_DIR}/scripts/gate_mount.py" --root "${GATE_REPO_DIR}" --mount "${GATE_MOUNT_DIR}" --broker-host "${GATE_BROKER_HOST}" --broker-port "${GATE_BROKER_PORT}" --max-hold-ms "${GATE_MAX_HOLD_MS}" ${ALLOW_OTHER}; fi'
Restart=always
User=gate
Group=gate

[Install]
WantedBy=multi-user.target
"""

USER_DATA_TEMPLATE = """#cloud-config
package_update: true
packages:
  - fuse
  - openssh-server
  - python3
  - python3-pip
  - git
  - rsync
  - curl
  - ca-certificates

users:
  - name: gate
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    ssh_authorized_keys:
      - __SSH_KEY__

runcmd:
  - mkdir -p /var/lib/gate /mnt/gate /etc/gate /opt/target
  - chown gate:gate /var/lib/gate /mnt/gate /opt/target
  - __CLONE_BLOCK__
  - systemctl enable --now ssh
  - __ENABLE_GATE_UNITS__
"""

META_DATA_TEMPLATE = """instance-id: __VM_NAME__
local-hostname: __VM_NAME__
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gate")
    parser.add_argument("--version", action="version", version=f"gate {get_version()}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    broker = subparsers.add_parser("broker", help="Run the lock broker server")
    broker.add_argument("--state-dir", default=BrokerConfig().state_dir)
    broker.add_argument("--host", default=BrokerConfig().host)
    broker.add_argument("--port", type=int, default=BrokerConfig().port)
    broker.add_argument("--lease-ms", type=int, default=BrokerConfig().lease_ms)
    broker.add_argument("--max-hold-ms", type=int, default=BrokerConfig().max_hold_ms)
    broker.add_argument("--acquire-timeout-ms", type=int, default=BrokerConfig().acquire_timeout_ms)

    mount = subparsers.add_parser("mount", help="Mount the Gate FUSE filesystem")
    mount.add_argument("--root", required=True, help="Real repo root (read-only to users)")
    mount.add_argument("--mount", required=True, help="Mount point for the FUSE view")
    mount.add_argument("--broker-host", default=BrokerConfig().host)
    mount.add_argument("--broker-port", type=int, default=BrokerConfig().port)
    mount.add_argument("--lease-ms", type=int, default=BrokerConfig().lease_ms)
    mount.add_argument("--max-hold-ms", type=int, default=BrokerConfig().max_hold_ms)
    mount.add_argument("--acquire-timeout-ms", type=int, default=BrokerConfig().acquire_timeout_ms)
    mount.add_argument("--foreground", action="store_true")
    mount.add_argument("--owner", default=None)
    mount.add_argument("--allow-other", action="store_true", help="Allow non-mount users to access the FUSE view")

    bundle_build = subparsers.add_parser("bundle-build", help="Build a Gate bundle tarball")
    bundle_build.add_argument("--binary", default=None, help="Path to gate binary")
    bundle_build.add_argument("--out", default="./dist/gate_bundle.tar.gz")

    build_binary = subparsers.add_parser("build-binary", help="Build a standalone gate executable")
    build_binary.add_argument("--name", default="gate")
    build_binary.add_argument("--out-dir", default="./dist")
    build_binary.add_argument("--build-dir", default="./.build_gate")
    build_binary.add_argument("--python", default=None, help="Python interpreter to use")

    bundle_install = subparsers.add_parser("bundle-install", help="Install a Gate bundle (run inside VM)")
    bundle_install.add_argument("--prefix", default="/opt/gate")
    bundle_install.add_argument("--target-dir", default="/opt/target")
    bundle_install.add_argument("--state-dir", default="/var/lib/gate")
    bundle_install.add_argument("--mount-dir", default="/mnt/gate")
    bundle_install.add_argument("--start-gate", action="store_true")

    vm_build = subparsers.add_parser("vm-build", help="Build a VM image (QEMU/KVM)")
    vm_build.add_argument(
        "--base",
        default="ubuntu-22.04",
        choices=["ubuntu-22.04", "ubuntu-24.04", "debian-12"],
    )
    vm_build.add_argument("--vm-dir", default="./vm_build")
    vm_build.add_argument("--vm-name", default="gate-vm")
    vm_build.add_argument("--repo-url", default=None)
    vm_build.add_argument("--repo-branch", default="main")
    vm_build.add_argument("--ssh-key", required=True)
    vm_build.add_argument("--disk-size", default=None)
    vm_build.add_argument("--no-clone", action="store_true")
    vm_build.add_argument("--redownload", action="store_true", help="Force re-download of base image")

    vm_run = subparsers.add_parser("vm-run", help="Run a VM (QEMU/KVM)")
    vm_run.add_argument("--vm-dir", required=True)
    vm_run.add_argument("--vm-name", required=True)
    vm_run.add_argument("--ssh-port", default="2222")
    vm_run.add_argument("--memory", default="4096")
    vm_run.add_argument("--cpus", default="2")
    vm_run.add_argument("--nfs-port", type=int, default=None, help="Forward host port to guest 2049 for NFS")

    up = subparsers.add_parser("up", help="Run full end-to-end workflow with logs")
    up.add_argument("--vm-name", default="gate-vm")
    up.add_argument("--vm-dir", default="./vm_build")
    up.add_argument("--base", default="ubuntu-22.04")
    up.add_argument("--ssh-key", required=True)
    up.add_argument("--ssh-port", type=int, default=2222)
    up.add_argument("--disk-size", default="20G")
    up.add_argument("--redownload", action="store_true")
    up.add_argument("--repo-path", required=True)
    up.add_argument("--vm-repo-path", default="/opt/target")
    up.add_argument("--binary", default=None, help="Path to gate binary (defaults to `which gate`)")
    up.add_argument("--host-mount", default=None)
    up.add_argument(
        "--host-mount-method",
        choices=["sshfs", "nfs"],
        default="sshfs",
        help="How to mount the VM view on the host",
    )
    up.add_argument("--accept-host-key", action="store_true", default=True)
    up.add_argument("--strict-host-key", action="store_true")
    up.add_argument("--ssh-timeout", type=int, default=180)
    up.add_argument("--memory", default="4096")
    up.add_argument("--cpus", default="2")
    up.add_argument("--nfs-port", type=int, default=2049)
    up.add_argument("--max-hold-ms", type=int, default=BrokerConfig().max_hold_ms)
    up.add_argument("--skip-build", action="store_true")
    up.add_argument("--skip-host-mount", action="store_true")
    up.add_argument("--verbose", action="store_true")
    up.add_argument("--dry-run", action="store_true")
    up.add_argument("--keep-vm-on-error", action="store_true")

    status = subparsers.add_parser("status", help="Show status of VM, broker, and mounts")
    status.add_argument("--vm-name", default="gate-vm")
    status.add_argument("--vm-dir", default="./vm_build")
    status.add_argument("--vm-user", default="gate")
    status.add_argument("--vm-host", default="127.0.0.1")
    status.add_argument("--ssh-port", type=int, default=2222)
    status.add_argument("--host-mount", default=None)

    logs = subparsers.add_parser("logs", help="Show log file paths or tail logs")
    logs.add_argument("--vm-name", default="gate-vm")
    logs.add_argument("--component", default="all")
    logs.add_argument("--tail", type=int, default=200)

    vm_list = subparsers.add_parser("vm-list", help="List known VMs from local state")

    down = subparsers.add_parser("down", help="Stop a running VM and unmount host view")
    down.add_argument("--vm-name", default=None)
    down.add_argument("--force", action="store_true")
    down.add_argument("--skip-unmount", action="store_true")

    host = subparsers.add_parser(
        "host-provision",
        help="Install Gate bundle in a VM and sync a repo from the host",
    )
    host.add_argument("--vm-user", required=True)
    host.add_argument("--vm-host", required=True)
    host.add_argument("--ssh-port", type=int, default=22)
    host.add_argument("--binary", default=None, help="Path to gate binary (defaults to `which gate`)")
    host.add_argument("--bundle", default=None, help="Path to gate_bundle.tar.gz")
    host.add_argument("--target-dir", default="/opt/target")
    host.add_argument("--repo-path", default=None, help="Host repo path to sync")
    host.add_argument("--vm-repo-path", default=None, help="VM repo path (default: --target-dir)")
    host.add_argument("--start-gate", action="store_true")

    host_mount = subparsers.add_parser("host-mount", help="Mount a VM gate view on the host")
    host_mount.add_argument("--vm-user", required=True)
    host_mount.add_argument("--vm-host", required=True)
    host_mount.add_argument("--ssh-port", type=int, default=22)
    host_mount.add_argument("--vm-mount", default="/mnt/gate")
    host_mount.add_argument("--host-mount", required=True)
    host_mount.add_argument(
        "--method",
        "--host-mount-method",
        dest="host_mount_method",
        choices=["sshfs", "nfs"],
        default="sshfs",
        help="Mount method to use",
    )
    host_mount.add_argument("--nfs-port", type=int, default=2049)
    host_mount.add_argument("--known-hosts")
    host_mount.add_argument("--accept-host-key", action="store_true")

    return parser


def _require_cmd(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"Required command not found: {name}")


def _require_nfs_mount_helper() -> None:
    if shutil.which("mount.nfs4") is None and shutil.which("mount.nfs") is None:
        raise RuntimeError("NFS mount helper not found (install nfs-common)")


def _sudo_prefix() -> list[str]:
    override = os.environ.get("GATE_SUDO_CMD")
    if override:
        return shlex.split(override)
    return ["sudo"]


def _maybe_sudo(cmd: list[str]) -> list[str]:
    if os.geteuid() == 0:
        return cmd
    prefix = _sudo_prefix()
    if not prefix:
        raise RuntimeError("GATE_SUDO_CMD resolved to an empty command")
    if shutil.which(prefix[0]) is None:
        raise RuntimeError(
            f"Sudo command not found (required for host mount): {prefix[0]}"
        )
    return [*prefix, *cmd]


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _run_logged(
    cmd: list[str],
    log_path: Path,
    verbose: bool = False,
    env: dict[str, str] | None = None,
) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as log:
        if verbose:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                log.write(line)
                log.flush()
                print(line, end="")
            ret = proc.wait()
            if ret != 0:
                raise subprocess.CalledProcessError(ret, cmd)
        else:
            subprocess.run(cmd, check=True, stdout=log, stderr=log, env=env)


def _run_background(cmd: list[str], log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = open(log_path, "a", encoding="utf-8")
    subprocess.Popen(cmd, stdout=log, stderr=log)


def _find_repo_root() -> Path | None:
    here = Path(__file__).resolve()
    for parent in [here] + list(here.parents):
        if (parent / "systems" / "gate_vm" / "systemd" / "gate-broker.service").exists():
            return parent
    return None


def _state_home() -> Path:
    base = os.environ.get("XDG_STATE_HOME", "~/.local/state")
    return Path(base).expanduser()


def _gate_state_dir(vm_name: str) -> Path:
    return _state_home() / "gate" / "state" / vm_name


def _gate_log_dir(vm_name: str) -> Path:
    return _state_home() / "gate" / "logs" / vm_name


def _gate_mount_dir(vm_name: str) -> Path:
    return _state_home() / "gate" / "mounts" / vm_name


def _qemu_command(
    vm_dir: Path,
    vm_name: str,
    ssh_port: str,
    memory: str,
    cpus: str,
    nfs_port: int | None = None,
) -> list[str]:
    root_disk = vm_dir / f"{vm_name}.qcow2"
    seed_img = vm_dir / f"{vm_name}-seed.img"
    hostfwd = [f"hostfwd=tcp::{ssh_port}-:22"]
    if nfs_port is not None:
        hostfwd.append(f"hostfwd=tcp::{nfs_port}-:2049")
    netdev = f"user,id=net0,{','.join(hostfwd)}"
    return [
        "qemu-system-x86_64",
        "-enable-kvm",
        "-m",
        str(memory),
        "-smp",
        str(cpus),
        "-drive",
        f"file={root_disk},if=virtio,format=qcow2",
        "-drive",
        f"file={seed_img},if=virtio,format=raw",
        "-netdev",
        netdev,
        "-device",
        "virtio-net-pci,netdev=net0",
        "-nographic",
    ]


def _ssh_base_args(ssh_port: int, known_hosts: Path | None, accept_host_key: bool) -> list[str]:
    args = ["-p", str(ssh_port)]
    if known_hosts is not None:
        args += ["-o", f"UserKnownHostsFile={known_hosts}"]
    if accept_host_key:
        args += ["-o", "StrictHostKeyChecking=accept-new"]
    return args


def _ssh_command(
    ssh_port: int,
    known_hosts: Path | None,
    accept_host_key: bool,
    user_host: str,
    remote_cmd: str,
) -> list[str]:
    return ["ssh", *_ssh_base_args(ssh_port, known_hosts, accept_host_key), user_host, remote_cmd]


def _ssh_shell_command(command: str) -> str:
    return f"sh -lc {shlex.quote(command)}"


def _list_vm_names() -> list[str]:
    state_root = _state_home() / "gate" / "state"
    if not state_root.exists():
        return []
    return sorted([p.name for p in state_root.iterdir() if p.is_dir()])


def _is_pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _unmount_path(path: Path) -> None:
    try:
        exists = path.exists()
    except OSError as exc:
        if exc.errno == errno.ENOTCONN:
            exists = True
        else:
            raise
    if not exists:
        return
    with open("/proc/mounts", "r", encoding="utf-8") as mounts:
        if not any(str(path) in line for line in mounts):
            return
    if shutil.which("fusermount3"):
        _run(["fusermount3", "-u", str(path)])
        return
    if shutil.which("fusermount"):
        _run(["fusermount", "-u", str(path)])
        return
    try:
        _run(["umount", str(path)])
    except subprocess.CalledProcessError:
        try:
            _run(_maybe_sudo(["umount", str(path)]))
            return
        except RuntimeError:
            pass
        raise


def _ensure_mount_dir(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        if exc.errno == errno.ENOTCONN:
            _unmount_path(path)
            path.mkdir(parents=True, exist_ok=True)
        else:
            raise


def _wait_for_ssh(
    vm_user: str,
    vm_host: str,
    ssh_port: int,
    known_hosts: Path | None,
    accept_host_key: bool,
    timeout_seconds: int,
    log_path: Path,
    verbose: bool,
) -> None:
    start = time.monotonic()
    while True:
        if time.monotonic() - start > timeout_seconds:
            raise RuntimeError("Timed out waiting for SSH")
        cmd = [
            "ssh",
            *_ssh_base_args(ssh_port, known_hosts, accept_host_key),
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=5",
            f"{vm_user}@{vm_host}",
            "echo",
            "ok",
        ]
        try:
            _run_logged(cmd, log_path, verbose)
            return
        except subprocess.CalledProcessError:
            time.sleep(2)


def _gate_bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent.parent
    repo_root = _find_repo_root()
    if repo_root is None:
        raise RuntimeError("Unable to locate repo root for bundle install")
    return repo_root


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _load_template(path: Path, fallback: str) -> str:
    try:
        return path.read_text()
    except OSError:
        return fallback


def _format_eta(seconds: float) -> str:
    if seconds <= 0:
        return "0s"
    mins, secs = divmod(int(seconds), 60)
    if mins < 60:
        return f"{mins}m{secs:02d}s"
    hours, mins = divmod(mins, 60)
    return f"{hours}h{mins:02d}m"


def _download_with_progress(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as resp, open(dest, "wb") as out:
        total = resp.headers.get("Content-Length")
        total_bytes = int(total) if total and total.isdigit() else None
        downloaded = 0
        start = time.monotonic()
        last_print = start
        chunk_size = 1024 * 1024
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            out.write(chunk)
            downloaded += len(chunk)
            now = time.monotonic()
            if now - last_print < 0.5:
                continue
            last_print = now
            elapsed = now - start
            rate = downloaded / elapsed if elapsed > 0 else 0.0
            if total_bytes:
                pct = (downloaded / total_bytes) * 100
                remaining = total_bytes - downloaded
                eta = remaining / rate if rate > 0 else 0.0
                print(
                    f"\rDownloading {dest.name}: {pct:5.1f}% "
                    f"({downloaded/1024/1024:.1f}MB/{total_bytes/1024/1024:.1f}MB) "
                    f"ETA { _format_eta(eta) }",
                    end="",
                    flush=True,
                )
            else:
                print(
                    f"\rDownloading {dest.name}: {downloaded/1024/1024:.1f}MB",
                    end="",
                    flush=True,
                )
        print()


def main(argv: Iterable[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "broker":
        config = BrokerConfig(
            state_dir=args.state_dir,
            host=args.host,
            port=args.port,
            lease_ms=args.lease_ms,
            max_hold_ms=args.max_hold_ms,
            acquire_timeout_ms=args.acquire_timeout_ms,
        )
        server = LockBrokerServer(config)
        server.serve_forever()
        return

    if args.command == "mount":
        from .fuse_fs import mount_fuse

        owner = args.owner
        if owner is None:
            owner = f"{socket.gethostname()}:{os.getpid()}"
        endpoint = BrokerEndpoint(host=args.broker_host, port=args.broker_port)
        client = LockBrokerClient(endpoint, timeout_seconds=None)
        enable_export = args.allow_other
        mount_fuse(
            root=args.root,
            mountpoint=args.mount,
            broker=client,
            owner=owner,
            lease_ms=args.lease_ms,
            acquire_timeout_ms=args.acquire_timeout_ms,
            max_hold_ms=args.max_hold_ms,
            foreground=args.foreground,
            allow_other=args.allow_other,
            default_permissions=enable_export,
            use_ino=enable_export,
        )
        return

    if args.command == "bundle-build":
        if args.binary is None:
            if getattr(sys, "frozen", False):
                binary_path = Path(sys.executable).resolve()
            else:
                parser.error("--binary is required when not running from a built gate executable")
        else:
            binary_path = Path(args.binary).expanduser()
        if not binary_path.exists():
            parser.error(f"Binary not found: {binary_path}")

        repo_root = _find_repo_root()
        systemd_dir = None
        config_dir = None
        if repo_root is not None:
            systemd_dir = repo_root / "systems" / "gate_vm" / "systemd"
            config_dir = systemd_dir

        broker_service = _load_template(
            (systemd_dir / "gate-broker.service") if systemd_dir else Path(),
            GATE_BROKER_SERVICE_TEMPLATE,
        )
        fuse_service = _load_template(
            (systemd_dir / "gate-fuse.service") if systemd_dir else Path(),
            GATE_FUSE_SERVICE_TEMPLATE,
        )
        gate_env = _load_template(
            (config_dir / "gate.env") if config_dir else Path(),
            GATE_ENV_TEMPLATE,
        )

        out_path = Path(args.out).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            bin_dir = tmp / "bin"
            systemd_out = tmp / "systemd"
            config_out = tmp / "config"
            bin_dir.mkdir(parents=True, exist_ok=True)
            systemd_out.mkdir(parents=True, exist_ok=True)
            config_out.mkdir(parents=True, exist_ok=True)

            shutil.copy2(binary_path, bin_dir / "gate")
            os.chmod(bin_dir / "gate", 0o755)

            _write_file(systemd_out / "gate-broker.service", broker_service)
            _write_file(systemd_out / "gate-fuse.service", fuse_service)
            _write_file(config_out / "gate.env", gate_env)

            with tarfile.open(out_path, "w:gz") as tar:
                tar.add(tmp, arcname=".")

        print(f"Built bundle: {out_path}")
        return

    if args.command == "build-binary":
        repo_root = _find_repo_root()
        if repo_root is None:
            parser.error("build-binary requires running from the Gate source repo")
        python_bin = args.python or sys.executable
        _require_cmd(python_bin)
        build_dir = Path(args.build_dir).expanduser()
        out_dir = Path(args.out_dir).expanduser()
        entrypoint = repo_root / "scripts" / "gate_cli.py"
        if not entrypoint.exists():
            parser.error("Missing scripts/gate_cli.py in repo")
        venv_dir = build_dir / "venv"
        work_dir = build_dir / "pyinstaller"
        spec_dir = build_dir / "spec"

        out_dir.mkdir(parents=True, exist_ok=True)
        build_dir.mkdir(parents=True, exist_ok=True)

        _run([python_bin, "-m", "venv", str(venv_dir)])
        pip_bin = venv_dir / "bin" / "pip"
        py_bin = venv_dir / "bin" / "python"
        _run([str(pip_bin), "install", "--upgrade", "pip"])
        _run([str(pip_bin), "install", "-r", str(repo_root / "requirements.txt"), "pyinstaller"])

        _run(
            [
                str(py_bin),
                "-m",
                "PyInstaller",
                "--onefile",
                "--name",
                args.name,
                "--paths",
                str(repo_root / "src"),
                "--distpath",
                str(out_dir),
                "--workpath",
                str(work_dir),
                "--specpath",
                str(spec_dir),
                str(entrypoint),
            ]
        )
        print(f"Built binary: {out_dir / args.name}")
        return

    if args.command == "bundle-install":
        bundle_root = _gate_bundle_root()
        prefix = Path(args.prefix)
        systemd_dir = bundle_root / "systemd"
        config_dir = bundle_root / "config"
        bin_dir = bundle_root / "bin"

        if not (bin_dir / "gate").exists():
            raise RuntimeError(f"Gate binary not found at {bin_dir / 'gate'}")

        prefix.mkdir(parents=True, exist_ok=True)
        etc_gate = Path("/etc/gate")
        etc_gate.mkdir(parents=True, exist_ok=True)

        for sub in ["bin", "systemd", "config"]:
            src = bundle_root / sub
            dst = prefix / sub
            if src.exists():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)

        shutil.copy2(prefix / "systemd" / "gate-broker.service", Path("/etc/systemd/system/gate-broker.service"))
        shutil.copy2(prefix / "systemd" / "gate-fuse.service", Path("/etc/systemd/system/gate-fuse.service"))
        shutil.copy2(prefix / "config" / "gate.env", etc_gate / "gate.env")

        os.chmod(prefix / "bin" / "gate", 0o755)

        env_path = etc_gate / "gate.env"
        env_lines = env_path.read_text().splitlines()
        replacements = {
            "GATE_STATE_DIR": args.state_dir,
            "GATE_MOUNT_DIR": args.mount_dir,
            "GATE_REPO_DIR": args.target_dir,
        }
        out_lines: list[str] = []
        for line in env_lines:
            if not line or line.startswith("#") or "=" not in line:
                out_lines.append(line)
                continue
            key, _ = line.split("=", 1)
            if key in replacements:
                out_lines.append(f"{key}={replacements[key]}")
            else:
                out_lines.append(line)
        env_path.write_text("\n".join(out_lines) + "\n")

        _run(["systemctl", "daemon-reload"])
        if args.start_gate:
            _run(["systemctl", "enable", "--now", "gate-broker.service"])
            _run(["systemctl", "enable", "--now", "gate-fuse.service"])
        return

    if args.command == "vm-build":
        _require_cmd("cloud-localds")
        _require_cmd("qemu-img")

        base_url = ""
        base_file = ""
        if args.base == "ubuntu-22.04":
            base_url = "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"
            base_file = "ubuntu-22.04-base.qcow2"
        elif args.base == "ubuntu-24.04":
            base_url = "https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img"
            base_file = "ubuntu-24.04-base.qcow2"
        elif args.base == "debian-12":
            base_url = "https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-genericcloud-amd64.qcow2"
            base_file = "debian-12-base.qcow2"

        vm_dir = Path(args.vm_dir).expanduser()
        vm_dir.mkdir(parents=True, exist_ok=True)
        base_path = vm_dir / base_file
        root_path = vm_dir / f"{args.vm_name}.qcow2"
        seed_path = vm_dir / f"{args.vm_name}-seed.img"
        user_data = vm_dir / "user-data"
        meta_data = vm_dir / "meta-data"

        if not Path(args.ssh_key).expanduser().is_file():
            parser.error(f"SSH key not found: {args.ssh_key}")

        if args.redownload and base_path.exists():
            base_path.unlink()

        if not base_path.exists():
            _download_with_progress(base_url, base_path)

        shutil.copy2(base_path, root_path)
        if args.disk_size:
            _run(["qemu-img", "resize", str(root_path), args.disk_size])

        ssh_key = Path(args.ssh_key).expanduser().read_text().strip()

        do_clone = args.repo_url is not None and not args.no_clone
        if not do_clone:
            clone_block = "# no clone"
            enable_units = "# no gate units"
        else:
            clone_block = (
                f"git clone --branch {args.repo_branch} {args.repo_url} /opt/gate"
            )
            enable_units = (
                "cp /opt/gate/systems/gate_vm/systemd/gate.env /etc/gate/gate.env\n"
                "  - cp /opt/gate/systems/gate_vm/systemd/gate-broker.service /etc/systemd/system/gate-broker.service\n"
                "  - cp /opt/gate/systems/gate_vm/systemd/gate-fuse.service /etc/systemd/system/gate-fuse.service\n"
                "  - systemctl daemon-reload\n"
                "  - systemctl enable --now gate-broker.service\n"
                "  - systemctl enable --now gate-fuse.service"
            )

        user_rendered = USER_DATA_TEMPLATE.replace("__SSH_KEY__", ssh_key)
        user_rendered = user_rendered.replace("__CLONE_BLOCK__", clone_block)
        user_rendered = user_rendered.replace("__ENABLE_GATE_UNITS__", enable_units)
        user_data.write_text(user_rendered)
        meta_data.write_text(
            META_DATA_TEMPLATE.replace("__VM_NAME__", args.vm_name)
        )

        _run(["cloud-localds", str(seed_path), str(user_data), str(meta_data)])
        print(f"VM image ready: {root_path}")
        print(f"Seed image ready: {seed_path}")
        return

    if args.command == "vm-run":
        _require_cmd("qemu-system-x86_64")
        vm_dir = Path(args.vm_dir).expanduser()
        root_disk = vm_dir / f"{args.vm_name}.qcow2"
        seed_img = vm_dir / f"{args.vm_name}-seed.img"
        if not root_disk.exists() or not seed_img.exists():
            parser.error("Missing root disk or seed image in vm-dir")
        _run(
            _qemu_command(
                vm_dir,
                args.vm_name,
                args.ssh_port,
                args.memory,
                args.cpus,
                args.nfs_port,
            )
        )
        return

    if args.command == "up":
        vm_dir = Path(args.vm_dir).expanduser()
        vm_dir.mkdir(parents=True, exist_ok=True)
        log_dir = _gate_log_dir(args.vm_name)
        state_dir = _gate_state_dir(args.vm_name)
        state_dir.mkdir(parents=True, exist_ok=True)
        known_hosts = state_dir / "known_hosts"

        accept_host_key = not args.strict_host_key

        started_vm = False

        if args.dry_run:
            nfs_port = args.nfs_port if args.host_mount_method == "nfs" else None
            qemu_cmd = _qemu_command(
                vm_dir,
                args.vm_name,
                str(args.ssh_port),
                args.memory,
                args.cpus,
                nfs_port,
            )
            print("Dry run:")
            print(f"- vm-build (base={args.base}, vm-dir={vm_dir}, vm-name={args.vm_name})")
            print(f"- vm-run: {' '.join(qemu_cmd)}")
            print(f"- wait for ssh: gate@127.0.0.1:{args.ssh_port}")
            deps = "apt-get update && apt-get install -y fuse3 libfuse3-3"
            if args.host_mount_method == "nfs":
                deps += " nfs-kernel-server"
            print(f"- install deps: {deps}")
            print(f"- copy binary: {args.binary or '$(which gate)'} -> /opt/gate/bin/gate")
            print(f"- rsync repo: {args.repo_path} -> {args.vm_repo_path}")
            print("- start broker: /opt/gate/bin/gate broker --port 8787")
            print("- start mount: /opt/gate/bin/gate mount --root <repo> --mount /mnt/gate")
            if not args.skip_host_mount:
                host_mount = Path(args.host_mount).expanduser() if args.host_mount else _gate_mount_dir(args.vm_name)
                if args.host_mount_method == "nfs":
                    print(
                        f"- host mount: sudo mount -t nfs4 -o vers=4,proto=tcp,port={args.nfs_port} "
                        f"127.0.0.1:/mnt/gate {host_mount}"
                    )
                else:
                    print(f"- host mount: /mnt/gate -> {host_mount}")
            print(f"- logs: {log_dir}")
            return

        pid_file = state_dir / "vm.pid"
        try:
            # Step 1: Build VM if needed
            root_disk = vm_dir / f"{args.vm_name}.qcow2"
            seed_img = vm_dir / f"{args.vm_name}-seed.img"
            if not args.skip_build and (not root_disk.exists() or not seed_img.exists()):
                if getattr(sys, "frozen", False):
                    build_cmd = [
                        sys.executable,
                        "vm-build",
                    ]
                    env = None
                else:
                    build_cmd = [
                        sys.executable,
                        "-m",
                        "gate.cli",
                        "vm-build",
                    ]
                    env = os.environ.copy()
                    repo_root = _find_repo_root()
                    if repo_root is not None:
                        env.setdefault("PYTHONPATH", str(repo_root / "src"))
                build_cmd += [
                    "--base",
                    args.base,
                    "--vm-dir",
                    str(vm_dir),
                    "--vm-name",
                    args.vm_name,
                    "--ssh-key",
                    args.ssh_key,
                    "--disk-size",
                    args.disk_size,
                ]
                if args.redownload:
                    build_cmd.append("--redownload")
                _run_logged(build_cmd, log_dir / "vm-build.log", args.verbose, env=env)

            # Step 2: Run VM in background if not running
            if pid_file.exists():
                try:
                    pid = int(pid_file.read_text().strip())
                    os.kill(pid, 0)
                except Exception:
                    pid_file.unlink(missing_ok=True)
            if not pid_file.exists():
                _require_cmd("qemu-system-x86_64")
                nfs_port = args.nfs_port if args.host_mount_method == "nfs" else None
                qemu_cmd = _qemu_command(
                    vm_dir,
                    args.vm_name,
                    str(args.ssh_port),
                    args.memory,
                    args.cpus,
                    nfs_port,
                )
                log_path = log_dir / "vm-run.log"
                log_path.parent.mkdir(parents=True, exist_ok=True)
                with open(log_path, "a", encoding="utf-8") as log:
                    proc = subprocess.Popen(qemu_cmd, stdout=log, stderr=log)
                pid_file.write_text(str(proc.pid))
                started_vm = True

            # Step 3: Wait for SSH
            _wait_for_ssh(
                vm_user="gate",
                vm_host="127.0.0.1",
                ssh_port=args.ssh_port,
                known_hosts=known_hosts,
                accept_host_key=accept_host_key,
                timeout_seconds=args.ssh_timeout,
                log_path=log_dir / "ssh.log",
                verbose=args.verbose,
            )

            # Step 4: Ensure libfuse in VM
            _run_logged(
                _ssh_command(
                    args.ssh_port,
                    known_hosts,
                    accept_host_key,
                    "gate@127.0.0.1",
                    "sudo env DEBIAN_FRONTEND=noninteractive apt-get update",
                ),
                log_dir / "deps.log",
                args.verbose,
            )
            vm_deps = "fuse3 libfuse3-3 libfuse2"
            if args.host_mount_method == "nfs":
                vm_deps += " nfs-kernel-server"
            _run_logged(
                _ssh_command(
                    args.ssh_port,
                    known_hosts,
                    accept_host_key,
                    "gate@127.0.0.1",
                    f"sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y {vm_deps}",
                ),
                log_dir / "deps.log",
                args.verbose,
            )
            _run_logged(
                _ssh_command(
                    args.ssh_port,
                    known_hosts,
                    accept_host_key,
                    "gate@127.0.0.1",
                _ssh_shell_command(
                    "sudo mkdir -p /var/lib/gate /opt/target; "
                    "if ! grep -q ' /mnt/gate ' /proc/mounts; then sudo mkdir -p /mnt/gate; fi; "
                    "if ! grep -q '^user_allow_other' /etc/fuse.conf 2>/dev/null; then "
                    "echo 'user_allow_other' | sudo tee -a /etc/fuse.conf >/dev/null; fi"
                ),
            ),
            log_dir / "deps.log",
            args.verbose,
        )
            if args.host_mount_method == "nfs":
                export_line = (
                    "/mnt/gate 10.0.2.2/32"
                    "(rw,sync,no_subtree_check,no_root_squash,insecure)"
                )
                _run_logged(
                    _ssh_command(
                        args.ssh_port,
                        known_hosts,
                        accept_host_key,
                        "gate@127.0.0.1",
                        _ssh_shell_command(
                            "sudo mkdir -p /etc/exports.d && "
                            f"echo {shlex.quote(export_line)} | sudo tee /etc/exports.d/gate.exports >/dev/null && "
                            "sudo exportfs -ra && "
                            "sudo systemctl enable --now nfs-kernel-server"
                        ),
                    ),
                    log_dir / "deps.log",
                    args.verbose,
                )

            # Step 5: Install gate binary into VM
            if args.binary is not None:
                binary_path = Path(args.binary).expanduser()
            elif getattr(sys, "frozen", False):
                binary_path = Path(sys.executable).resolve()
            else:
                found = shutil.which("gate")
                binary_path = Path(found) if found else None
            if binary_path is None or not binary_path.is_file():
                parser.error("gate binary not found; provide --binary or ensure it is on PATH")
            scp_args = ["-P", str(args.ssh_port), "-o", f"UserKnownHostsFile={known_hosts}"]
            if accept_host_key:
                scp_args += ["-o", "StrictHostKeyChecking=accept-new"]
            _run_logged(
                [
                    "scp",
                    *scp_args,
                    str(binary_path),
                    "gate@127.0.0.1:/tmp/gate",
                ],
                log_dir / "copy.log",
                args.verbose,
            )
            _run_logged(
                [
                    "ssh",
                    *_ssh_base_args(args.ssh_port, known_hosts, accept_host_key),
                    "gate@127.0.0.1",
                    "sudo",
                    "install",
                    "-m",
                    "0755",
                    "/tmp/gate",
                    "/opt/gate/bin/gate",
                ],
                log_dir / "copy.log",
                args.verbose,
            )

            # Step 6: Sync repo into VM
            repo_path = Path(args.repo_path).expanduser()
            if not repo_path.is_dir():
                parser.error(f"Repo path not found: {repo_path}")
            _run_logged(
                [
                    "rsync",
                    "-a",
                    "--delete",
                    "--info=progress2",
                    "-e",
                    (
                        f"ssh -p {args.ssh_port} -o UserKnownHostsFile={known_hosts} "
                        + ("-o StrictHostKeyChecking=accept-new" if accept_host_key else "")
                    ),
                    f"{repo_path}/",
                    f"gate@127.0.0.1:{args.vm_repo_path}/",
                ],
                log_dir / "rsync.log",
                args.verbose,
            )

            # Step 7: Start broker and mount in VM
            _run_logged(
                _ssh_command(
                    args.ssh_port,
                    known_hosts,
                    accept_host_key,
                    "gate@127.0.0.1",
                    _ssh_shell_command(
                        "nohup /opt/gate/bin/gate broker --state-dir /var/lib/gate --host 127.0.0.1 --port 8787 "
                        f"--max-hold-ms {args.max_hold_ms} "
                        "> /var/lib/gate/broker.log 2>&1 &"
                    ),
                ),
                log_dir / "broker.log",
                args.verbose,
            )
            _run_logged(
                _ssh_command(
                    args.ssh_port,
                    known_hosts,
                    accept_host_key,
                    "gate@127.0.0.1",
                    _ssh_shell_command(
                        "nohup /opt/gate/bin/gate mount "
                        f"--root {shlex.quote(args.vm_repo_path)} --mount /mnt/gate "
                        "--broker-host 127.0.0.1 --broker-port 8787 "
                        f"--max-hold-ms {args.max_hold_ms} "
                        + ("--allow-other " if args.host_mount_method == "nfs" else "")
                        + "> /var/lib/gate/fuse.log 2>&1 &"
                    ),
                ),
                log_dir / "mount.log",
                args.verbose,
            )

            # Step 8: Host mount
            if not args.skip_host_mount:
                host_mount = Path(args.host_mount).expanduser() if args.host_mount else _gate_mount_dir(args.vm_name)
                _ensure_mount_dir(host_mount)
                if args.host_mount_method == "nfs":
                    _require_nfs_mount_helper()
                    mount_cmd = _maybe_sudo(
                        [
                            "mount",
                            "-t",
                            "nfs4",
                            "-o",
                            f"vers=4,proto=tcp,port={args.nfs_port}",
                            "127.0.0.1:/mnt/gate",
                            str(host_mount),
                        ]
                    )
                    _run_logged(mount_cmd, log_dir / "host-mount.log", args.verbose)
                else:
                    _require_cmd("sshfs")
                    sshfs_cmd = ["sshfs", "-o", f"port={args.ssh_port}"]
                    if known_hosts is not None:
                        sshfs_cmd += ["-o", f"UserKnownHostsFile={known_hosts}"]
                    if accept_host_key:
                        sshfs_cmd += ["-o", "StrictHostKeyChecking=accept-new"]
                    sshfs_cmd += [f"gate@127.0.0.1:/mnt/gate", str(host_mount)]
                    _run_background(sshfs_cmd, log_dir / "host-mount.log")

            print(f"Gate up complete. Logs: {log_dir}")
            return
        except Exception:
            if not args.keep_vm_on_error and started_vm and pid_file.exists():
                try:
                    pid = int(pid_file.read_text().strip())
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(2)
                    try:
                        os.kill(pid, 0)
                        os.kill(pid, signal.SIGKILL)
                    except OSError:
                        pass
                except Exception:
                    pass
                pid_file.unlink(missing_ok=True)
            raise

    if args.command == "status":
        vm_name = args.vm_name
        state_dir = _gate_state_dir(vm_name)
        log_dir = _gate_log_dir(vm_name)
        host_mount = Path(args.host_mount).expanduser() if args.host_mount else _gate_mount_dir(vm_name)
        known_hosts = state_dir / "known_hosts"
        print(f"Logs: {log_dir}")
        pid_file = state_dir / "vm.pid"
        if pid_file.exists():
            pid = int(pid_file.read_text().strip())
            try:
                os.kill(pid, 0)
                print(f"VM: running (pid {pid})")
            except Exception:
                print("VM: not running (stale pid)")
        else:
            print("VM: not running")

        # SSH check
        try:
            _run(
                [
                    "ssh",
                    "-p",
                    str(args.ssh_port),
                    "-o",
                    f"UserKnownHostsFile={known_hosts}",
                    "-o",
                    "StrictHostKeyChecking=accept-new",
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    "ConnectTimeout=3",
                    f"{args.vm_user}@{args.vm_host}",
                    "echo",
                    "ok",
                ]
            )
            print("SSH: reachable")
        except Exception:
            print("SSH: unreachable")

        # Host mount check
        try:
            exists = host_mount.exists()
        except OSError as exc:
            if exc.errno == errno.ENOTCONN:
                print(f"Host mount: stale (transport endpoint not connected) ({host_mount})")
                return
            raise

        if exists:
            try:
                with open("/proc/mounts", "r", encoding="utf-8") as f:
                    mounted = any(str(host_mount) in line for line in f)
                print(f"Host mount: {'mounted' if mounted else 'not mounted'} ({host_mount})")
            except OSError:
                print(f"Host mount: {host_mount} (unknown)")
        else:
            print(f"Host mount: {host_mount} (missing)")
        return

    if args.command == "logs":
        log_dir = _gate_log_dir(args.vm_name)
        if not log_dir.exists():
            print(f"No logs at {log_dir}")
            return
        if args.component == "all":
            for path in sorted(log_dir.glob("*.log")):
                print(path)
            return
        log_path = log_dir / f"{args.component}.log"
        if not log_path.exists():
            print(f"Log not found: {log_path}")
            return
        lines = log_path.read_text().splitlines()
        tail = lines[-args.tail :] if args.tail > 0 else lines
        print("\n".join(tail))
        return

    if args.command == "vm-list":
        names = _list_vm_names()
        if not names:
            print("No VMs found.")
            return
        for name in names:
            pid_file = _gate_state_dir(name) / "vm.pid"
            status = "stopped"
            if pid_file.exists():
                try:
                    pid = int(pid_file.read_text().strip())
                    if _is_pid_running(pid):
                        status = f"running (pid {pid})"
                except Exception:
                    status = "stale pid"
            print(f"{name}\t{status}")
        return

    if args.command == "down":
        vm_names = _list_vm_names()
        if args.vm_name is None:
            if len(vm_names) == 1:
                vm_name = vm_names[0]
            elif len(vm_names) == 0:
                parser.error("No VMs found. Provide --vm-name.")
            else:
                print("Multiple VMs found. Provide --vm-name.")
                for name in vm_names:
                    print(f"  - {name}")
                return
        else:
            vm_name = args.vm_name

        state_dir = _gate_state_dir(vm_name)
        pid_file = state_dir / "vm.pid"

        if not args.skip_unmount:
            host_mount = _gate_mount_dir(vm_name)
            try:
                _unmount_path(host_mount)
            except Exception as exc:
                if not args.force:
                    raise RuntimeError(f"Failed to unmount {host_mount}: {exc}") from exc

        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                if _is_pid_running(pid):
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(2)
                    if _is_pid_running(pid):
                        os.kill(pid, signal.SIGKILL)
                pid_file.unlink(missing_ok=True)
                print(f"Stopped VM {vm_name}")
            except Exception as exc:
                if not args.force:
                    raise RuntimeError(f"Failed to stop VM {vm_name}: {exc}") from exc
        else:
            print(f"No PID file for {vm_name} (already stopped?)")
        return

    if args.command == "host-provision":
        binary_path: Path | None = None
        if args.binary is not None:
            binary_path = Path(args.binary).expanduser()
            if not binary_path.is_file():
                parser.error(f"Binary not found: {binary_path}")
        else:
            found = shutil.which("gate")
            if found:
                binary_path = Path(found)
            else:
                parser.error("gate binary not found on PATH; provide --binary")

        if args.bundle is None and args.repo_path is None and binary_path is None:
            parser.error("host-provision requires a gate binary or --repo-path")

        vm_repo_path = args.vm_repo_path or args.target_dir

        if binary_path is not None:
            _require_cmd("scp")
            _require_cmd("ssh")
            _run(
                [
                    "scp",
                    "-P",
                    str(args.ssh_port),
                    str(binary_path),
                    f"{args.vm_user}@{args.vm_host}:/tmp/gate",
                ]
            )
            _run(
                [
                    "ssh",
                    "-p",
                    str(args.ssh_port),
                    f"{args.vm_user}@{args.vm_host}",
                    "sudo",
                    "mkdir",
                    "-p",
                    "/opt/gate/bin",
                ]
            )
            _run(
                [
                    "ssh",
                    "-p",
                    str(args.ssh_port),
                    f"{args.vm_user}@{args.vm_host}",
                    "sudo",
                    "install",
                    "-m",
                    "0755",
                    "/tmp/gate",
                    "/opt/gate/bin/gate",
                ]
            )

        if args.bundle is not None:
            bundle_path = Path(args.bundle).expanduser()
            if not bundle_path.is_file():
                parser.error(f"Bundle not found: {bundle_path}")
            _require_cmd("scp")
            _require_cmd("ssh")
            _run(
                [
                    "scp",
                    "-P",
                    str(args.ssh_port),
                    str(bundle_path),
                    f"{args.vm_user}@{args.vm_host}:/tmp/gate_bundle.tar.gz",
                ]
            )
            start_flag = "--start-gate" if args.start_gate else ""
            install_cmd = (
                "sudo mkdir -p /opt/gate && "
                "sudo tar -xzf /tmp/gate_bundle.tar.gz -C /opt/gate && "
                "sudo chmod +x /opt/gate/bin/gate && "
                f"sudo /opt/gate/bin/gate bundle-install --target-dir {shlex.quote(args.target_dir)} {start_flag}"
            )
            _run(
                [
                    "ssh",
                    "-p",
                    str(args.ssh_port),
                    f"{args.vm_user}@{args.vm_host}",
                    _ssh_shell_command(install_cmd),
                ]
            )

        if args.repo_path is not None:
            repo_path = Path(args.repo_path).expanduser()
            if not repo_path.is_dir():
                parser.error(f"Repo path not found: {repo_path}")
            _require_cmd("rsync")
            _require_cmd("ssh")
            _run(
                [
                    "ssh",
                    "-p",
                    str(args.ssh_port),
                    f"{args.vm_user}@{args.vm_host}",
                    "mkdir",
                    "-p",
                    vm_repo_path,
                ]
            )
            _run(
                [
                    "rsync",
                    "-a",
                    "--delete",
                    "--info=progress2",
                    "-e",
                    f"ssh -p {args.ssh_port}",
                    f"{repo_path}/",
                    f"{args.vm_user}@{args.vm_host}:{vm_repo_path}/",
                ]
            )
        return

    if args.command == "host-mount":
        host_mount = Path(args.host_mount).expanduser()
        _ensure_mount_dir(host_mount)
        if args.host_mount_method == "nfs":
            _require_nfs_mount_helper()
            mount_cmd = _maybe_sudo(
                [
                    "mount",
                    "-t",
                    "nfs4",
                    "-o",
                    f"vers=4,proto=tcp,port={args.nfs_port}",
                    f"{args.vm_host}:{args.vm_mount}",
                    str(host_mount),
                ]
            )
            _run_logged(mount_cmd, _gate_log_dir("host-mount") / "nfs.log", True)
            print(f"NFS mount: {args.vm_host}:/ -> {host_mount}")
        else:
            _require_cmd("sshfs")
            sshfs_cmd = ["sshfs", "-o", f"port={args.ssh_port}"]
            if args.known_hosts:
                known_hosts = Path(args.known_hosts).expanduser()
                sshfs_cmd += ["-o", f"UserKnownHostsFile={known_hosts}"]
            if args.accept_host_key:
                sshfs_cmd += ["-o", "StrictHostKeyChecking=accept-new"]
            sshfs_cmd += [f"{args.vm_user}@{args.vm_host}:{args.vm_mount}", str(host_mount)]
            _run_background(sshfs_cmd, _gate_log_dir("host-mount") / "sshfs.log")
            print(f"Mount started: {args.vm_host}:{args.vm_mount} -> {host_mount}")
        return

    parser.error("Unknown command")


if __name__ == "__main__":
    main()
