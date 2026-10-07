"""Record the machine a measurement was taken on.

Every latency figure in chapters 3, 4, 6 and 7 is a comparison run on one
machine. The comparison is what carries, not the absolute number — a reader on
different hardware will get something else. Rather than argue about which
machine to standardise on, every tool that reports a timing writes down the one
it ran on, so a captured result explains itself.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import time


def _sysctl(key: str) -> str | None:
    try:
        out = subprocess.run(["sysctl", "-n", key], capture_output=True,
                             text=True, timeout=5)
        return out.stdout.strip() or None
    except Exception:
        return None


def _cpu_model() -> str:
    if platform.system() == "Darwin":
        return _sysctl("machdep.cpu.brand_string") or platform.processor()
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def _memory_bytes() -> int | None:
    if platform.system() == "Darwin":
        v = _sysctl("hw.memsize")
        return int(v) if v else None
    try:
        for line in open("/proc/meminfo"):
            if line.startswith("MemTotal"):
                return int(line.split()[1]) * 1024
    except OSError:
        return None
    return None


def runtime_product(context: str, name: str, operating_system: str) -> str:
    """The product behind the Docker Engine API, read from what the client
    and the daemon call themselves: the active context (`rancher-desktop`,
    `desktop-linux`, `colima`, `podman-machine-default`, ...), the daemon's
    `Name` and its `OperatingSystem`. Every cost figure in this book was
    measured on Rancher Desktop; a report that says which runtime it ran on
    lets a reader compare like with like."""
    key = f"{context} {name} {operating_system}".lower()
    if "rancher" in key:
        return "Rancher Desktop"
    if "desktop-linux" in key or "docker-desktop" in key or "docker desktop" in key:
        return "Docker Desktop"
    if "podman" in key:
        return "Podman"
    if "colima" in key:
        return "Colima"
    return "Docker Engine"


def _docker() -> dict | None:
    try:
        out = subprocess.run(
            ["docker", "info", "--format",
             "{{.NCPU}}|{{.MemTotal}}|{{.ServerVersion}}|{{.Name}}|{{.OperatingSystem}}"],
            capture_output=True, text=True, timeout=10)
        if out.returncode:
            return None
        ncpu, mem, ver, name, os_name = out.stdout.strip().split("|", 4)
        ctx = subprocess.run(["docker", "context", "show"], capture_output=True,
                             text=True, timeout=10)
        context = ctx.stdout.strip() if ctx.returncode == 0 else ""
        return {"cpus": int(ncpu), "memory_gb": round(int(mem) / 1e9, 1),
                "server_version": ver,
                "runtime": runtime_product(context, name, os_name),
                "runtime_name": name, "runtime_os": os_name, "context": context}
    except Exception:
        return None


def collect() -> dict:
    return {
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "os": f"{platform.system()} {platform.release()}",
        "arch": platform.machine(),
        "cpu": _cpu_model(),
        "cpu_count": os.cpu_count(),
        "memory_gb": round(_memory_bytes() / 1e9, 1) if _memory_bytes() else None,
        "python": platform.python_version(),
        "docker": _docker(),
    }


def as_markdown(info: dict | None = None) -> str:
    i = info or collect()
    d = i.get("docker")
    lines = [
        f"- machine: {i['cpu']}, {i['cpu_count']} cores, {i['memory_gb']} GB",
        f"- os: {i['os']} {i['arch']}, python {i['python']}",
    ]
    if d:
        lines.append(f"- docker: {d['cpus']} cpus, {d['memory_gb']} GB, "
                     f"engine {d['server_version']}")
    lines.append(f"- captured: {i['captured_at']}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(json.dumps(collect(), indent=2))
