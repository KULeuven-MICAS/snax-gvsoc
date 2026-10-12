from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path


# Root of the pulpos/core checkout (parent of this tests/ dir).
PULPOS_ROOT = Path(__file__).resolve().parents[1]


def run_with_process_group_cleanup(
    command: list[str],
    cwd: Path,
    timeout: int,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )

    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as timeout_exc:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = process.communicate()

        raise subprocess.TimeoutExpired(command, timeout, output=stdout, stderr=stderr) from timeout_exc

    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def failure_message(step: str, command: str, result: subprocess.CompletedProcess[str], cwd: Path) -> str:
    stdout_tail = result.stdout[-4000:]
    stderr_tail = result.stderr[-4000:]
    return (
        f"{step} failed\n"
        f"cwd: {cwd}\n"
        f"command: {command}\n"
        f"return code: {result.returncode}\n"
        f"stdout tail:\n{stdout_tail}\n"
        f"stderr tail:\n{stderr_tail}"
    )
