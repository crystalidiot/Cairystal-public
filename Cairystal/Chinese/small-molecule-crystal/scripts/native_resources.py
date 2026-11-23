"""Read local resources and choose bounded SHELXL settings; -b is not RAM in MB."""
from pathlib import Path
import argparse
import ctypes
import datetime
import json
import os
import platform
import re
import shutil
import struct

POLICY = Path(__file__).resolve().parent.parent / 'assets/native_resources.json'
GIB = 1024 ** 3


def _positive(value):
    return type(value) is int and value > 0


def _affinity_count():
    """Only query this process; never change affinity or priority."""
    if hasattr(os, 'sched_getaffinity'):
        return len(os.sched_getaffinity(0)) or None
    if os.name == 'nt':
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.GetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
        kernel.GetProcessAffinityMask.restype = ctypes.c_int
        process_mask, system_mask = ctypes.c_size_t(), ctypes.c_size_t()
        if not kernel.GetProcessAffinityMask(kernel.GetCurrentProcess(), ctypes.byref(process_mask), ctypes.byref(system_mask)):
            raise OSError(ctypes.get_last_error(), 'Cannot query process CPU affinity')
        # On >64-CPU Windows systems this is the primary group, a conservative bound.
        return process_mask.value.bit_count() or None
    return None


def _memory():
    if os.name == 'nt':
        class Memory(ctypes.Structure):
            _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [
                (n, ctypes.c_ulonglong) for n in ['total', 'available', 'total_pagefile', 'available_pagefile', 'total_virtual', 'available_virtual', 'extended']]
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(Memory)]
        kernel.GlobalMemoryStatusEx.restype = ctypes.c_int
        m = Memory(); m.length = ctypes.sizeof(m)
        if not kernel.GlobalMemoryStatusEx(ctypes.byref(m)):
            raise OSError(ctypes.get_last_error(), 'Cannot query available RAM')
        return m.total, m.available, 'GlobalMemoryStatusEx'
    if platform.system() == 'Linux':
        values = {}
        for line in Path('/proc/meminfo').read_text('ascii').splitlines():
            key, _, value = line.partition(':')
            if key in {'MemTotal', 'MemAvailable'}: values[key] = int(value.split()[0]) * 1024
        return values.get('MemTotal'), values.get('MemAvailable'), '/proc/meminfo'
    if hasattr(os, 'sysconf'):
        total = os.sysconf('SC_PHYS_PAGES') * os.sysconf('SC_PAGE_SIZE')
        try: available = os.sysconf('SC_AVPHYS_PAGES') * os.sysconf('SC_PAGE_SIZE')
        except (OSError, ValueError): available = None
        return total, available, 'sysconf'
    return None, None, 'unavailable'


def hardware():
    result = {'logical_processors': None, 'usable_logical_processors': 1,
              'affinity_logical_processors': None, 'cpu_name': None,
              'total_ram_bytes': None, 'available_ram_bytes': None,
              'os': platform.system(), 'architecture': platform.machine(),
              'python_bits': struct.calcsize('P') * 8,
              'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'warnings': []}
    try:
        count = os.cpu_count()
        result['logical_processors'] = count if _positive(count) else None
    except (OSError, RuntimeError): pass
    candidates = [result['logical_processors']] if result['logical_processors'] else []
    try:
        affinity = _affinity_count()
        if _positive(affinity):
            candidates.append(affinity); result['affinity_logical_processors'] = affinity
        else: result['warnings'].append('Process CPU affinity unavailable; using detected CPU count.')
    except (OSError, ValueError, AttributeError, RuntimeError):
        result['warnings'].append('Process CPU affinity query failed; using detected CPU count.')
    if hasattr(os, 'process_cpu_count'):
        try:
            count = os.process_cpu_count()
            if _positive(count): candidates.append(count)
        except (OSError, RuntimeError): pass
    result['usable_logical_processors'] = min(candidates) if candidates else 1
    if not candidates: result['warnings'].append('CPU count unavailable; using one thread.')
    if os.name == 'nt':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
                result['cpu_name'] = winreg.QueryValueEx(key, 'ProcessorNameString')[0].strip()
        except (ImportError, OSError): pass
    try:
        total, available, source = _memory()
        result.update(total_ram_bytes=total if _positive(total) else None,
                      available_ram_bytes=available if type(available) is int and available >= 0 else None,
                      memory_source=source)
        if result['total_ram_bytes'] and result['available_ram_bytes'] is not None:
            result['available_ram_bytes'] = min(result['total_ram_bytes'], result['available_ram_bytes'])
    except (OSError, ValueError, AttributeError, RuntimeError): result['memory_source'] = 'unavailable'
    if result['available_ram_bytes'] is None: result['warnings'].append('Available RAM unknown; use conservative automatic threading.')
    if result['python_bits'] < 64: result['warnings'].append('32-bit Python detected; use a 64-bit runtime for the supported full pipeline.')
    return result


def disk_info(directory):
    requested = Path(directory).expanduser().resolve(); existing = requested
    while not existing.exists() and existing.parent != existing: existing = existing.parent
    info = {'requested_path': str(requested), 'checked_path': str(existing), 'free_bytes': None}
    try:
        usage = shutil.disk_usage(existing)
        info.update(free_bytes=usage.free, total_bytes=usage.total, low_space_warning=usage.free < 2 * GIB, writable_verified=False)
    except OSError as exc: info['error'] = str(exc)
    return info


def policy():
    p = json.loads(POLICY.read_text('utf-8-sig'))
    if set(p) != {'schema', 'shelxl', 'platon_completion'} or p['schema'] != 2: raise ValueError('Invalid native resource policy')
    s = p['shelxl']
    if set(s) != {'threads', 'max_auto_threads', 'reserve_logical_processors', 'unknown_memory_threads', 'memory_thread_caps', 'matrix_parameters'}:
        raise ValueError('Unknown SHELXL resource setting')
    for name in ['max_auto_threads', 'unknown_memory_threads']:
        if not _positive(s[name]) or s[name] > 128: raise ValueError('Invalid automatic thread setting: ' + name)
    if type(s['reserve_logical_processors']) is not int or not 0 <= s['reserve_logical_processors'] <= 128: raise ValueError('Invalid reserved CPU count')
    last = 0
    for cap in s['memory_thread_caps']:
        if set(cap) != {'below_gib', 'threads'} or not _positive(cap['below_gib']) or cap['below_gib'] <= last or not _positive(cap['threads']):
            raise ValueError('Invalid available-RAM thread cap')
        last = cap['below_gib']
    if p['platon_completion'] not in {'strict_fast', 'conservative'}: raise ValueError('Unknown PLATON completion mode')
    return p


def decision(threads=None, matrix_parameters=None, snapshot=None):
    h = hardware() if snapshot is None else snapshot; p = policy(); s = p['shelxl']
    logical = h.get('usable_logical_processors') or h.get('logical_processors') or 1
    if not _positive(logical): raise ValueError('Invalid usable logical CPU count')
    cpu_cap = max(1, logical - s['reserve_logical_processors']); memory_cap = s['max_auto_threads']
    available = h.get('available_ram_bytes')
    reasons = ['automatic ceiling: ' + str(s['max_auto_threads']), 'usable CPUs minus reserved CPU: ' + str(cpu_cap)]
    if type(available) is not int or available < 0:
        memory_cap = s['unknown_memory_threads']; reasons.append('available RAM unknown')
    else:
        for cap in s['memory_thread_caps']:
            if available < cap['below_gib'] * GIB:
                memory_cap = cap['threads']; reasons.append('available RAM below ' + str(cap['below_gib']) + ' GiB'); break
    recommended = min(s['max_auto_threads'], cpu_cap, memory_cap)
    requested = s['threads'] if threads is None else threads
    t = recommended if requested == 'auto' else requested
    b = s['matrix_parameters'] if matrix_parameters is None else matrix_parameters
    if type(t) is not int or not 1 <= t <= logical: raise ValueError('Thread count must be an integer within available logical processors')
    if type(b) is not int or not 100 <= b <= 12000: raise ValueError('Matrix parameter capacity must be an integer in 100..12000; it is not memory in MB')
    warnings = list(h.get('warnings', []))
    if t > recommended: warnings.append('Explicit/pinned threads exceed conservative automatic recommendation; preserved within usable CPUs.')
    if type(available) is int and available < GIB: warnings.append('Low available RAM; fewer threads do not guarantee sufficient memory. Close other work or use a larger machine if allocation fails.')
    return {'hardware': h, 'effective': {'threads': t, 'matrix_parameters': b}, 'recommended_threads': recommended,
            'mode': 'auto' if requested == 'auto' else 'explicit_or_pinned', 'reasons': reasons, 'warnings': warnings, 'policy': p,
            'concurrent_native_jobs': 1, 'b_units': 'maximum full-matrix parameters, not MB',
            'memory_limit_enforced': False, 'benchmark_optimum_claimed': False}


def effective(threads=None, matrix_parameters=None, logical_processors=None):
    h = hardware()
    if logical_processors is not None:
        if not _positive(logical_processors): raise ValueError('Invalid logical CPU override')
        h = dict(h, logical_processors=logical_processors, usable_logical_processors=logical_processors)
    return decision(threads, matrix_parameters, h)['effective']


def prepare(command, snapshot=None):
    args = [str(x) for x in command]
    if not args or Path(args[0]).stem.lower() != 'shelxl': return args, None, None
    if len(args) < 2 or args[1].startswith('-'): raise ValueError('SHELXL filename stem must precede resource flags')
    opts = {}; kept = args[:2]
    for token in args[2:]:
        match = re.fullmatch(r'-([tb])(\d+)', token)
        if match:
            key = 'threads' if match[1] == 't' else 'matrix_parameters'
            if key in opts: raise ValueError('Repeated SHELXL resource flag: ' + token)
            opts[key] = int(match[2])
        elif token.startswith(('-t', '-b')): raise ValueError('Use one positive SHELXL resource flag -tN / -bN: ' + token)
        else: kept.append(token)
    report = decision(**opts, snapshot=snapshot); selected = report['effective']
    return kept + [f"-t{selected['threads']}", f"-b{selected['matrix_parameters']}"], selected, report


def configure(command):
    args, resources, _ = prepare(command)
    return args, resources


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--threads', type=int); p.add_argument('--matrix-parameters', type=int)
    p.add_argument('--output-root', help='Inspect free space on this selected volume; no directory creation'); p.add_argument('--output'); a = p.parse_args()
    info = decision(a.threads, a.matrix_parameters)
    info.update(software_executed=False, network_used=False, system_settings_modified=False)
    if a.output_root: info['disk'] = disk_info(a.output_root)
    if a.output:
        with Path(a.output).open('x', encoding='utf8') as stream: json.dump(info, stream, ensure_ascii=False, indent=2)
    print(json.dumps(info, ensure_ascii=False))


if __name__ == '__main__': main()
