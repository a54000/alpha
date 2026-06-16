from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def read_script(name: str) -> str:
    return (REPO_ROOT / "scripts" / name).read_text(encoding="utf-8")


def test_daily_pipeline_wrapper_calls_full_orchestrator_and_logs():
    content = read_script("run_full_daily_pipeline.ps1")

    assert "scripts\\run_full_daily_pipeline.py" in content
    assert "logs\\daily_pipeline" in content
    assert "--business-date" in content
    assert "--portfolio-id" in content
    assert "--rebalance-paper" in content
    assert "Tee-Object" in content


def test_daily_pipeline_task_installer_registers_scheduled_task():
    content = read_script("install_daily_pipeline_task.ps1")

    assert "New-ScheduledTaskAction" in content
    assert "New-ScheduledTaskTrigger -Daily" in content
    assert "Register-ScheduledTask" in content
    assert "run_full_daily_pipeline.ps1" in content
    assert "18:30" in content


def test_daily_pipeline_task_uninstaller_unregisters_task():
    content = read_script("uninstall_daily_pipeline_task.ps1")

    assert "Get-ScheduledTask" in content
    assert "Unregister-ScheduledTask" in content
    assert "NSE Research Daily Paper Pipeline" in content
