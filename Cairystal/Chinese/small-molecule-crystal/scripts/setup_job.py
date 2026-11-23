#!/usr/bin/env python3
"""Create an isolated, traceable crystal-processing job from .hkl/.ins inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from inspect_case import parse_ins, REQUIRED_INS, reflection_stats, input_format_blockers


DEFAULT_SOFTWARE_DIR = Path(r"D:\software\olex2-win64")
TOOL_NAMES = ("olex2.exe", "shelxt.exe", "shelxl.exe", "platon.exe")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def discover_pairs(directory: Path) -> dict[str, dict[str, Path]]:
    by_stem: dict[str, dict[str, Path]] = {}
    for path in directory.iterdir():
        if path.is_file() and path.suffix.lower() in {".hkl", ".ins"}:
            by_stem.setdefault(path.stem.casefold(), {})[path.suffix.lower()] = path
    return {
        stem: files
        for stem, files in by_stem.items()
        if ".hkl" in files and ".ins" in files
    }


def next_job_dir(output_root: Path, stem: str) -> Path:
    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    base = output_root / f"{stem}_{timestamp}"
    candidate = base
    counter = 2
    while candidate.exists():
        candidate = output_root / f"{base.name}_{counter}"
        counter += 1
    return candidate


def fail(message: str, as_json: bool) -> int:
    payload = {"status": "stopped", "message": message}
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"状态：已停止\n原因：{message}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("data_directory", type=Path)
    parser.add_argument("--stem", help="Select one basename when multiple pairs exist")
    parser.add_argument("--output-root", type=Path, default=Path.cwd() / "crystal_jobs")
    parser.add_argument("--software-dir", type=Path, default=DEFAULT_SOFTWARE_DIR)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    source = args.data_directory.expanduser().resolve()
    output_root = args.output_root.expanduser().resolve()
    software_dir = args.software_dir.expanduser().resolve()

    if not source.is_dir():
        return fail(f"数据目录不存在：{source}", args.json)

    pairs = discover_pairs(source)
    if args.stem:
        selected_key = args.stem.casefold()
        if selected_key not in pairs:
            return fail(f"没有找到同名的 {args.stem}.hkl 和 {args.stem}.ins", args.json)
    elif len(pairs) == 1:
        selected_key = next(iter(pairs))
    elif not pairs:
        return fail("目录中没有找到同名的 .hkl 和 .ins 文件", args.json)
    else:
        names = ", ".join(sorted(files[".ins"].stem for files in pairs.values()))
        return fail(f"找到多个数据组，请使用 --stem 选择其中一个：{names}", args.json)

    files = pairs[selected_key]
    stem = files[".ins"].stem
    directives, _ = parse_ins(files[".ins"])
    missing = sorted(card for card in REQUIRED_INS if not str(directives.get(card, "")).strip())
    if missing:
        return fail("INS 缺少必要指令：" + ", ".join(missing), args.json)
    if any(path.stat().st_size == 0 for path in files.values()):
        return fail("INS 或 HKL 文件为空，尚不能创建可处理任务", args.json)
    blockers = input_format_blockers(directives, reflection_stats(files[".hkl"]))
    if blockers:
        return fail("反射格式需核对，未创建任务：" + " ".join(blockers), args.json)
    output_root.mkdir(parents=True, exist_ok=True)
    job_dir = next_job_dir(output_root, stem)
    input_dir = job_dir / "input"
    solve_dir = job_dir / "solve"
    refine_dir = job_dir / "refine"
    validate_dir = job_dir / "validate"

    for directory in (input_dir, solve_dir, refine_dir, validate_dir):
        directory.mkdir(parents=True, exist_ok=False)

    copied: list[dict[str, object]] = []
    for suffix in (".hkl", ".ins"):
        src = files[suffix]
        dst = input_dir / f"{stem}{suffix}"
        before = sha256(src)
        shutil.copy2(src, dst)
        after = sha256(dst)
        if before != after:
            return fail(f"复制校验失败：{src.name}", args.json)
        copied.append(
            {
                "kind": suffix[1:],
                "source_path": str(src),
                "copied_path": str(dst),
                "size": src.stat().st_size,
                "sha256": before,
            }
        )

    tools = []
    for name in TOOL_NAMES:
        path = software_dir / name
        tools.append(
            {
                "name": name,
                "path": str(path),
                "exists": path.is_file(),
                "sha256": sha256(path) if path.is_file() else None,
            }
        )

    missing_tools = [item["name"] for item in tools if not item["exists"]]
    manifest = {
        "schema_version": 1,
        "status": "initialized" if not missing_tools else "initialized_missing_tools",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "job_directory": str(job_dir),
        "source_directory": str(source),
        "stem": stem,
        "source_files_unchanged": True,
        "inputs": copied,
        "software_directory": str(software_dir),
        "tools": tools,
        "missing_tools": missing_tools,
        "stages": {
            "inspect": "ready",
            "solve": "not_started",
            "refine": "not_started",
            "validate": "not_started",
        },
    }
    manifest_path = job_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    response = {
        "status": "ready" if not missing_tools else "needs_review",
        "job_directory": str(job_dir),
        "manifest": str(manifest_path),
        "stem": stem,
        "source_files_unchanged": True,
        "missing_tools": missing_tools,
    }
    if args.json:
        print(json.dumps(response, ensure_ascii=False, indent=2))
    else:
        state = "可以继续" if not missing_tools else "建议检查"
        print(f"状态：{state}")
        print(f"已创建独立任务目录：{job_dir}")
        print("原始 .hkl 和 .ins 文件未被修改。")
        if missing_tools:
            print("缺少软件：" + ", ".join(missing_tools))
        else:
            print("下一步：可以在 solve 目录中进行结构解析。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
