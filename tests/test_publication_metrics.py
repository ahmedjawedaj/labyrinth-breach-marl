from __future__ import annotations

import csv
import copy
import json
import math
import random
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from analyze_experiment_power import minimum_detectable_effect  # noqa: E402
from analyze_publication_statistics import (  # noqa: E402
    bootstrap_policy_generalization_gap,
    hierarchical_bootstrap,
    seed_layout_variance_components,
    wilson,
)
from run_multiseed_curriculum import (  # noqa: E402
    build_parser as build_curriculum_parser,
    parse_matrix_manifest,
    select_matrix_seeds,
)
from run_publication_eval_matrix import select_policy_seeds  # noqa: E402
from train_with_metadata import (  # noqa: E402
    build_parser as build_training_parser,
    build_training_command,
)
from summarize_eval_kpis import mean_team_spread, summarize, summarize_target_reacquisition  # noqa: E402
from summarize_publication_campaign import (  # noqa: E402
    classify_evaluation_status,
    classify_training_status,
    evaluation_artifact_problems,
)
from validate_ablation_controls import allowed_changes, expected_values, flatten  # noqa: E402
from validate_evaluation_controls import controlled_fields  # noqa: E402


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class PublicationMetricTests(unittest.TestCase):
    def test_campaign_evaluation_completion_requires_artifact_integrity(self) -> None:
        status = {"success": True, "completed_episodes": 100, "target_episodes": 100}
        with tempfile.TemporaryDirectory() as temp_dir:
            run_root = Path(temp_dir)
            problems = evaluation_artifact_problems(run_root, 100)
            self.assertTrue(problems)
            self.assertEqual(
                classify_evaluation_status(status, 100, not problems),
                "failed_or_incomplete",
            )

            required = (
                "metadata/run_metadata.json",
                "logs/agent_step_log.csv",
                "logs/reward_audit.csv",
                "logs/replay_events.csv",
                "kpi/eval_kpi_summary.json",
                "kpi/eval_kpi_summary.csv",
            )
            for relative_path in required:
                path = run_root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("artifact\n", encoding="utf-8")
            episode_path = run_root / "logs/episode_log.csv"
            episode_path.write_text("header\n" + "row\n" * 100, encoding="utf-8")
            metadata_path = run_root / "metadata/evaluation_metadata.json"
            metadata_path.write_text(
                json.dumps(
                    {
                        "source_training_artifacts_immutable": True,
                        "inference_workspace_ephemeral": True,
                        "checkpoints": [
                            {"exists": True, "sha256": "sentinel"},
                            {"exists": True, "sha256": "runner"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            problems = evaluation_artifact_problems(run_root, 100)
            self.assertEqual(problems, [])
            self.assertEqual(classify_evaluation_status(status, 100, True), "completed")

    def test_campaign_status_requires_success_and_episode_target(self) -> None:
        self.assertEqual(
            classify_training_status({"status": "completed", "success": True, "exit_code": 0}),
            "completed",
        )
        self.assertEqual(
            classify_training_status({"status": "running", "success": False, "exit_code": None}),
            "running",
        )
        self.assertEqual(
            classify_training_status({"status": "completed", "success": False, "exit_code": 1}),
            "failed_or_incomplete",
        )
        self.assertEqual(
            classify_evaluation_status(
                {"success": True, "completed_episodes": 99, "target_episodes": 100},
                100,
            ),
            "failed_or_incomplete",
        )
        self.assertEqual(
            classify_evaluation_status(
                {"success": True, "completed_episodes": 100, "target_episodes": 100},
                100,
            ),
            "completed",
        )

    def test_isolated_training_worker_forwards_unique_base_port(self) -> None:
        launcher_args = build_curriculum_parser().parse_args(
            ["--base-port", "5014", "--matrix-status-dir", "worker_status"]
        )
        self.assertEqual(launcher_args.base_port, 5014)
        self.assertEqual(launcher_args.matrix_status_dir, "worker_status")

        training_args = build_training_parser().parse_args(
            [
                "--trainer-config",
                "trainer.yaml",
                "--run-id",
                "port_test",
                "--allow-cpu",
                "--base-port",
                "5014",
            ]
        )
        training_args.manifest_data = {}
        command = build_training_command(training_args, ROOT)
        self.assertEqual(command[-2:], ["--base-port", "5014"])

    def test_evaluation_shard_honors_registered_seed_subset(self) -> None:
        matrix = {"seeds": [42, 101, 202, 606, 707], "splits": []}
        self.assertEqual(select_policy_seeds(matrix, [202])["seeds"], [202])
        with self.assertRaises(ValueError):
            select_policy_seeds(matrix, [999])

    def test_curriculum_launcher_honors_registered_seed_subset(self) -> None:
        matrix = parse_matrix_manifest(
            ROOT,
            "configs/experiment_manifests/official_curriculum_matrix.yaml",
        )
        self.assertEqual(matrix["seeds"], [42, 101, 202, 606, 707])
        self.assertEqual(select_matrix_seeds(matrix, [42])["seeds"], [42])
        with self.assertRaises(ValueError):
            select_matrix_seeds(matrix, [999])

    def test_path_survival_and_route_change_do_not_cross_episode_resets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            episode_path = root / "episode_log.csv"
            step_path = root / "agent_step_log.csv"
            reward_path = root / "reward_audit.csv"
            replay_path = root / "replay_events.csv"

            write_csv(
                episode_path,
                ["episode_id", "outcome", "duration_seconds", "capture_count", "exit_count"],
                [
                    {"episode_id": 1, "outcome": "RunnerWinExitReached", "duration_seconds": 2, "capture_count": 0, "exit_count": 1},
                    {"episode_id": 2, "outcome": "RunnerWinTimeout", "duration_seconds": 1, "capture_count": 0, "exit_count": 0},
                ],
            )
            write_csv(
                step_path,
                [
                    "episode_id", "step_id", "time_seconds", "agent_id", "team", "pos_x", "pos_z",
                    "vel_x", "vel_z", "alive",
                ],
                [
                    {"episode_id": 1, "step_id": 0, "time_seconds": 0, "agent_id": "Runner_1", "team": "Runner", "pos_x": 0, "pos_z": 0, "vel_x": 1, "vel_z": 0, "alive": "true"},
                    {"episode_id": 1, "step_id": 1, "time_seconds": 1, "agent_id": "Runner_1", "team": "Runner", "pos_x": 1, "pos_z": 0, "vel_x": 1, "vel_z": 0, "alive": "true"},
                    {"episode_id": 1, "step_id": 2, "time_seconds": 2, "agent_id": "Runner_1", "team": "Runner", "pos_x": 1, "pos_z": 1, "vel_x": 0, "vel_z": 1, "alive": "true"},
                    {"episode_id": 2, "step_id": 0, "time_seconds": 0, "agent_id": "Runner_1", "team": "Runner", "pos_x": 100, "pos_z": 100, "vel_x": 1, "vel_z": 0, "alive": "true"},
                    {"episode_id": 2, "step_id": 1, "time_seconds": 1, "agent_id": "Runner_1", "team": "Runner", "pos_x": 101, "pos_z": 100, "vel_x": 1, "vel_z": 0, "alive": "true"},
                ],
            )
            write_csv(reward_path, ["episode_id", "event_name", "total"], [])
            write_csv(
                replay_path,
                ["episode_id", "time_seconds", "event_type"],
                [{"episode_id": 1, "time_seconds": 1, "event_type": "wall_shift"}],
            )

            result = summarize(
                SimpleNamespace(
                    episode_log=episode_path,
                    step_log=step_path,
                    reward_audit_log=reward_path,
                    replay_log=replay_path,
                    run_id="metric_test",
                    seed=42,
                    stall_speed_threshold=0.1,
                )
            )

            self.assertAlmostEqual(result["path_efficiency"]["runner_path_meters_per_episode"], 1.5)
            self.assertAlmostEqual(
                result["path_efficiency"]["shortest_path_vs_actual_ratio_proxy"],
                (math.sqrt(2.0) + 1.0) / 3.0,
            )
            self.assertAlmostEqual(result["runner_survival_time_seconds_mean"], 1.5)
            self.assertAlmostEqual(result["dynamic_route_change_proxy"]["value"], 90.0)
            self.assertEqual(result["dynamic_route_change_proxy"]["runner_shift_observations"], 1)

    def test_team_spread_is_episode_balanced(self) -> None:
        rows = [
            {"episode_id": 1, "step_id": 1, "agent_id": "Sentinel_1", "team": "Sentinel", "pos_x": 0, "pos_z": 0, "alive": "true"},
            {"episode_id": 1, "step_id": 1, "agent_id": "Sentinel_2", "team": "Sentinel", "pos_x": 2, "pos_z": 0, "alive": "true"},
            {"episode_id": 1, "step_id": 2, "agent_id": "Sentinel_1", "team": "Sentinel", "pos_x": 0, "pos_z": 0, "alive": "true"},
            {"episode_id": 1, "step_id": 2, "agent_id": "Sentinel_2", "team": "Sentinel", "pos_x": 2, "pos_z": 0, "alive": "true"},
            {"episode_id": 2, "step_id": 1, "agent_id": "Sentinel_1", "team": "Sentinel", "pos_x": 0, "pos_z": 0, "alive": "true"},
            {"episode_id": 2, "step_id": 1, "agent_id": "Sentinel_2", "team": "Sentinel", "pos_x": 10, "pos_z": 0, "alive": "true"},
        ]
        self.assertAlmostEqual(mean_team_spread(rows, "Sentinel"), 6.0)

    def test_reacquisition_excludes_initial_acquisition_and_reports_censoring(self) -> None:
        rows = [
            {"episode_id": 1, "step_id": 0, "time_seconds": 0, "agent_id": "Sentinel_1", "team": "Sentinel", "alive": "true", "visible_target_id": "Runner_1"},
            {"episode_id": 1, "step_id": 1, "time_seconds": 1, "agent_id": "Sentinel_1", "team": "Sentinel", "alive": "true", "visible_target_id": ""},
            {"episode_id": 1, "step_id": 2, "time_seconds": 2, "agent_id": "Sentinel_1", "team": "Sentinel", "alive": "true", "visible_target_id": ""},
            {"episode_id": 1, "step_id": 3, "time_seconds": 3, "agent_id": "Sentinel_1", "team": "Sentinel", "alive": "true", "visible_target_id": "Runner_2"},
            {"episode_id": 1, "step_id": 4, "time_seconds": 4, "agent_id": "Sentinel_1", "team": "Sentinel", "alive": "true", "visible_target_id": ""},
            {"episode_id": 2, "step_id": 0, "time_seconds": 0, "agent_id": "Sentinel_1", "team": "Sentinel", "alive": "true", "visible_target_id": ""},
            {"episode_id": 2, "step_id": 1, "time_seconds": 1, "agent_id": "Sentinel_1", "team": "Sentinel", "alive": "true", "visible_target_id": "Runner_1"},
        ]
        result = summarize_target_reacquisition(rows)
        self.assertAlmostEqual(result["mean_seconds"], 2.0)
        self.assertEqual(result["completed_occlusion_gaps"], 1)
        self.assertEqual(result["right_censored_occlusion_gaps"], 1)

    def test_registered_seed_count_has_low_power_for_small_effects(self) -> None:
        self.assertAlmostEqual(minimum_detectable_effect(3, 0.05, 0.80), 3.264, places=3)
        self.assertAlmostEqual(minimum_detectable_effect(5, 0.05, 0.80), 1.682, places=3)

    def test_wilson_interval_matches_reported_diagnostic(self) -> None:
        low, high = wilson(9, 12)
        self.assertAlmostEqual(low, 0.4677, places=4)
        self.assertAlmostEqual(high, 0.9111, places=4)

    def test_hierarchical_bootstrap_requires_independent_policies(self) -> None:
        one_policy = [
            {"policy_id": "42", "layout_id": "seen", "sentinel_win": value}
            for value in (1.0, 0.0, 1.0)
        ]
        low, high = hierarchical_bootstrap(one_policy, "sentinel_win", 100, random.Random(7))
        self.assertTrue(math.isnan(low))
        self.assertTrue(math.isnan(high))

        two_policies = one_policy + [
            {"policy_id": "101", "layout_id": "seen", "sentinel_win": value}
            for value in (0.0, 0.0, 1.0)
        ]
        low, high = hierarchical_bootstrap(two_policies, "sentinel_win", 200, random.Random(7))
        self.assertTrue(math.isfinite(low))
        self.assertTrue(math.isfinite(high))

    def test_generalization_gap_and_seed_layout_variance_are_exportable(self) -> None:
        records = []
        values = {
            "42": {"seen": [1.0, 1.0], "u1": [1.0, 0.0], "u2": [0.0, 0.0]},
            "101": {"seen": [1.0, 0.0], "u1": [0.0, 0.0], "u2": [1.0, 0.0]},
        }
        for policy_id, layouts in values.items():
            for layout_id, outcomes in layouts.items():
                records.extend(
                    {
                        "policy_id": policy_id,
                        "layout_id": layout_id,
                        "group": "seen" if layout_id == "seen" else "unseen",
                        "sentinel_win": outcome,
                    }
                    for outcome in outcomes
                )

        policy_42 = [record for record in records if record["policy_id"] == "42"]
        gap, low, high = bootstrap_policy_generalization_gap(
            policy_42, "sentinel_win", 500, random.Random(11)
        )
        self.assertAlmostEqual(gap, 0.75)
        self.assertTrue(math.isfinite(low))
        self.assertTrue(math.isfinite(high))

        variance = seed_layout_variance_components(records, "sentinel_win", "unseen")
        self.assertEqual(variance["policy_seeds"], 2)
        self.assertEqual(variance["layouts"], 2)
        self.assertAlmostEqual(
            variance["policy_variance_fraction"]
            + variance["layout_variance_fraction"]
            + variance["interaction_plus_error_variance_fraction"],
            1.0,
        )

    def test_evaluation_control_audit_rejects_non_topology_leakage(self) -> None:
        base = {
            "config_id": "seen",
            "sentinel": {"speed": 2.2},
            "maze": {"layout_split": "seen"},
            "randomization": {"seed": 42, "maze_seed": 42},
        }
        held_out = copy.deepcopy(base)
        held_out["config_id"] = "unseen_101"
        held_out["maze"] = {"layout_split": "unseen"}
        held_out["randomization"] = {"seed": 101, "maze_seed": 101}
        self.assertEqual(controlled_fields(base), controlled_fields(held_out))

        held_out["sentinel"]["speed"] = 2.3
        self.assertNotEqual(controlled_fields(base), controlled_fields(held_out))

    def test_ablation_control_audit_rejects_unregistered_field_change(self) -> None:
        base = flatten(
            {
                "config_id": "base",
                "action_assist": {"sentinel_pursuit_strength": 0.15, "runner_evade_strength": 0.0},
                "sentinel": {"speed": 2.2},
            }
        )
        variant = dict(base)
        variant["config_id"] = "assist_off"
        variant.update(expected_values("action_assist_off"))
        changed = {key for key in set(base) | set(variant) if base.get(key) != variant.get(key)}
        self.assertFalse(changed - allowed_changes("action_assist_off"))

        variant["sentinel.speed"] = 2.4
        changed = {key for key in set(base) | set(variant) if base.get(key) != variant.get(key)}
        self.assertEqual(changed - allowed_changes("action_assist_off"), {"sentinel.speed"})

    def test_official_evaluation_uses_v5_and_distinct_topology_seeds(self) -> None:
        import yaml

        matrix = yaml.safe_load(
            (ROOT / "configs/experiment_manifests/official_publication_eval_matrix.yaml").read_text()
        )
        training_matrix = yaml.safe_load(
            (ROOT / "configs/experiment_manifests/official_curriculum_matrix.yaml").read_text()
        )
        ablation_suite = yaml.safe_load(
            (ROOT / "configs/experiment_manifests/official_ablation_suite.yaml").read_text()
        )
        self.assertEqual(matrix["seeds"], [42, 101, 202, 606, 707])
        self.assertEqual(training_matrix["seeds"], matrix["seeds"])
        self.assertEqual(ablation_suite["effect_convention"], "canonical_full_minus_condition")
        self.assertTrue(
            all(condition.get("directional_hypotheses") for condition in ablation_suite["conditions"])
        )
        observed_topology_seeds = set()
        for split in matrix["splits"]:
            manifest = yaml.safe_load((ROOT / split["manifest"]).read_text())
            self.assertEqual(manifest["reward_config"], "reward_v5_active_agents.yaml")
            rule = yaml.safe_load((ROOT / "configs/env_configs" / manifest["rule_config"]).read_text())
            maze_seed = int(rule["randomization"]["maze_seed"])
            if split["group"] == "unseen":
                self.assertTrue(rule["maze"]["use_unseen_layout"])
                observed_topology_seeds.add(maze_seed)
        self.assertEqual(observed_topology_seeds, {101, 202, 303, 404, 505})


if __name__ == "__main__":
    unittest.main()
