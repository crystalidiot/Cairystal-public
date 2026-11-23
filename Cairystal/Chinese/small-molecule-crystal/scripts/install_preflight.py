#!/usr/bin/env python3
"""Read-only Windows installation preflight for the crystallography bundle."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
from pathlib import Path


REQUIRED = ("olex2.exe", "shelxt.exe", "shelxl.exe", "platon.exe")
MIN_FREE_BYTES = 2 * 1024**3

def default_target() -> Path:
    drive = Path('D:/') if Path('D:/').is_dir() else Path(os.environ.get('SystemDrive', 'C:') + '/')
    return drive / 'software' / 'olex2-win64'


def nearest_existing_parent(path: Path) -> Path | None:
    candidate = path
    while True:
        if candidate.exists():
            return candidate
        if candidate.parent == candidate:
            return None
        candidate = candidate.parent


def classify_target(target: Path) -> tuple[str, list[str]]:
    if not target.exists():
        return "missing", []
    if not target.is_dir():
        return "not_a_directory", []
    entries = [item.name for item in target.iterdir()]
    if not entries:
        return "empty", []
    found = [name for name in REQUIRED if (target / name).is_file()]
    if found:
        return "recognised_installation", found
    return "nonempty_unrecognised", []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path, default=default_target())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    target = args.target.expanduser().resolve()
    existing_parent = nearest_existing_parent(target)
    target_state, found = classify_target(target)
    is_windows = os.name == "nt"
    is_64bit = platform.architecture()[0] == "64bit"

    free_bytes = None
    if existing_parent is not None:
        free_bytes = shutil.disk_usage(existing_parent).free

    missing = [name for name in REQUIRED if name not in found]
    blockers: list[str] = []
    if not is_windows:
        blockers.append("This installation plan is for Windows only.")
    if not is_64bit:
        blockers.append("The operating system or Python process is not 64-bit.")
    if existing_parent is None:
        blockers.append("No existing parent drive or directory was found for the target.")
    if target_state == "not_a_directory":
        blockers.append("The target path exists but is not a directory.")
    if target_state == "nonempty_unrecognised":
        blockers.append("The target contains unrelated or unrecognised files and must not be overwritten.")
    if free_bytes is not None and free_bytes < MIN_FREE_BYTES:
        blockers.append("Less than 2 GiB of free space is available on the destination volume.")

    from native_resources import decision
    report = {
        "native_resources": decision(),
        "status": "ready" if not blockers else "blocked",
        "target": str(target),
        "target_state": target_state,
        "windows": is_windows,
        "architecture": platform.architecture()[0],
        "existing_parent": str(existing_parent) if existing_parent else None,
        "free_bytes": free_bytes,
        "recommended_minimum_free_bytes": MIN_FREE_BYTES,
        "found_required": found,
        "missing_required": missing,
        "blockers": blockers,
        "planned_changes": {
            "download": "requires explicit user approval",
            "write_target": str(target),
            "modify_global_path": False,
            "create_shortcuts": False,
            "overwrite_existing_files": False,
        },
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        state = "可以继续" if not blockers else "已停止"
        print(f"状态：{state}")
        print(f"计划安装位置：{target}")
        print(f"本机建议 SHELXL 线程数：{report['native_resources']['effective']['threads']}（不预分配内存）")
        print(f"可用空间：{free_bytes if free_bytes is not None else '未知'} 字节")
        if target_state == "recognised_installation":
            print("已检测到现有软件：" + ", ".join(found))
        for blocker in blockers:
            print("原因：" + blocker)
    return 0 if not blockers else 1


if __name__ == "__main__":
    sys.exit(main())
