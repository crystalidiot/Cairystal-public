# Local environment audit

Historical workstation evidence only, including a teaching case below. Do not load this file in a strict no-history blind test. For new machines/agents use the case-free [portable environment](portable-environment.md); re-detect paths and record actual runtime banners. A past installation is not proof of the current target's availability or compatibility.

Audit date: 2026-09-13

Software directory: `D:\software\olex2-win64`

## Detected programs

| Program | Detected version | SHA-256 |
|---|---:|---|
| Olex2 | 1.5, SVN revision 7575 | `A23AC09076C43614974BAC3B3BAD3D197291B0B498945EE455AF0DC7DFC55BEB` |
| SHELXT | 2018/2 | `D39B9AFD31EDF84059F326BE39066356843A700AEC1C4BEC6510672516A265E7` |
| SHELXL | 2018/3 | `ECA7C510CFECAF7903FF85FEE56ECD96AF1314B307A4E01ACE13174B0E8DD662` |
| SHELXS | 2013/1 | `6E41D0347D466F8892D2B2CF20E221DB9AED72D223EBC6C612B82A35B519BEB2` |
| PLATON | 210125 | `ECF99B3C560F06975E1914F08C9284E829785E90685181A9AC0142E009D6B6D5` |
| CIFTAB | bundled | `B182C246478ABAC40869C3202E80E68E1D7F9ED1D330CE7D8C6C5F2E56DA8A9C` |
| SHREDCIF | bundled | `92C72554440312B5D9620D039FD7EA0C2F29A9A019E195D1ABD2BEA9ED89BA12` |

None of `olex2.exe`, `shelxt.exe`, `shelxl.exe`, or `platon.exe` resolved through the process `PATH` during the audit. Use absolute paths for reproducibility.

## Smoke-test evidence

The bundled `sample_data\sucrose` case was copied into `test_runs\smoke` before execution.

- SHELXT 2018/2 exited normally in about 0.5 s, read 13,643 reflections, selected space group P2(1), and produced `sucrose_a.res` and `sucrose.lxt`.
- SHELXL 2018/3 exited normally in about 0.25 s and produced `.res`, `.lst`, `.cif`, and `.fcf`. The final summary reported R1 0.0279 for observed data, wR2 0.0647, GooF 1.046, residual extrema +0.20/-0.15 e A^-3, and unreliable absolute-structure determination for this light-atom case.
- PLATON 210125 produced `.chk`, `.ckf`, `.fcf`, `.ps`, and `platon.out`. The report summary contained 0 level-A, 0 level-B, 4 level-C, and 19 level-G alerts. The process remained alive after report generation and was terminated by exact verified process ID during the isolated test.

These results establish executable compatibility, not general crystallographic correctness. Retest against representative routine, disordered, twinned, heavy-atom, and chiral structures before enabling automatic repair.
