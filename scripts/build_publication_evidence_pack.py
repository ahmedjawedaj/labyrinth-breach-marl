#!/usr/bin/env python3
"""Build a hashed evidence pack from audited canonical artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STATIC_PATHS = [
    Path("README.md"),
    Path("environment.yml"),
    Path("requirements.txt"),
    Path("configs"),
    Path("paper/labyrinth_breach_journal.tex"),
    Path("output/pdf/labyrinth_breach_journal.pdf"),
    Path("docs/current_empirical_truth.md"),
    Path("docs/evaluation_protocol.md"),
    Path("docs/implementation_change_log.md"),
    Path("docs/independent_review_response_2026-07-16.md"),
    Path("docs/independent_senior_review_2026-07-16.md"),
    Path("docs/literature_review_2020_2026.md"),
    Path("docs/official_5seed_matrix.md"),
    Path("docs/publication_upgrade_status.md"),
    Path("docs/reproducibility_guide.md"),
    Path("docs/topology_validation.md"),
    Path("scripts"),
    Path("results/official_summary"),
]
EXCLUDED_NAMES = {"__pycache__", ".DS_Store", "runtime_overrides"}
EXCLUDED_SUFFIXES = {".pyc"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def official_training_paths() -> list[Path]:
    matrix = load_yaml(ROOT / "configs/experiment_manifests/official_curriculum_matrix.yaml")
    paths = []
    for seed in matrix["seeds"]:
        for stage in matrix["stages"]:
            run_id = matrix["run_id_template"].format(
                experiment_family=matrix["experiment_family"],
                seed=seed,
                stage_id=stage["id"],
                stage_order=stage["order"],
            )
            paths.append(Path("results") / run_id)
    return paths


def include_file(path: Path) -> bool:
    return not any(part in EXCLUDED_NAMES for part in path.parts) and path.suffix not in EXCLUDED_SUFFIXES


def copy_source(source_relative: Path, output: Path, records: list[dict], allow_missing: bool) -> None:
    source = ROOT / source_relative
    if not source.exists():
        if allow_missing:
            records.append({"source": str(source_relative), "status": "missing"})
            return
        raise FileNotFoundError(f"Required evidence path is missing: {source_relative}")

    files = [source] if source.is_file() else [path for path in source.rglob("*") if path.is_file()]
    for path in files:
        relative = path.relative_to(ROOT)
        if not include_file(relative):
            continue
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        records.append(
            {
                "source": str(relative),
                "packed_path": str(relative),
                "bytes": destination.stat().st_size,
                "sha256": sha256(destination),
                "status": "included",
            }
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="output/evidence/labyrinth_breach_publication")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Create a development snapshot while registered extensions are still being added.",
    )
    args = parser.parse_args()

    readiness_path = ROOT / "results/official_summary/publication_readiness.json"
    if not readiness_path.is_file():
        raise FileNotFoundError("Run scripts/audit_publication_readiness.py first.")
    readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
    if readiness.get("status") != "READY_FOR_SUBMISSION_REVIEW" and not args.allow_incomplete:
        pending = ", ".join(readiness.get("pending_evidence_gate_ids") or readiness.get("blocking_gate_ids") or [])
        print(f"Evidence pack requires unresolved evidence gates or --allow-incomplete: {pending}", file=sys.stderr)
        return 2

    output = (ROOT / args.output_dir).resolve()
    output_parent = (ROOT / "output/evidence").resolve()
    if output_parent not in output.parents and output != output_parent:
        raise ValueError(f"Evidence output must stay under {output_parent}")
    if output.exists():
        if not args.force:
            raise FileExistsError(f"Evidence output exists; pass --force to replace it: {output}")
        shutil.rmtree(output)
    output.mkdir(parents=True)

    dynamic_paths = official_training_paths() + [
        Path("results/publication_eval_official"),
        Path("results/ablations"),
    ]
    records: list[dict] = []
    for source_relative in STATIC_PATHS + dynamic_paths:
        copy_source(source_relative, output, records, args.allow_incomplete)

    included = [record for record in records if record["status"] == "included"]
    manifest = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "readiness_status": readiness.get("status"),
        "development_snapshot": bool(readiness.get("pending_evidence_gate_ids")),
        "file_count": len(included),
        "total_bytes": sum(record["bytes"] for record in included),
        "files": records,
    }
    (output / "artifact_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    checksum_lines = [f"{record['sha256']}  {record['packed_path']}" for record in included]
    (output / "SHA256SUMS").write_text("\n".join(sorted(checksum_lines)) + "\n", encoding="utf-8")
    print(f"Evidence pack: {output}")
    print(f"Included files: {len(included)}")
    print(f"Total bytes: {manifest['total_bytes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
