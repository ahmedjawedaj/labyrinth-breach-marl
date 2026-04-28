#!/usr/bin/env python3
"""Reusable artifact validation for evaluation reliability."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ArtifactRequirement:
    path: Path
    label: str
    must_be_non_empty: bool = True


@dataclass(frozen=True)
class ArtifactProblem:
    path: Path
    label: str
    reason: str


def validate_artifacts(requirements: Iterable[ArtifactRequirement]) -> list[ArtifactProblem]:
    problems: list[ArtifactProblem] = []
    for requirement in requirements:
        path = requirement.path
        if not path.exists():
            problems.append(ArtifactProblem(path=path, label=requirement.label, reason="missing"))
            continue
        if path.is_dir():
            problems.append(ArtifactProblem(path=path, label=requirement.label, reason="is_directory"))
            continue
        if requirement.must_be_non_empty and path.stat().st_size <= 0:
            problems.append(ArtifactProblem(path=path, label=requirement.label, reason="empty_file"))
    return problems


def format_problem_report(problems: Iterable[ArtifactProblem], *, heading: str) -> str:
    problem_list = list(problems)
    if not problem_list:
        return f"{heading}: none"
    lines = [f"{heading} ({len(problem_list)}):"]
    for problem in problem_list:
        lines.append(f"- [{problem.reason}] {problem.label}: {problem.path}")
    return "\n".join(lines)


def required_raw_log_requirements(logs_dir: Path) -> list[ArtifactRequirement]:
    return [
        ArtifactRequirement(path=logs_dir / "episode_log.csv", label="episode_log.csv"),
        ArtifactRequirement(path=logs_dir / "agent_step_log.csv", label="agent_step_log.csv"),
        ArtifactRequirement(path=logs_dir / "reward_audit.csv", label="reward_audit.csv"),
        ArtifactRequirement(path=logs_dir / "replay_events.csv", label="replay_events.csv"),
    ]

