"""Run the frozen engine's bundled offline regressions, including newer tests.

This package-level helper does not change the scientific engine. It combines
the original portable_tests.MODULES list with tests/test_*.py and scripts/test_*.py. It is not a
structure-accuracy benchmark or a native-software/website certification.
"""
import argparse
import ast
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import time
import unittest


def plain(value):
    path = Path(value).absolute()
    for candidate in (path, *path.parents):
        if candidate.is_symlink() or getattr(candidate, 'is_junction', lambda: False)():
            raise ValueError('Linked paths are not accepted: ' + str(candidate))
    return path.resolve()


def run(args):
    skill, output = plain(args.skill), plain(args.output)
    package = Path(__file__).resolve().parent
    if not (skill / 'SKILL.md').is_file():
        raise ValueError('Select a complete skill directory containing SKILL.md')
    if output.is_relative_to(package) or output.is_relative_to(skill):
        raise ValueError('Keep test output outside the frozen package and skill')
    if output.exists():
        raise FileExistsError('Choose a new output directory; existing tests are preserved')
    modules = []
    source = ast.parse((skill / 'scripts/portable_tests.py').read_text('utf-8-sig'))
    for node in source.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'MODULES' for t in node.targets):
            modules.extend(ast.literal_eval(node.value))
    if not modules:
        raise ValueError('Original portable test module list not found')
    modules.extend(p.stem for p in sorted((skill / 'tests').glob('test_*.py')))
    modules.extend(p.stem for p in sorted((skill / 'scripts').glob('test_*.py')))
    modules = list(dict.fromkeys(modules))
    for value in reversed(args.module_dir):
        path = plain(value)
        if not path.is_dir():
            raise ValueError('Missing module directory: ' + str(path))
        sys.path.insert(0, str(path))
    sys.path[:0] = [str(skill / 'tests'), str(skill / 'scripts')]
    sys.dont_write_bytecode = True
    os.environ.update(PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    output.mkdir(parents=True, exist_ok=False)
    scratch = output / 'scratch'
    scratch.mkdir()
    tempfile.tempdir = str(scratch)
    start = time.perf_counter()
    with (output / 'tests.log').open('w', encoding='utf-8') as log:
        suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    info = {
        'schema': 1, 'modules': modules, 'module_count': len(modules),
        'tests': result.testsRun, 'failures': len(result.failures),
        'errors': len(result.errors), 'skipped': len(result.skipped),
        'skips': [{'test': str(test), 'reason': reason} for test, reason in result.skipped],
        'failed_tests': [str(test) for test, _ in result.failures],
        'error_tests': [str(test) for test, _ in result.errors],
        'success': result.wasSuccessful(), 'seconds': round(time.perf_counter() - start, 3),
        'python': sys.version, 'platform': platform.platform(),
        'skill': str(skill), 'log': str(output / 'tests.log'),
        'native_program_execution': False, 'official_upload': False, 'new_crystal_solved': False,
        'scope': 'Offline synthetic regressions only; not crystallographic correctness or cross-agent/host certification.'
    }
    (output / 'results.json').write_text(json.dumps(info, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in info.items() if k != 'modules'}, ensure_ascii=False))
    return 0 if result.wasSuccessful() else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skill', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--module-dir', action='append', default=[])
    try:
        return run(parser.parse_args())
    except (ValueError, OSError, SyntaxError) as exc:
        print(json.dumps({'status': 'test_setup_error', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
