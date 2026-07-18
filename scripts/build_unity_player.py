#!/usr/bin/env python3
"""Build the Labyrinth Breach Unity player used by ML-Agents automation."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


UNITY_CANDIDATES = (
    Path("/Applications/Unity/Hub/Editor/6000.0.40f1/Unity.app/Contents/MacOS/Unity"),
    Path("/Applications/Unity/Hub/Editor/6000.4.1f1/Unity.app/Contents/MacOS/Unity"),
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def discover_unity(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit).expanduser()
        if path.exists():
            return path
        raise FileNotFoundError(f"Requested Unity executable does not exist: {path}")

    for candidate in UNITY_CANDIDATES:
        if candidate.exists():
            return candidate

    matches = sorted(Path("/Applications/Unity/Hub/Editor").glob("*/Unity.app/Contents/MacOS/Unity"))
    if matches:
        return matches[0]

    raise FileNotFoundError("Could not find Unity. Install Unity 6000.0.40f1 or pass --unity.")


def build_command(unity: Path, output: Path, *, server_build: bool, log_file: Path) -> list[str]:
    root = repo_root()
    command = [
        str(unity),
        "-batchmode",
        "-quit",
        "-projectPath",
        str(root / "unity"),
        "-executeMethod",
        "LabyrinthBreachBuild.BuildMacOS",
        "-buildOutput",
        str(output),
        "-logFile",
        str(log_file),
    ]
    if server_build:
        command.append("-serverBuild")
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unity", help="Path to Unity executable.")
    parser.add_argument("--output", default="builds/macos/LabyrinthBreach.app")
    parser.add_argument("--log-file", default="builds/macos/unity_build.log")
    parser.add_argument("--server-build", action="store_true", help="Request a Unity server/headless build when supported.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = repo_root()
    unity = discover_unity(args.unity)
    output = (root / args.output).resolve()
    log_file = (root / args.log_file).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    command = build_command(unity, output, server_build=args.server_build, log_file=log_file)
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "unity": str(unity),
        "output": str(output),
        "log_file": str(log_file),
        "server_build": args.server_build,
        "command": command,
    }
    manifest_path = output.parent / "build_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Unity build command:")
    print(" ".join(command))
    print(f"Build manifest: {manifest_path}")

    if args.dry_run:
        return 0

    rc = subprocess.run(command, cwd=root).returncode
    if rc != 0:
        print(f"Unity build failed with exit code {rc}. See {log_file}")
        return rc
    if not output.exists():
        print(f"Unity build command completed but output is missing: {output}")
        return 2
    print(f"Unity build created: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
