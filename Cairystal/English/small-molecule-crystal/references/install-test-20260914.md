# Windows isolated installation test: 2026-09-14

This is an evidence record, not permanent release metadata. Re-resolve official URLs, versions, sizes, and checksums on every future installation.

## Scope

- Use: non-profit academic work at a university or research institution.
- Test root: `D:\software\crystal-skill-install-test-20260914`.
- Existing installation `D:\software\olex2-win64` was not modified.
- Windows: 64-bit; destination had approximately 440 GB free before installation.
- No global `PATH` or persistent environment-variable changes were made.

## Olex2

- Source: official Olex2 distribution server.
- Archive: `olex2-win64.zip`, 216,027,998 bytes.
- MD5: `D6C816C6D03D9D1356031D63959317E2`, matching the official index at download time.
- Detected version: Olex2 1.5, SVN 7665.
- Archive scan: 8,881 entries and no unsafe paths.
- Result: `olex2.exe` launched hidden and exited normally with code 0.
- Observation: this archive contained no `shelxt.exe`, `shelxl.exe`, or `platon.exe`.

## PLATON and PWT

- `platon.zip`: 1,952,230 bytes; SHA-256 `A8C845891DC1DCA1CB98D691917355C1BDB1C380E947A91893966D163900063B`.
- `platon.exe`: 4,786,688 bytes; SHA-256 `2A19E5F197DA962E073EDD93BED10E56A7B1A10EE91B8F5B6875B5EA006C3E07`.
- `check.def`: 276,227 bytes; SHA-256 `B546826010958862B3CF741B351728BFBB9D476231FE2446C7D91A8AFFE85ACB`; first line reports version `260619`.
- `pwt_setup.zip`: 1,924,095 bytes; SHA-256 `B60FA412F7B2E95287826C364A9AA7FFF5CD962BC11FAE42D91CC4E70CFAB276`.
- PWT installer: Inno Setup 5.2.3; installed silently with no shortcuts into `app\pwt`; exit code 0.
- The current `platon.zip` contained only `platon.exe`. A first direct run failed with Windows code `0xC0000135`; dependency inspection identified `salflibc.dll`. The PWT installer supplied that library.
- PWT launch test: `pwt.exe` remained alive after six seconds, confirming successful GUI startup; only that test process was then terminated.
- PLATON validation test: `app\pwt\platon.exe -u s810c.cif` generated `s810c.chk` (5,669 bytes), `s810c.ckf` (123 bytes), `s810c.vrf`, and `platon.out`. The report identified PLATON/CHECK and `check.def` version `260619`. The exact process was terminated only after output completion because the graphical program remained resident.

## SHELX

- Status: not downloaded into the fresh test directory.
- Reason: the official academic download requires registration and emailed credentials. This is a user identity and licence checkpoint, not a technical download failure.
- Next action: the user completes official academic registration or confirms that credentials already exist, then the skill downloads SHELXT/SHELXL from the authenticated official page and runs solve/refine teaching examples in an isolated job.
