from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Mapping

import pytest

from run_helpers import PULPOS_ROOT, failure_message, run_with_process_group_cleanup


# Examples are built and run in place via gvrun on the gap9 EVK target. The
# surrounding SDK environment (gvrun on PATH, PULPOS_HOME / PULPOS_GAP9_HOME /
# GAP_RISCV_GCC_TOOLCHAIN, model+target dirs) is expected to be sourced before
# pytest is invoked — the child process inherits the current environment.
GVRUN_BASE_ARGS = [
    "--platform=gvsoc",
    "--target",
    "gap.gap9.evk",
    "clean",
    "all",
    "run",
]

DEFAULT_REQUIRED_OUTPUT_MARKERS: list[str] = []

REQUIRED_OUTPUT_MARKERS: dict[str, list[str]] = {
}

KERNEL_EXPECTED_FAILS: dict[str, str] = {
}


def _run_gvrun(example_dir: Path, timeout: int = 60) -> tuple[subprocess.CompletedProcess[str], str]:
    gvrun_command = ["gvrun", *GVRUN_BASE_ARGS]
    result = run_with_process_group_cleanup(
        gvrun_command,
        cwd=example_dir,
        timeout=timeout,
    )
    return result, " ".join(gvrun_command)


def test_hello_example_run() -> None:
    hello_result, hello_cmd = _run_gvrun(PULPOS_ROOT / "examples/hello")
    assert hello_result.returncode == 0, failure_message("Hello example run", hello_cmd, hello_result, PULPOS_ROOT)

    assert "Hello" in hello_result.stdout, (
        "Hello string was not found in hello example output\n"
        f"stdout tail:\n{hello_result.stdout[-4000:]}\n"
        f"stderr tail:\n{hello_result.stderr[-4000:]}\n"
    )


def get_example_params(test_dir: str, expected_fails: Mapping[str, str]) -> list[pytest.ParameterSet]:
    params: list[pytest.ParameterSet] = []

    test_root = PULPOS_ROOT / test_dir
    if not test_root.is_dir():
        return params
    config_files = sorted(test_root.glob("**/config.py"))
    example_dirs = [config_file.parent for config_file in config_files]

    for example_dir in example_dirs:
        for k, v in expected_fails.items():
            if str(example_dir).endswith(k):
                reason = v
                break
        else:
            reason = None
        params.append(pytest.param(example_dir, reason, id=str(example_dir.relative_to(PULPOS_ROOT))))
    return params


@pytest.mark.parametrize(
    "example_dir,fail_reason",
    get_example_params("examples/kernel", KERNEL_EXPECTED_FAILS),
)
def test_kernel_example_runs(example_dir: Path, fail_reason: str | None) -> None:
    relative_dir = example_dir.relative_to(PULPOS_ROOT)
    relative_dir_str = str(relative_dir)
    run_result, run_cmd = _run_gvrun(example_dir)
    if fail_reason:
        assert run_result.returncode == 1 and fail_reason in run_result.stdout, failure_message(
            f"Kernel example run ({relative_dir})",
            run_cmd,
            run_result,
            PULPOS_ROOT,
        )
    else:
        assert run_result.returncode == 0, failure_message(
            f"Kernel example run ({relative_dir})",
            run_cmd,
            run_result,
            PULPOS_ROOT,
        )

        required_markers = REQUIRED_OUTPUT_MARKERS.get(relative_dir_str, DEFAULT_REQUIRED_OUTPUT_MARKERS)
        for marker in required_markers:
            assert marker in run_result.stdout, (
                f"Missing expected marker '{marker}' in output for {relative_dir_str}\n"
                f"stdout tail:\n{run_result.stdout[-4000:]}\n"
                f"stderr tail:\n{run_result.stderr[-4000:]}\n"
            )
