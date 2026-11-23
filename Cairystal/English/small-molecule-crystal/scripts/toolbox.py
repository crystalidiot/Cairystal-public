"""Portable, lazy CLI router for Cairystal's existing tools (standard library only).

List/describe/plan do not import scientific modules or run external programs.
Run preserves the selected tool's stdout, stderr, exit status and authorization gates.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def load_catalog(root=ROOT):
    root = Path(root)
    data = json.loads((root / "assets" / "toolbox.json").read_text("utf-8"))
    if data.get("schema") != 1:
        raise ValueError("Unsupported toolbox catalog schema")
    release = json.loads((root / "release_info.json").read_text("utf-8"))
    if not isinstance(release.get("release_id"), str) or not release['release_id']:
        raise ValueError("Missing release identity")
    data['release'] = release['release_id']
    if release.get('tools') != len(data['tools']):
        raise ValueError('Release tool count differs from catalog')
    seen = set()
    for item in data["tools"]:
        tool_id, script = item["id"], item["script"]
        if item.get('group') not in data['groups']:
            raise ValueError('Unregistered tool group: ' + tool_id)
        if not re.fullmatch(r"[a-z][a-z0-9-]*", tool_id) or tool_id in seen:
            raise ValueError("Invalid or duplicate tool id: " + tool_id)
        seen.add(tool_id)
        if not re.fullmatch(r"[a-z][a-z0-9_]*\.py", script):
            raise ValueError("Invalid toolbox script: " + script)
        path = root / "scripts" / script
        if path.is_symlink() or path.resolve().parent != (root / "scripts").resolve() or not path.is_file():
            raise ValueError("Missing or redirected toolbox script: " + script)
        if not isinstance(item.get("prefix"), list) or not all(isinstance(x, str) for x in item["prefix"]):
            raise ValueError("Invalid command prefix: " + tool_id)
        for doc in item["references"]:
            ref = (root / doc).resolve()
            if not ref.is_relative_to(root.resolve()) or not ref.is_file():
                raise ValueError("Missing or external reference: " + doc)
    return data


def selected_tool(catalog, tool_id):
    for item in catalog["tools"]:
        if item["id"] == tool_id:
            return item
    raise ValueError("Unknown tool: " + tool_id + ". Use python -B cairystal.py list")


def command_for(item, arguments, root=ROOT):
    return [sys.executable, "-B", str(Path(root) / "scripts" / item["script"]),
            *item["prefix"], *arguments]


def default_language():
    try:
        language = json.loads((ROOT / "language.json").read_text("utf-8"))["default_language"]
        return language if language in ("zh-CN", "en") else "zh-CN"
    except (OSError, ValueError, KeyError):
        return "zh-CN"

def show_guide(catalog, language, topic, json_output):
    data = json.loads((ROOT / 'assets/user_guide.json').read_text('utf-8'))
    result = {'schema': 1, 'release': catalog['release'], 'language': language,
              'executed': False, 'topics': []}
    if topic and topic not in data:
        raise ValueError('Unknown guide topic. Choose: ' + ', '.join(data))
    for key, item in data.items():
        if topic and topic != key:
            continue
        title, prompt, detail = item[language]
        row = {'id':key, 'title':title, 'prompt':prompt}
        if topic:
            row.update(detail=detail, tools=item['tools'], references=item['references'])
        result['topics'].append(row)
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    zh = language == 'zh-CN'
    print('Cairystal · ' + ('可以直接告诉助手' if zh else 'What you can ask your agent'))
    for row in result['topics']:
        print(f"\n{row['title']}  [{row['id']}]\n  {row['prompt']}")
        if topic:
            print('  ' + row['detail'])
            if row['tools']:
                print(('  相关工具  ' if zh else '  Tools  ') + ', '.join(row['tools']))
            for ref in row['references']:
                print('  ' + str(ROOT / ref))
    if not topic:
        print('\n' + ('查看某一项  ' if zh else 'Read one topic  ') + 'python -B cairystal.py guide TOPIC')


def main(argv=None):
    raw = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", choices=("zh-CN", "en"), default=default_language())
    sub = parser.add_subparsers(dest="action")
    guide = sub.add_parser('guide', help='Show example requests for new crystals, alerts, reports or skill maintenance')
    guide.add_argument('topic', nargs='?')
    guide.add_argument('--json', action='store_true')
    version = sub.add_parser('version', help='Show authoritative release identity')
    version.add_argument('--json', action='store_true')
    listing = sub.add_parser("list", help="List tools; no execution")
    listing.add_argument("--group")
    listing.add_argument("--json", action="store_true")
    description = sub.add_parser("describe", help="Inputs, outputs, effects, dependencies and references")
    description.add_argument("tool")
    description.add_argument("--json", action="store_true")
    for name in ("plan", "run"):
        command = sub.add_parser(name, help="Preview argv only" if name == "plan" else "Execute a registered tool")
        command.add_argument("tool")
        command.add_argument("arguments", nargs=argparse.REMAINDER, help="-- followed by the tool's native arguments")
    args = parser.parse_args(raw)
    try:
        catalog = load_catalog()
        lang = args.language
        if args.action in (None, 'guide'):
            show_guide(catalog, lang, getattr(args,'topic',None), getattr(args,'json',False))
            return 0
        if args.action == 'version':
            info = json.loads((ROOT/'release_info.json').read_text('utf-8'))
            print(json.dumps(info, ensure_ascii=False, indent=2) if args.json else info['release_id'])
            return 0
        if args.action == "list":
            groups = catalog["groups"]
            if args.group and args.group not in groups:
                raise ValueError("Unknown group; choose " + ", ".join(groups))
            items = [x for x in catalog["tools"] if not args.group or x["group"] == args.group]
            if args.json:
                print(json.dumps({"schema": 1, "release": catalog['release'], "groups": groups, "tools": items}, ensure_ascii=False, indent=2))
            else:
                print('Cairystal ' + catalog['release'])
                for group, label in groups.items():
                    selected = [x for x in items if x["group"] == group]
                    if selected:
                        print("\n" + group + " / " + label[lang])
                        for item in selected:
                            print("  {:20} {}".format(item["id"], item["title"][lang]))
                print("\npython -B cairystal.py describe TOOL\npython -B cairystal.py run TOOL -- --help")
            return 0
        item = selected_tool(catalog, args.tool)
        if args.action == "describe":
            if args.json:
                print(json.dumps(item, ensure_ascii=False, indent=2))
            else:
                print(item["id"] + " — " + item["title"][lang])
                for field in ("inputs", "outputs", "effects", "requires", "boundary"):
                    print(field + ": " + item[field][lang])
                print("Command: python -B cairystal.py run " + item["id"] + " -- " + item["example"])
                print("References: " + ", ".join(item["references"]))
            return 0
        # argparse strips a separator before a positional REMAINDER; inspect raw argv.
        forwarded = raw[raw.index(args.action) + 2:]
        if not forwarded or forwarded[0] != "--":
            raise ValueError("Use: python -B cairystal.py " + args.action + " TOOL -- <native arguments>")
        command = command_for(item, forwarded[1:])
        if args.action == "plan":
            print(json.dumps({"schema": 1, "release": catalog['release'], "tool": item["id"], "argv": command,
                              "cwd": str(Path.cwd()), "executed": False,
                              "arguments_validated": False, "authorization_granted": False},
                             ensure_ascii=False, indent=2))
            return 0
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        # No shell, implicit profile, permission, retry or success reinterpretation.
        return subprocess.call(command, env=env, shell=False)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "toolbox_error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
