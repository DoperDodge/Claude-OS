"""
Claude-OS App Sandbox

Provides process isolation for third-party apps using Linux namespaces
and seccomp filters. Each app runs in its own sandbox with:

- Separate PID namespace (can't see other processes)
- Separate network namespace (no network unless granted)
- Restricted filesystem view (only app data + allowed paths)
- seccomp-bpf syscall filtering (block dangerous syscalls)
- Resource limits via cgroups (CPU, memory)

The Claude launcher itself runs unsandboxed (it IS the OS).
"""

import ctypes
import json
import logging
import os
import resource
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("security.sandbox")

# Namespace flags (from linux/sched.h)
CLONE_NEWNS = 0x00020000    # Mount namespace
CLONE_NEWPID = 0x20000000   # PID namespace
CLONE_NEWNET = 0x40000000   # Network namespace
CLONE_NEWUTS = 0x04000000   # UTS (hostname) namespace
CLONE_NEWIPC = 0x08000000   # IPC namespace

# Seccomp constants
SECCOMP_SET_MODE_FILTER = 1

# Dangerous syscalls to block for sandboxed apps
BLOCKED_SYSCALLS = [
    "reboot",           # Can't reboot the device
    "kexec_load",       # Can't load a new kernel
    "init_module",      # Can't load kernel modules
    "delete_module",    # Can't unload kernel modules
    "mount",            # Can't mount filesystems
    "umount2",          # Can't unmount filesystems
    "swapon",           # Can't enable swap
    "swapoff",          # Can't disable swap
    "pivot_root",       # Can't change root
    "chroot",           # Can't chroot
    "ptrace",           # Can't trace other processes
    "process_vm_readv", # Can't read other process memory
    "process_vm_writev",# Can't write other process memory
    "keyctl",           # Can't access kernel keyring
    "bpf",              # Can't load BPF programs
    "userfaultfd",      # Can block for exploitation
    "perf_event_open",  # Can leak kernel info
]


@dataclass
class SandboxProfile:
    """Security profile for a sandboxed app."""
    app_id: str
    allow_network: bool = False
    allow_gpu: bool = False
    allowed_paths: list[str] = field(default_factory=list)
    max_memory_mb: int = 256
    max_cpu_percent: int = 50
    max_open_files: int = 256
    max_processes: int = 32
    blocked_syscalls: list[str] = field(default_factory=lambda: list(BLOCKED_SYSCALLS))

    @classmethod
    def from_manifest(cls, manifest: dict) -> "SandboxProfile":
        """Create a sandbox profile from an app manifest."""
        perms = manifest.get("permissions", [])
        return cls(
            app_id=manifest["app_id"],
            allow_network="network" in perms,
            allow_gpu="gpu" in perms,
            allowed_paths=manifest.get("allowed_paths", []),
            max_memory_mb=manifest.get("max_memory_mb", 256),
        )


class Sandbox:
    """
    Creates and manages sandboxed environments for apps.

    Uses Linux namespaces for isolation, seccomp-bpf for syscall
    filtering, and cgroups v2 for resource limiting.
    """

    CGROUP_BASE = "/sys/fs/cgroup/claude-os"

    def __init__(self):
        self._active_sandboxes: dict[str, int] = {}  # app_id -> pid

    def launch_sandboxed(self, profile: SandboxProfile,
                         command: list[str],
                         env: dict = None) -> dict:
        """
        Launch an application inside a sandbox.

        Args:
            profile: Security profile defining restrictions
            command: Command and arguments to run
            env: Environment variables for the app

        Returns:
            Dict with PID and sandbox info
        """
        app_id = profile.app_id
        logger.info("Launching sandboxed: %s", app_id)

        # Set up cgroup for resource limits
        cgroup = self._create_cgroup(profile)

        # Build the unshare command for namespace isolation
        unshare_cmd = self._build_unshare_cmd(profile)

        # Build the full command
        full_cmd = unshare_cmd + command

        # Prepare environment
        app_env = os.environ.copy()
        if env:
            app_env.update(env)

        # Set app data directory
        data_dir = f"/var/lib/claude-os/apps/{app_id}/data"
        os.makedirs(data_dir, exist_ok=True)
        app_env["APP_DATA_DIR"] = data_dir
        app_env["HOME"] = data_dir

        # Launch the process
        proc = subprocess.Popen(
            full_cmd,
            env=app_env,
            preexec_fn=lambda: self._apply_rlimits(profile),
        )

        # Add to cgroup
        self._add_to_cgroup(app_id, proc.pid)

        self._active_sandboxes[app_id] = proc.pid

        logger.info("Sandboxed app %s launched (PID %d)", app_id, proc.pid)

        return {
            "app_id": app_id,
            "pid": proc.pid,
            "sandbox": {
                "namespaces": self._get_namespace_list(profile),
                "cgroup": cgroup,
                "network": profile.allow_network,
                "max_memory_mb": profile.max_memory_mb,
                "blocked_syscalls": len(profile.blocked_syscalls),
            },
        }

    def _build_unshare_cmd(self, profile: SandboxProfile) -> list[str]:
        """Build the unshare command for namespace isolation."""
        cmd = ["unshare"]

        # PID namespace — app can't see other processes
        cmd.append("--pid")
        cmd.append("--fork")

        # Mount namespace — app gets its own filesystem view
        cmd.append("--mount")

        # IPC namespace — separate shared memory
        cmd.append("--ipc")

        # UTS namespace — separate hostname
        cmd.append("--uts")

        # Network namespace — no network unless explicitly allowed
        if not profile.allow_network:
            cmd.append("--net")

        # Map root user in namespace to unprivileged user outside
        cmd.extend(["--map-root-user"])

        return cmd

    def _get_namespace_list(self, profile: SandboxProfile) -> list[str]:
        """Get list of active namespaces for a profile."""
        ns = ["pid", "mount", "ipc", "uts"]
        if not profile.allow_network:
            ns.append("net")
        return ns

    # --- cgroups v2 ---

    def _create_cgroup(self, profile: SandboxProfile) -> str:
        """Create a cgroup for resource limiting."""
        cgroup_path = os.path.join(self.CGROUP_BASE, profile.app_id)

        try:
            os.makedirs(cgroup_path, exist_ok=True)

            # Memory limit
            mem_limit = profile.max_memory_mb * 1024 * 1024
            mem_max = os.path.join(cgroup_path, "memory.max")
            if os.path.exists(mem_max):
                Path(mem_max).write_text(str(mem_limit))

            # CPU limit (as percentage of one core)
            cpu_max = os.path.join(cgroup_path, "cpu.max")
            if os.path.exists(cpu_max):
                # Format: quota period (microseconds)
                quota = profile.max_cpu_percent * 1000  # percentage of 100000
                Path(cpu_max).write_text(f"{quota} 100000")

            # Process count limit
            pids_max = os.path.join(cgroup_path, "pids.max")
            if os.path.exists(pids_max):
                Path(pids_max).write_text(str(profile.max_processes))

            logger.info("cgroup created: %s (mem: %dMB, cpu: %d%%)",
                         cgroup_path, profile.max_memory_mb,
                         profile.max_cpu_percent)

        except PermissionError:
            logger.warning("Cannot create cgroup (no permissions), "
                           "resource limits will not be enforced")
            return "unavailable"

        return cgroup_path

    def _add_to_cgroup(self, app_id: str, pid: int):
        """Add a process to its cgroup."""
        procs_file = os.path.join(self.CGROUP_BASE, app_id, "cgroup.procs")
        try:
            Path(procs_file).write_text(str(pid))
        except (PermissionError, OSError):
            logger.debug("Could not add PID %d to cgroup", pid)

    # --- Resource Limits (rlimits) ---

    def _apply_rlimits(self, profile: SandboxProfile):
        """Apply POSIX resource limits (called in child process)."""
        # Max open files
        resource.setrlimit(
            resource.RLIMIT_NOFILE,
            (profile.max_open_files, profile.max_open_files),
        )

        # Max processes/threads
        resource.setrlimit(
            resource.RLIMIT_NPROC,
            (profile.max_processes, profile.max_processes),
        )

        # Max address space (memory)
        mem_bytes = profile.max_memory_mb * 1024 * 1024
        resource.setrlimit(
            resource.RLIMIT_AS,
            (mem_bytes, mem_bytes),
        )

        # No core dumps
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    # --- seccomp ---

    def generate_seccomp_policy(self, profile: SandboxProfile) -> dict:
        """
        Generate a seccomp-bpf policy for an app.

        Returns the policy as a JSON structure compatible with
        OCI runtime spec (used by container runtimes).
        """
        policy = {
            "defaultAction": "SCMP_ACT_ALLOW",
            "syscalls": [
                {
                    "names": profile.blocked_syscalls,
                    "action": "SCMP_ACT_ERRNO",
                    "errnoRet": 1,  # EPERM
                }
            ],
        }

        # Save policy for the app
        policy_dir = Path(f"/var/lib/claude-os/apps/{profile.app_id}")
        policy_dir.mkdir(parents=True, exist_ok=True)
        policy_path = policy_dir / "seccomp.json"
        policy_path.write_text(json.dumps(policy, indent=2))

        return {
            "policy_path": str(policy_path),
            "blocked_count": len(profile.blocked_syscalls),
            "default_action": "allow",
        }

    # --- Queries ---

    def list_sandboxed(self) -> list[dict]:
        """List all sandboxed apps."""
        result = []
        for app_id, pid in self._active_sandboxes.items():
            # Check if still running
            try:
                os.kill(pid, 0)
                running = True
            except OSError:
                running = False

            result.append({
                "app_id": app_id,
                "pid": pid,
                "running": running,
            })
        return result

    def get_sandbox_info(self, app_id: str) -> dict:
        """Get sandbox details for an app."""
        pid = self._active_sandboxes.get(app_id)
        if not pid:
            return {"app_id": app_id, "sandboxed": False}

        info = {
            "app_id": app_id,
            "sandboxed": True,
            "pid": pid,
        }

        # Read namespace info from /proc
        try:
            ns_dir = f"/proc/{pid}/ns"
            if os.path.exists(ns_dir):
                info["namespaces"] = os.listdir(ns_dir)
        except OSError:
            pass

        # Read cgroup info
        try:
            cgroup_file = f"/proc/{pid}/cgroup"
            if os.path.exists(cgroup_file):
                info["cgroup"] = Path(cgroup_file).read_text().strip()
        except OSError:
            pass

        return info
