# 本机资源与原生程序速度 / Native resources

常规 SHELXL 调用统一经 `crystal_runtime.run_command` 配置资源。每次新调用在本机只读检测 CPU、进程可用 CPU、总/可用内存，不沿用作者电脑检测值。策略在 `assets/native_resources.json`：可用逻辑处理器数减 1（最低 1），再与 8 及下表内存档位取最小值。全矩阵参数容量保持 6000。这是保守资源分配规则，不是每台电脑实测出的最优速度。

| 当前可用内存 | 自动线程上限 |
|---|---:|
| 小于 1 GiB | 1 |
| 1 至小于 2 GiB | 2 |
| 2 至小于 4 GiB | 4 |
| 至少 4 GiB | 8 |
| 检测不到 | 2，并说明未知 |

低内存不会自动降低模型参数容量、删原子、减少精修或验证项目。减少线程也不保证模型一定装得进内存；分配失败仍须保留真实错误并处理环境。默认流程顺序运行；独立启动的多个 agent 不受本策略统一调度，不承诺全机并发总额。

```powershell
python -B scripts/toolbox.py run native-resources -- --output NEW_RESOURCE_INFO.json
python -B scripts/toolbox.py run doctor -- --profile LOCAL_PROFILE.json --output-root JOBS_DIRECTORY --output NEW_ENVIRONMENT.json
python -B scripts/toolbox.py run stage -- --executable SHELXL.exe --ins INPUT.ins --hkl INPUT.hkl --output NEW_RUN --reason "Explicit resource comparison on unchanged input" --threads 8 --matrix-parameters 6000
```

`native-resources` 只读基础配置，不联网、不采集序列号/主机名/用户名、不修改系统配置；命令行工具执行权限由客户的 agent 提供。可加 `--output-root` 读取选定磁盘的可用空间（不证明可写）。`doctor` 同时检查依赖和 profile 指定的可执行文件/哈希，缺失或不符直接列出；不搜索客户其它样品，也不运行求解器。安装前检查使用相同硬件策略；Windows 有 D 盘优先 D，无 D 时使用系统盘，支持明确指定其它目录。

`stage` 的手动参数仅用于 SHELXL；在本进程可用 CPU 数以内允许显式覆盖，并记录偏离自动建议的提示。实际命令日志包含检测快照、选参理由和警告。`repair-plan` 一组对照固定同一资源设置，续跑沿用已校验的设置，避免可用内存变化导致重复计算；换机后可用 CPU 不够则明确拒绝混用，应在新目录重新比较。资源进入去重和续跑核验。`doctor` 建议每台新电脑首次安装、换软件/profile 或遇到环境故障时运行；常规每轮原生调用只做轻量硬件检测，不重复全依赖检查。

## 两种参数不能混淆

- `-tN` 是线程数，不是保证利用 N 个物理核心；线程更多不保证更快。小任务会受启动、I/O、同步开销影响。
- `-bN` 是**最大全矩阵参数数量**，不是 MB 或 GB。它扩大能够处理的模型容量，不增加实验信息或改善精修精度。只有容量不足才需要增加，不能靠反复放大来“加速”。本轮已测 3000、6000、12000；6000 到 12000 未见明确速度收益。
- 线程测试保持 INS、HKL、权重、周期及模型完全相同，记录原生命令、版本、输入哈希、指标和 A/B。并行浮点运算可能有末位差别；保留实际差异，不能为追求相等改写结果。
- 当前帮助的线程与容量范围按已安装的 SHELXL 2018/3 MULTI-CPU 版核对。其他构建先用其原生帮助和小规模实测检查，未知不填确定值。

## PLATON

没有把 SHELXL 的 `-t` / `-b` 传给 PLATON：这些字符在 PLATON 中另有含义。仍执行 `-u` 完整本地 CIF/FCF 检查，继续检查规则来源、报告尾部、反射文件、解析一致性和输入哈希。

对已识别的输出格式，额外核对 CheckCIF/CheckFCF/CheckPlots 完成通知、PostScript 页数和 `%%EOF`；四份产物的内容哈希稳定至少 0.4 秒后返回。最终再核对这些哈希，避免仅看大小造成误判。无法取得这些强证据时保留原有的 1.5 秒稳定等待；程序自行退出时仍完成全部后检。没有省略 A/B 项，也不以本地报告替代最终已授权官网 PDF。

`local_validation(..., completion_mode="conservative")` 可作旧等待策略的独立对照。运行记录的 `completion_policy` 明确写出采用的方法及证据。无需弹出 Olex2，不提高进程优先级、不修改系统安全设置、不把任务并发堆满机器。

## English

Every new SHELXL call queries the customer's own CPU affinity and available RAM using local OS APIs. Auto threads are the minimum of (usable logical CPUs minus one, at least one), eight, and an available-RAM cap: below 1/2/4 GiB allows at most 1/2/4 threads; unknown RAM allows at most two. These are conservative heuristics, not a benchmarked optimum or a RAM allocation guarantee. The matrix capacity stays 6000; `-b` is not a memory quota. No atoms, precision, refinement cycles, AB checks, official validation or Word reports are removed to save resources.

`native-resources` displays/saves the hardware snapshot, actual settings and reasons; `--output-root` optionally checks disk free space without creating directories. `doctor --profile LOCAL_PROFILE.json --output-root JOBS_DIRECTORY --output NEW_ENVIRONMENT.json` also checks dependency imports and the selected executable paths/hashes, without running them or contacting services. Run doctor on installation, software/profile changes or environment failures, not inside every refinement loop. Windows installation defaults to D when available, otherwise the system drive. Explicit paths remain supported.

Manual `stage --threads N --matrix-parameters N` overrides are permitted within usable CPUs and logged. A diagnostic comparison pins its resources across branches and verified continuation despite RAM changes. A machine that cannot support the pinned CPU setting must start a fresh comparison. Independent agents are not globally scheduled by this policy. Only basic machine information is read; no username, hostname or device serial is collected. Detection failure remains unknown and falls back conservatively. GPU acceleration and cgroup container memory quotas are not implemented; Windows is the native integration environment tested for this release. The agent must support permitted local command execution.

PLATON keeps complete `-u` validation and its existing conservative completion fallback; it does not receive SHELXL threading flags. Hardware decisions do not alter that workflow.

技术依据：本机 SHELXL 无参数启动的原生帮助（记录于本轮工程证据）；[PLATON 官方启动参数](https://www.platonsoft.nl/platon/pl060000.html)。不要把其它同名 PLATON 区块链或计算框架的并行文档用于晶体学 PLATON。
