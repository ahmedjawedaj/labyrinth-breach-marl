from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from evaluate_policy import build_evaluation_command, prepare_inference_workspace  # noqa: E402


class EvaluationIsolationTests(unittest.TestCase):
    def test_inference_uses_checkpoint_snapshot_without_mutating_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_results = root / "results"
            source_run_id = "source_run"
            behaviors = ["Sentinel", "Runner"]
            source_hashes = {}
            for behavior in behaviors:
                checkpoint = source_results / source_run_id / behavior / "checkpoint.pt"
                checkpoint.parent.mkdir(parents=True, exist_ok=True)
                checkpoint.write_bytes(f"{behavior}-checkpoint".encode("ascii"))
                source_hashes[behavior] = hashlib.sha256(checkpoint.read_bytes()).hexdigest()

            workspace = prepare_inference_workspace(
                root,
                source_results,
                source_run_id,
                behaviors,
                "eval_run",
            )
            self.addCleanup(shutil.rmtree, workspace, ignore_errors=True)

            args = SimpleNamespace(
                manifest_data={"trainer_config": "trainer.yaml", "seed": 42},
                trainer_config=None,
                seed=None,
                torch_device=None,
                allow_cpu=True,
                source_run_id=source_run_id,
                source_results_dir=str(source_results),
                deterministic=True,
                env=None,
                no_graphics=True,
                timeout_wait=120,
                base_port=5064,
                extra_mlagents_args=[],
            )
            command = build_evaluation_command(args, root, workspace)

            results_index = command.index("--results-dir") + 1
            self.assertEqual(Path(command[results_index]), workspace)
            for behavior in behaviors:
                source = source_results / source_run_id / behavior / "checkpoint.pt"
                staged = workspace / source_run_id / behavior / "checkpoint.pt"
                self.assertEqual(staged.read_bytes(), source.read_bytes())
                staged.write_bytes(b"inference-side-write")
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), source_hashes[behavior])


if __name__ == "__main__":
    unittest.main()
