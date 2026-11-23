# Windows 安装与验收 / Windows setup and acceptance

使用 Windows x64、Python 3.12，打开 PowerShell，进入解压后含 verify_package.py 的 Cairystal 目录。路径可含空格和中文。以下示例在包旁建立独立的工作目录。新电脑请填写本机实际路径。

Use Windows x64 and Python 3.12. In PowerShell, change to the extracted Cairystal directory containing verify_package.py. The examples create a sibling working directory. Replace all example executable paths with the actual files on this machine.

```powershell
$pkg = (Get-Location).Path
$work = Join-Path (Split-Path $pkg -Parent) 'Cairystal-work'
$skill = Join-Path $pkg 'Chinese/small-molecule-crystal'
# For English: $skill = Join-Path $pkg 'English/small-molecule-crystal'
py -3.12 -B verify_package.py
py -3.12 -m venv "$work/venv"
$py = "$work/venv/Scripts/python.exe"
& $py -m pip install -r requirements-test.txt
& $py -B "$skill/cairystal.py" version
& $py -B "$skill/cairystal.py" list
```

**安装外部程序 / External programs.** SHELXT、SHELXL 来自使用者获授权的 [SHELX](https://shelx.uni-goettingen.de/) 安装；SHELXD 用于备用求解。可使用 [Olex2](https://www.olexsys.org/olex2/docs/getting-started/) 环境中已合法安装的程序。请确认 [PLATON](https://www.platonsoft.nl/platon/pl030000.html) 可运行。报表需要本机 Word 或 LibreOffice 和 Poppler 的 pdftoppm。SHELX、PLATON、Word 及其安装程序请按各自条款另行取得。Use your own authorized executables. Optional SHELXD enables fallback solving. Install Word or LibreOffice and Poppler for report rendering.

**生成本机配置 / Configure this machine.** 替换下列四个示例路径。Word 用户使用下列命令。LibreOffice 用户将最后的 renderer 和 powershell 两项改为 `--renderer libreoffice --soffice "C:/Program Files/LibreOffice/program/soffice.exe"`。可另加 `--shelxd "完整路径/shelxd.exe"`。

```powershell
$profileFile = "$work/machine.json"
& $py -B configure_machine.py --skill $skill --output $profileFile --shelxt "D:/software/olex2-win64/shelxt.exe" --shelxl "D:/software/olex2-win64/shelxl.exe" --platon "D:/software/olex2-win64/platon.exe" --pdftoppm "C:/poppler/Library/bin/pdftoppm.exe" --renderer word --powershell (Get-Command powershell.exe).Source
New-Item -ItemType Directory -Force "$work/jobs" | Out-Null
& $py -B "$skill/cairystal.py" run doctor -- --profile $profileFile --output-root "$work/jobs" --output "$work/doctor.json"
& $py -B run_acceptance.py --skill $skill --output "$work/acceptance-01"
```

测试目录及 profile 文件应指定新路径。查看验收目录的 results.json 和 tests.log。遇到错误，请将错误信息和阶段提供给维护者。The acceptance command writes a new directory. Inspect results.json for failures, errors and skips. Keep the environment, runs and results outside the extracted ZIP directory.

**官网与交付 / Online validation and delivery.** 官网验证需要网络与样品上传许可。默认浏览器回退使用本机 Microsoft Edge。若改用 Playwright Chromium，先运行 `& $py -m playwright install chromium`，再在运行该任务的 PowerShell 会话执行 `$env:CAIRYSTAL_BROWSER_CHANNEL = 'chromium'`。如果上传或下载失败，请保留任务目录和回执以便续接。最终应核对含结构因子的 CIF、IUCr_checkCIF.pdf、中文 Word 和英文 Word。Make sure the official receipt and PDF belong to the final CIF. Local PLATON is a separate check.
