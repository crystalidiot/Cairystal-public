# Windows software installation

Use this reference only when Olex2, SHELX, or PLATON is missing or the user asks for installation help.

## Required components

The beginner workflow needs:

- Olex2 for optional graphical inspection and guided structure work; it is not required to open or run for command-line solution/refinement;
- SHELXT for routine small-molecule structure solution;
- SHELXL for refinement;
- SHELXD/SHELXS when a justified alternative solution route is needed;
- PLATON with working validation rules for local checkCIF/FCF validation. Modern builds may embed rules; an external `check.def` is not universally required.

For a partial installation, report readiness by operation using [portable-environment](portable-environment.md). The installation preflight's combined missing-file list does not mean every missing component blocks every stage.

## Official sources and licence routing

Re-open the official pages immediately before each installation and resolve the current Windows download there. Do not use third-party mirrors, search-result download buttons, or an old link copied from a prior run.

- Olex2 documentation and download server: `https://www.olexsys.org/olex2/docs/getting-started/` and `https://secure.olexsys.org/olex2-distro/`. Olex2 is free to use; prefer the current official release rather than alpha or beta for beginners.
- SHELX homepage and registration/download route: `https://shelx.uni-goettingen.de/`. SHELX is free for academic use; for-profit users require the applicable paid licence. Never register, accept terms, or represent the user's organisation without the user's input.
- PLATON information and Windows downloads: `https://www.platonsoft.nl/platon/pl030000.html` and the official Windows directory linked from the PLATON site. PLATON is free for academics; for-profit organisations must follow the stated licence/contact route.

If the current Olex2 Windows distribution already contains working SHELXT/SHELXL or PLATON executables, record and verify them instead of downloading duplicates. The presence of files does not settle the user's licence eligibility.

Do not assume that the current Olex2 archive bundles SHELX or PLATON. Inspect the archive and probe the extracted directory. The official Olex2 1.5 Windows archive tested on 2026-09-14 contained neither package.

### SHELX academic registration boundary

The official SHELX download page is credential-protected. For an academic or non-profit user who has no download credentials:

1. explain that registration is required by the official distributor;
2. open or link the official registration page for the user;
3. let the user enter their own name, affiliation, email, and anti-spam answer;
4. wait until the user reports that the emailed download credentials are available;
5. let the user type credentials in the official page rather than pasting a password into chat.

Never invent an affiliation, answer the registration challenge for the user, reuse credentials from another person, or download from an unofficial mirror.

### PLATON first-install layout

Treat a first Windows installation as two official components:

- `pwt_setup.zip`, whose installer supplies the PWT launcher and `salflibc.dll`;
- `platon.zip`, which supplies the frequently updated `platon.exe`.

Inspect the currently selected official distribution and its instructions before extraction. If that build requires PWT/`salflibc.dll`, install the matching runtime in an isolated directory and put the executable there. Do not mix arbitrary DLL or rule versions. Historical archive contents are not a current requirement: absence of `check.def` alone is not an error. Run `platon_check.py` and record the selected rule version from actual reports; obtain an external rule file only when the selected build's documented requirements or explicit native errors establish that it is needed. See [PLATON/PDF reliability](platon-and-pdf-reliability.md).

Use a specifically selected installation destination and respect the user's existing installation authorization. Do not change global environment variables or enable shortcuts incidentally. Whether embedded or external, record the rules actually used in an isolated validation job instead of diagnosing installation by file presence alone.

## Preflight

Run:

```text
python scripts/install_preflight.py --target D:\software\olex2-win64 --json
```

Check:

- Windows and 64-bit architecture;
- destination drive exists;
- sufficient free space;
- target is missing, empty, a recognised installation, or contains unrelated files;
- whether required executables are already present;
- whether administrator elevation is actually required.

Never propose overwriting a non-empty unrecognised directory. Offer a new versioned directory instead.

## Consent boundary

Before downloading, show:

- exact official domain;
- release channel and resolved version;
- destination directory;
- approximate download size and available disk space;
- whether an installer will run or a portable archive will be extracted;
- whether administrator elevation, shortcuts, or environment-variable changes are proposed;
- the user's academic/non-profit or for-profit route.

Ask one yes/no question for the concrete plan. A previous general statement such as “帮我安装” does not authorize a changed destination, overwriting files, accepting licence terms, or system-wide configuration.

## Preferred beginner installation shape

Prefer a portable, isolated installation under `D:\software\olex2-win64` when D exists and the official release supports it; otherwise choose a permitted location such as `C:\software\olex2-win64`. Download to a separate staging directory, verify the official checksum when published, extract into a new empty directory, and only then promote it as the selected software directory.

Do not add the folder to global `PATH` by default. The skill can call programs with absolute paths, and Olex2 can be configured to search an explicit external-program directory. Ask separately before changing system-wide settings.

## Verification

Installation is complete only after all of the following pass:

1. `olex2.exe`, `shelxt.exe`, `shelxl.exe`, and `platon.exe` are found or the missing component has a documented licence/download next step;
2. paths, versions, sizes, and hashes are recorded;
3. SHELXT solves a bundled teaching example in an isolated directory;
4. SHELXL completes a refinement and generates `.res` and `.lst`;
5. PLATON generates `.chk` and `.ckf` from a bundled CIF;
6. any process that remains interactive after output generation is handled using the exact-process rule in [workflow.md](workflow.md);
7. the user receives a summary in the selected language and the installation location, with verified and unavailable stages distinguished.

Do not start with the user's experimental data. Use a bundled example for installation verification.

For PLATON, Windows exit code `0xC0000135` means a required DLL could not be loaded. Inspect the executable dependencies before redownloading. The official build tested on 2026-09-14 required `salflibc.dll`, which was supplied by the official PWT installer. A successful `platon -u example.cif` run must be judged by the generated `.chk` and `.ckf` files as well as process state; the graphical process can remain resident after the reports are complete.

## Failure handling

Keep downloaded archives and logs when verification fails unless the user asks to remove them. Report the failed component and one recovery action. Do not repeatedly redownload a package without checking the prior file, official checksum, available space, proxy/firewall errors, and licence route.
