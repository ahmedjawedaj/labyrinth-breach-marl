#!/usr/bin/env python3
"""Strict pre-training implementation audit for Labyrinth Breach."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path


def check(condition: bool, name: str, evidence: str) -> dict:
    return {"check": name, "status": "PASS" if condition else "FAIL", "evidence": evidence}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def has_all(text: str, needles: list[str]) -> bool:
    return all(needle in text for needle in needles)


def cli_check(command: list[str], cwd: Path) -> tuple[bool, str]:
    try:
        completed = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=15)
    except Exception as exc:
        return False, f"{' '.join(command)} failed: {exc}"
    return completed.returncode == 0, (completed.stdout or "").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--output", default="results/official_summary/pretraining_implementation_audit.json")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    unity_root = root / "unity"
    scenes_root = unity_root / "Assets" / "Scenes"
    scripts_root = unity_root / "Assets" / "Scripts"
    summary_root = root / "results" / "official_summary"
    summary_root.mkdir(parents=True, exist_ok=True)

    checks: list[dict] = []

    required_scenes = [
        "01_Baseline_OpenArena_3v2.unity",
        "02_StaticMaze_3v2.unity",
        "03_DynamicMaze_3v2.unity",
        "04_Eval_UnseenMaze_3v2.unity",
    ]
    scenes_exist = all((scenes_root / name).exists() for name in required_scenes)
    checks.append(check(scenes_exist, "Required scenes exist", ", ".join(required_scenes)))

    sentinel_prefab = read(unity_root / "Assets" / "Prefabs" / "Sentinel.prefab")
    runner_prefab = read(unity_root / "Assets" / "Prefabs" / "Runner.prefab")
    base_agent_text = read(scripts_root / "Agents" / "BaseAgent.cs")
    checks.append(check(has_all(sentinel_prefab, ["m_BehaviorName: Sentinel", "TeamId: 0"]), "Sentinel behavior/team", "Sentinel.prefab"))
    checks.append(check(has_all(runner_prefab, ["m_BehaviorName: Runner", "TeamId: 1"]), "Runner behavior/team", "Runner.prefab"))
    runtime_training_switch = has_all(
        base_agent_text,
        ["Academy.Instance.IsCommunicatorOn", "BehaviorType.Default", "BehaviorType.InferenceOnly"],
    )
    checks.append(check(runtime_training_switch, "Runtime training mode switch", "BaseAgent selects Default when the Python communicator is active"))
    checks.append(check("DecisionPeriod: 2" in sentinel_prefab and "DecisionPeriod: 2" in runner_prefab, "DecisionRequester period", "DecisionPeriod=2"))
    inference_models_assigned = all(
        "m_Model: {fileID: 0}" not in prefab and "m_BehaviorType: 2" in prefab
        for prefab in (sentinel_prefab, runner_prefab)
    )
    checks.append(check(inference_models_assigned, "Standalone inference models assigned", "Prefabs retain ONNX models while communicator mode switches to training"))

    controller_text = read(scripts_root / "Environment" / "PursuitEvasionEnvController.cs")
    reward_text = read(scripts_root / "Rewards" / "RewardEngine.cs")
    trap_text = read(scripts_root / "Rewards" / "TrapEventDetector.cs")
    resolver_text = read(scripts_root / "Logging" / "RunLogPathResolver.cs")
    episode_logger = read(scripts_root / "Logging" / "EpisodeLogger.cs")
    step_logger = read(scripts_root / "Logging" / "StepLogger.cs")
    replay_logger = read(scripts_root / "Logging" / "ReplayEventExporter.cs")
    memory_text = read(scripts_root / "Sensors" / "LastKnownPositionMemory.cs")
    maze_generator_text = read(scripts_root / "Environment" / "MazeGenerator.cs")
    summarize_kpi = read(root / "scripts" / "summarize_eval_kpis.py")
    artifact_validation = read(root / "scripts" / "artifact_validation.py")
    training_wrapper = read(root / "scripts" / "train_with_metadata.py")
    curriculum_wrapper = read(root / "scripts" / "run_multiseed_curriculum.py")
    evaluation_wrapper = read(root / "scripts" / "evaluate_policy.py")

    checks.append(check("ResetEpisode" in controller_text or "BeginEpisode" in controller_text, "Environment reset flow present", "PursuitEvasionEnvController.cs"))
    checks.append(check("capture" in controller_text.lower(), "Capture logic present", "PursuitEvasionEnvController.cs"))
    checks.append(check("exit" in controller_text.lower(), "Exit logic present", "PursuitEvasionEnvController.cs"))
    checks.append(check("DynamicWallController" in controller_text or "dynamic wall" in controller_text.lower(), "Dynamic wall logic wired", "PursuitEvasionEnvController.cs"))
    checks.append(check("CollectObservations" in base_agent_text, "Observation pipeline present", "BaseAgent.cs"))
    memory_off_configs = [
        root / "configs" / "env_configs" / "asymmetry_config_memory_off.yaml",
        root / "configs" / "env_configs" / "maze_static_config_memory_off.yaml",
        root / "configs" / "env_configs" / "maze_dynamic_config_memory_off.yaml",
        root / "configs" / "env_configs" / "maze_unseen_eval_config_memory_off.yaml",
    ]
    memory_toggle_ok = "LastKnownPositionMemory" in memory_text and all(path.exists() and "use_memory: false" in read(path) for path in memory_off_configs)
    checks.append(check(memory_toggle_ok, "Memory toggle support present", "LastKnownPositionMemory.cs + *_memory_off.yaml configs"))
    checks.append(check("LoadConfig" in reward_text or "RewardConfig" in reward_text, "Reward config load path present", "RewardEngine.cs"))
    topology_build_log = root / "builds" / "macos" / "unity_build.log"
    topology_log_text = read(topology_build_log) if topology_build_log.exists() else ""
    topology_seeds = [101, 202, 303, 404, 505]
    topology_validation_ok = (
        has_all(
            maze_generator_text,
            ["BuildProceduralLayout", "TryValidateProceduralLayout", "SetTopologySeed", "placementSeed"],
        )
        and has_all(episode_logger, ["maze_layout_id", "maze_topology_seed"])
        and all(f"Validated held-out topology seed={seed}" in topology_log_text for seed in topology_seeds)
    )
    checks.append(
        check(
            topology_validation_ok,
            "Distinct held-out topology validation",
            "MazeGenerator invariants + episode provenance + Unity build signatures for seeds 101/202/303/404/505",
        )
    )
    checks.append(check("TacticalEventTracker" in trap_text and "TryFindExitDenial" in trap_text, "Trap-aware metrics wired", "TrapEventDetector.cs"))
    checks.append(
        check(
            all("RunLogPathResolver" in text for text in [episode_logger, step_logger, replay_logger]) and "ResolveLogDirectory" in resolver_text,
            "Log routing wired",
            "RunLogPathResolver + log exporters",
        )
    )
    checks.append(check("config_snapshots" in read(root / "scripts" / "save_run_metadata.py"), "Metadata snapshot logic present", "save_run_metadata.py"))
    checks.append(check("validate_artifacts" in artifact_validation, "Artifact validation logic present", "artifact_validation.py"))
    checks.append(check("eval_kpi_summary.csv" in summarize_kpi and "eval_kpi_summary.json" in summarize_kpi, "KPI scripts outputs present", "summarize_eval_kpis.py"))
    clean_retry_ok = has_all(
        training_wrapper,
        ["clean_forced_run_directory", "shutil.rmtree(run_dir)", 'status="running"'],
    )
    checks.append(
        check(
            clean_retry_ok,
            "Forced retry starts with clean artifacts",
            "train_with_metadata removes the target run directory before recreating metadata/log routing",
        )
    )
    clean_eval_retry_ok = has_all(
        evaluation_wrapper,
        ["prepare_evaluation_output", "shutil.rmtree(run_dir)", "--force-output"],
    )
    checks.append(
        check(
            clean_eval_retry_ok,
            "Evaluation retry starts with clean artifacts",
            "evaluate_policy refuses existing outputs unless explicit force cleanup is requested",
        )
    )
    budget_ok, budget_output = cli_check([sys.executable, "scripts/validate_training_budgets.py"], root)
    checks.append(
        check(
            budget_ok,
            "Role training budgets are synchronized",
            budget_output[:300] if budget_output else "training budget audit passed",
        )
    )
    checks.append(
        check(
            has_all(curriculum_wrapper, ["config_snapshots_match", "sha256_file(source)", "sha256_file(snapshot)"]),
            "Completed-run resume verifies config hashes",
            "run_multiseed_curriculum compares current sources and saved snapshots before reuse",
        )
    )

    # Runtime tool availability checks support the repository's documented macOS setup.
    mlagents_candidates = [
        Path(candidate) for candidate in [
            shutil.which("mlagents-learn"),
            "/opt/anaconda3/envs/labyrinth-breach/bin/mlagents-learn",
            str(Path.home() / "anaconda3/envs/labyrinth-breach/bin/mlagents-learn"),
            "/home/code/anaconda3/envs/labyrinth-breach/bin/mlagents-learn",
        ] if candidate
    ]
    mlagents_cli = next((candidate for candidate in mlagents_candidates if candidate.exists()), None)
    mlagents_ok, mlagents_out = cli_check([str(mlagents_cli), "--help"], root) if mlagents_cli else (False, "not found")
    checks.append(check(mlagents_ok, "ML-Agents CLI available", mlagents_out[:200] if mlagents_out else "ok"))
    unity_candidates = [
        Path(candidate) for candidate in [
            shutil.which("Unity"),
            shutil.which("unity-editor"),
            "/Applications/Unity/Hub/Editor/6000.0.40f1/Unity.app/Contents/MacOS/Unity",
        ] if candidate
    ]
    unity_candidates.extend(sorted(Path("/Applications/Unity/Hub/Editor").glob("*/Unity.app/Contents/MacOS/Unity")))
    unity_cli = next((candidate for candidate in unity_candidates if candidate.exists()), None)
    checks.append(check(unity_cli is not None, "Unity CLI available", str(unity_cli) if unity_cli else "not found"))

    passed = sum(1 for item in checks if item["status"] == "PASS")
    failed = len(checks) - passed
    payload = {
        "schema_version": 1,
        "passed": passed,
        "failed": failed,
        "checks": checks,
    }
    output_path = root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    csv_path = summary_root / "pretraining_implementation_audit.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["check", "status", "evidence"])
        writer.writeheader()
        for item in checks:
            writer.writerow(item)

    print(f"Wrote audit: {output_path}")
    print(f"Wrote audit table: {csv_path}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
