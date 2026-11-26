# Delivery state synchronization / 交付状态同步

完成交付后，子流程释放锁时自动核对并同步顶层 `autorun.json`、交接记录和任务页面。`autorun status` / `resume` 也会恢复遗漏的同步。完成依据是本任务的正式交付记录、对应 CIF 的官网 PDF、中英文 Word 及客户目录内文件哈希；不凭文件存在或低 R 判断。重复续跑不会再次求解、精修、上传或生成报告。

旧版已交付任务可以运行：
```text
python -B cairystal.py run autorun -- sync-delivery --run CURRENT_JOB --expected-hkl ORIGINAL_HKL
```
该命令只修复已完成交付的状态，保留原计算版本与 `completion_sync/previous_autorun.json`、旧交接记录。它不会把未完成任务迁移到新版，不重新上传 CIF。正常新任务不需要额外调用。子流程尚未完成、报告缺失/被改动、样本不匹配或任务正运行时，不将其标记为完成。同步问题记录在 `completion_sync_error.json`，保留已有交付。

The child pipeline notifies its coordinator after releasing its lock. Status/resume also reconcile completed delivery. Exact-CIF official validation, both Word outputs, original specimen binding and customer export hashes must agree. Repeated resume performs no scientific computation or network/report work. The explicit command above repairs older completed jobs without changing their original execution-version record; unfinished jobs remain fixed-version runs. Previous coordinator/handoff records are retained. Delivery completion is not a new assertion of structural correctness.
