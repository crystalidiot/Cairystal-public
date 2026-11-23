# Third-party notices / 第三方声明

本文件随 Cairystal skill 一起分发，用于标明第三方依赖及其许可。它不改变 Cairystal 自有代码的许可证，也不代表已经完成全部依赖的法律审计。

## Gemmi

| 项目 | 内容 |
|---|---|
| 名称 / Name | Gemmi |
| 本次核对版本 / Verified version | 0.7.5 |
| 上游版权声明 / Upstream copyright notice | © 2017–2025 Global Phasing Ltd. |
| 本包采用的许可路径 / License selected for this notice | Mozilla Public License 2.0 (MPL-2.0) |
| 官方项目 / Project | https://github.com/project-gemmi/gemmi |
| 对应版本源码 / Versioned source | https://github.com/project-gemmi/gemmi/tree/v0.7.5 |
| 对应版本源码归档 / Source archive | https://github.com/project-gemmi/gemmi/archive/refs/tags/v0.7.5.tar.gz |
| 上游许可证 / Upstream license | https://github.com/project-gemmi/gemmi/blob/v0.7.5/LICENSE.txt |
| 本地许可证副本 / License copy | [licenses/Gemmi-MPL-2.0.txt](licenses/Gemmi-MPL-2.0.txt) |
| 来源与哈希 / Provenance | [licenses/gemmi-0.7.5.provenance.json](licenses/gemmi-0.7.5.provenance.json) |

Gemmi is an external dependency used for crystallographic file handling, symmetry and geometry. This Cairystal skill source archive does not bundle the Gemmi library, Python wheels, DLLs or executables. The license text is included for notice and reference purposes. Users install the dependency separately. The links above identify the upstream source corresponding to the version verified here.

Cairystal 将 Gemmi 作为外部依赖，用于晶体学文件处理、对称性及几何计算。本次 skill 源码包不捆绑 Gemmi 库、wheel、DLL 或可执行程序；用户另行安装依赖。随包保留许可全文和版本源码链接，方便核查。实际安装版本应写入运行记录；升级依赖后须重新核对相应版本，不能把本声明的 0.7.5 当成其他版本的证明。

Gemmi 0.7.5 的上游 README 另提供 LGPLv3 选项；本声明选择 MPL-2.0 路径，并未取消上游授予的其他选项。独立调用 Gemmi 的 Cairystal 文件不因调用而自动改用 MPL；复制 Gemmi 代码或修改 Gemmi 文件时，必须按相关许可单独处理。

若以后分发含 Gemmi 的离线安装包或打包 EXE，应按[再分发说明](references/redistribution-licenses.md)保留许可、版权及适用的第三方声明，明确提供所分发版本的对应源码，包括适用的修改。仅有本声明不能代替这些工作。

Gemmi contains or uses third-party components with their own notices. Those notices must be assessed against the exact contents of any future binary bundle; the MPL text alone is not a complete notice set for every Gemmi build. No endorsement by Gemmi, its contributors, CCP4 or Global Phasing Ltd is implied.

## Other dependencies / 其他依赖

本次新增并核对的是 Gemmi 条目。SHELX、PLATON、Olex2、Python、报告及可选识图依赖仍适用各自的许可；没有在本文件中列出不代表无许可义务。软件安装和发布包核对分别见 [Windows 安装说明](references/windows-install.md)及[再分发说明](references/redistribution-licenses.md)。

核对日期：2026-10-30。

## Bundled local console / 本地控制台

React、React DOM、React Flow 及实际进入前端包的依赖保留其各自的许可，不适用 Cairystal 自有代码的使用限制。逐项版本、版权与完整许可见 [控制台声明](licenses/console/NOTICE.md)。普通包只包含构建后的网页资源及可复现源文件，不包含 Node、node_modules 或 esbuild 可执行程序。


## Logo lettering / 标识字形

The supplied PNG uses Selawik outlines. [Font licence](licenses/OFL-Selawik.txt) · [Upstream](https://github.com/microsoft/Selawik/tree/89362e84731d1f5777fa078fd4d5ebbd339e4378). No font binary is included. Logo SHA256: 524ae0fb4d423b09ed8e7a1a926ef1c8f82ddb90609c2365cbac2fd6e570ba6f.
