# Moving the skill between computers and agents

Read on a new computer, when software paths are uncertain, or when preparing a comparable agent test. The skill supplies instructions and helpers; it is not an executable solver or a model fine-tune.

## Record the target environment

The target agent needs permitted local file reads/writes, command execution with logs/exit states, and installed crystallographic programs. A web chat or model API alone does not provide these capabilities. Load `SKILL.md` through the host's supported skill interface or explicitly read it from the selected directory. `agents/openai.yaml` is optional Codex UI metadata; do not invent another host's installation path or claim compatibility without testing that host.

Record the actual skill location/hash, Python executable/version, dependency versions, per-program absolute paths/hashes and output root. Historical workstation paths and version tables are evidence from that workstation, not defaults that must exist elsewhere. No global PATH change is needed.

On each target computer, run `python -B scripts/toolbox.py run doctor -- --profile LOCAL_PROFILE.json --output-root JOBS_DIRECTORY --output NEW_ENVIRONMENT.json`. It includes local CPU/affinity/RAM, dependency checks, configured executable file/hash checks and disk free space. Use `native-resources` if only basic machine information is needed. These are read-only checks with explicit output files; they do not upload data or prove native execution/permissions. Runtime resource selection and conservative fallback are documented in [native-performance](native-performance.md); do not copy another machine's detected settings as local measurements.

## Check by the operation requested

Use `python scripts/probe_environment.py --software-dir "actual program folder" --profile solve --json`.

| Profile | Executable files checked |
|---|---|
| `solve` (default) | SHELXT + SHELXL |
| `solve_d` / `solve_s` | SHELXD / SHELXS + SHELXL |
| `refine` | SHELXL |
| `validate` | PLATON |
| `viewer` | Olex2 |
| `bundle` | Historical combined Olex2 + SHELXT + SHELXL + PLATON check |

Missing Olex2 does not block command-line solution/refinement. Missing PLATON blocks that local validation stage, not prior phasing. An alternative solver's presence does not authorize arbitrary transfer of another solver's parameters.

The probe is read-only. `ready` means the selected executable files are present and readable; it does not prove they run, that a licence applies, or that PLATON has compatible `check.def`/runtime libraries. Version strings are hints. Do not read an old neighbouring `platon.out` to identify the current binary: it may be stale or contain a protected historical case. Obtain the actual banner from a new permitted isolated run.

Software may be distributed across folders. Probe those explicitly selected folders, record each actual executable path, and use those paths in commands. Do not silently substitute an unrelated PATH executable. The legacy `setup_job.py` and `install_preflight.py` still describe a combined installation: their missing-tool lists must be interpreted by stage, not erased. Supply `--software-dir` and `--output-root` explicitly to setup; a handoff configuration file is not automatically read by the original helpers.

## Validate in layers

The exception-only `autofinish` route additionally needs `pdfplumber` for measured PDF layout checks; synthetic PDF tests need `reportlab`. See [agent handoff](agent-handoff.md) for what is executable versus documentary knowledge. Install dependencies and build the runtime profile on the target computer; do not assume this workstation's module directories are portable.

1. Verify package contents against its manifest and the extraction result; this checks integrity, not scientific correctness.
2. Check dependencies and run synthetic regression tests in a new temporary/output directory. Python 3.12 with Gemmi 0.7.5 was used in the recorded migration check. Keep bytecode/temp files outside the frozen skill.
3. Run an authorized teaching sample through the relevant external software in an isolated job. Record actual executable banners, completion and outputs. Use only data permitted for that test; do not access an old case to work around a failed setup.
4. Evaluate scientific models and agent decisions separately. Passing tests or a successful import does not establish independent structure solution or cross-agent equivalence.

## Preserve comparable releases

Archive the exact skill file tree and hashes used for each benchmark. Later learning updates create a new version; do not overwrite the frozen package or reinterpret its old results as testing the new skill. For strict blind testing, load only case-free routes, isolate outputs between agents, and respect the test's input boundary even when metadata are missing.

A redistributable package should contain the skill and needed helpers, not experimental datasets, reference models, passwords, licence credentials or software installers. Historical explanatory text in the full references still requires blind-test routing discipline. The tests and stage gates in [acceptance-tests](acceptance-tests.md) define the verified scope; installation uses [windows-install](windows-install.md).

## 按功能检查 Python 依赖

先运行 `python scripts/runtime_capabilities.py --profile PROFILE.json`。输出分别检查核心数据处理、双语报告、自动排版检查、局部 Fourier 诊断。局部差值图需要 NumPy；缺少它只影响该诊断能力，不应误报基础精修也不可用。这个检查只证明导入成功，外部程序、Word/LibreOffice 渲染和网站仍需相应实测。

2026-10-29 维护在独立依赖目录测试了 NumPy 2.5.4，并通过本机 profile 的 module_dirs 引入，没有修改原 Python 环境。其他电脑需自行安装兼容版本并回归验证，不能照抄本机盘符。


## Native PLATON validation readiness

Do not diagnose missing rules from absence of an external `check.def`. Modern builds embed rules; their actual selected versions are recorded in the `.chk` header. Use `platon_check.py --profile PROFILE --cif INPUT --output NEW_DIRECTORY` to execute a real isolated validation. Add `--fcf PAIRED_FCF` when supplied separately; otherwise the script requires supported reflections embedded in the CIF. Empty early output is not completion or proof of missing rules. See [PLATON and PDF reliability](platon-and-pdf-reliability.md). Do not mix unrelated DLLs, rule files or executables, or delete environment variables globally to mask an error.

## Preserve dependency notices when packaging

Include the skill-root `THIRD_PARTY_NOTICES.md` and `licenses/` in source ZIPs and file manifests. Gemmi is installed separately in this package. Before bundling a runtime, wheel or executable, follow [redistribution guidance](redistribution-licenses.md), record the actual included version, preserve applicable notices and identify matching source. This does not replace other software licence checks.
