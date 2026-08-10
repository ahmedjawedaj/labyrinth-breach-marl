#!/usr/bin/env python3
"""Extract Self-play/ELO series from ML-Agents tfevents files.

Pure standard library plus numpy. Does not require tensorboard, so it runs
anywhere the results tree is readable. Reads the TFRecord container directly and
decodes only the protobuf fields needed for scalar summaries.

Feeds task section 2.5: correlate saved self-play ELO against the archive-based
Bradley-Terry rating from the snapshot tournament.
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path
from typing import Any, Iterator

OFFICIAL_RUN = re.compile(r"^LB_3v2_official_seed(?P<seed>\d+)_stage(?P<stage>\d+)$")


def read_varint(buf: bytes, pos: int) -> tuple[int, int]:
    result = shift = 0
    while pos < len(buf):
        byte = buf[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, pos
        shift += 7
    raise ValueError("truncated varint")


def iter_fields(buf: bytes) -> Iterator[tuple[int, int, Any]]:
    """Yield (field_number, wire_type, payload) for one protobuf message."""
    pos = 0
    while pos < len(buf):
        key, pos = read_varint(buf, pos)
        field, wire = key >> 3, key & 0x07
        if wire == 0:
            value, pos = read_varint(buf, pos)
        elif wire == 1:
            value, pos = buf[pos:pos + 8], pos + 8
        elif wire == 2:
            length, pos = read_varint(buf, pos)
            value, pos = buf[pos:pos + length], pos + length
        elif wire == 5:
            value, pos = buf[pos:pos + 4], pos + 4
        else:
            raise ValueError(f"unsupported wire type {wire}")
        yield field, wire, value


def iter_tfrecords(path: Path) -> Iterator[bytes]:
    with path.open("rb") as handle:
        while True:
            header = handle.read(8)
            if len(header) < 8:
                return
            (length,) = struct.unpack("<Q", header)
            handle.read(4)                      # masked crc of length
            payload = handle.read(length)
            handle.read(4)                      # masked crc of payload
            if len(payload) < length:
                return
            yield payload


def scalars_from_event(record: bytes) -> Iterator[tuple[int, str, float]]:
    step = 0
    summary = None
    for field, _wire, value in iter_fields(record):
        if field == 2:
            step = value
        elif field == 5:
            summary = value
    if summary is None:
        return
    for field, _wire, value in iter_fields(summary):
        if field != 1:                          # Summary.value
            continue
        tag = None
        simple = None
        for sub_field, sub_wire, sub_value in iter_fields(value):
            if sub_field == 1 and sub_wire == 2:
                tag = sub_value.decode("utf-8", "replace")
            elif sub_field == 2 and sub_wire == 5:
                (simple,) = struct.unpack("<f", sub_value)
            elif sub_field == 8 and sub_wire == 2 and simple is None:
                for t_field, t_wire, t_value in iter_fields(sub_value):
                    if t_field == 4 and t_wire == 2 and len(t_value) >= 4:
                        (simple,) = struct.unpack("<f", t_value[:4])
        if tag is not None and simple is not None:
            yield step, tag, float(simple)


def extract(results_dir: Path, pattern: str) -> dict[str, Any]:
    needle = pattern.lower()
    series: dict[str, list[list[float]]] = {}
    tags_seen: dict[str, list[str]] = {}
    missing: list[str] = []

    for run_dir in sorted(results_dir.glob("LB_3v2_official_seed*_stage*")):
        if OFFICIAL_RUN.match(run_dir.name) is None:
            continue
        for behavior in ("Sentinel", "Runner"):
            key = f"{run_dir.name}/{behavior}"
            points: list[list[float]] = []
            tags: set[str] = set()
            for event_file in sorted((run_dir / behavior).glob("events.out.tfevents.*")):
                try:
                    for record in iter_tfrecords(event_file):
                        for step, tag, value in scalars_from_event(record):
                            tags.add(tag)
                            if needle in tag.lower():
                                points.append([step, value])
                except (ValueError, struct.error, OSError) as exc:
                    print(f"  warning: {event_file.name}: {exc}", file=sys.stderr)
            tags_seen[key] = sorted(tags)
            if points:
                points.sort(key=lambda p: p[0])
                series[key] = points
            else:
                missing.append(key)
    return {"series": series, "missing": missing, "tags_seen": tags_seen}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--pattern", default="elo")
    parser.add_argument("--output", default="results/official_summary/tournament/selfplay_elo.json")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    data = extract(root / args.results_dir, args.pattern)

    out = root / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Series found:   {len(data['series'])}")
    print(f"Series missing: {len(data['missing'])}")
    for key in sorted(data["series"]):
        pts = data["series"][key]
        print(f"  {key:<48} n={len(pts):>4}  step {pts[0][0]:>8}-{pts[-1][0]:<8}  "
              f"elo {pts[0][1]:7.1f} -> {pts[-1][1]:7.1f}")
    for key in data["missing"]:
        print(f"  MISSING: {key}   tags={data['tags_seen'].get(key, [])[:6]}")
    print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
