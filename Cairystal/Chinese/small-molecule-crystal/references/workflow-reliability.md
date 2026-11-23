# 续跑与流程检查 / Checkpoints and workflow integrity

## 已完成本地收尾，继续生成报告

complete --local-only 只完成明确请求的本地阶段。状态 local_complete_waiting_delivery、full_delivery_complete=false，不代表客户所需四份文件已齐全。正常完整任务仍默认继续官网验证与双语报告；未授权上传时状态 awaiting_upload_authorization，需要已有的有效授权。

使用产生检查点的固定版本，先核对 FINISH_DIR/state.json。下列上传参数仅在已有授权时使用；工具不推定权限：

    python -B scripts/toolbox.py run resume-delivery -- --run FINISH_DIR --authorize-iucr-upload
    python -B scripts/toolbox.py run report-qa -- --run FINISH_DIR/delivery_run --output NEW_QA.json
    python -B scripts/toolbox.py run deliver -- finalize --run FINISH_DIR/delivery_run --data-dir ORIGINAL_DATA --automatic-qa NEW_QA.json --review-note "Exact-file automated QA passed; no visual or scientific acceptance claimed."

最后一步仅在 QA 通过时执行。若存在 A/B 或排版问题，处理或实际复核后再走相应路径，不能伪造通过。模型变动须重新精修和官网验证。已发起但结果不明的提交使用 recover-checkcif；resume-delivery 不重放已有 delivery_run。封存文件、代码或源数据哈希改变则不复用检查点。升级后仍从旧版本继续旧任务。

## 本轮修复的边界

- EXTI 本身是精修参数，正常的数值改变不再等同于新增/删除消光模型。前后数值保留在审计中；负值/非有限值、新增或删去 EXTI、明显的坐标/占有率/ADP 变化仍不能自动通过。并不自动引入消光，也不证明消光的物理原因。
- 自动 HFIX 前检查四字符母原子名生成多个氢时的命名风险。先为本次重原子模型生成并复核编号映射，更新二维图匹配后重新生成氢。精修后还必须检查实际原子名：同一个 RESI 内不区分大小写，不同 PART 不能复用同名。合法不同 RESI 允许同名，峰表和片段模板不当成模型原子。
- 报告 QA 使用运行记录中的实际文件主名，仍校验确切最终 CIF 哈希；改名不能让旧官网结果通过。
- HKL+JSON 尚无一键初始化入口；按 workflow 的显式参数路线建立无坐标求解输入。不得伪造 P4P、把每种元素当一个原子，或把试探的 UNIT/Z 当实测组成。该限制留待独立输入接口改进。

EXTI 定义见 SHELXL 原作者的 [指令参考](https://cpb-us-w2.wpmucdn.com/web.sas.upenn.edu/dist/f/266/files/2016/11/shelxl_comlist-1mp04in.pdf)。本页归纳工作流规则，不收录个案坐标、答案或第三方课件图。

## English

An explicit local-only run can complete its requested local scope while full_delivery_complete remains false. Resume the sealed checkpoint with the same pinned skill version; do not repeat refinement to obtain reports. The commands above require existing upload authorization. Perform report-qa and final customer export afterwards. Remaining A/B or layout findings require review, not a fabricated pass. A changed model needs fresh refinement and exact-CIF validation. Recover an uncertain existing submission instead of repeating it.

The EXTI scalar is refined; changing its value alone no longer counts as changing the model. Its presence, validity and the existing coordinate/population/ADP safeguards are retained. Four-character multi-H parent labels require naming review before HFIX; native outputs are checked for duplicate identities within each residue, including punctuation labels. PART does not provide a separate name space. Report QA uses the recorded basename and still verifies the exact CIF hash. HKL+JSON initialization remains an explicit, evidence-recorded route rather than a one-command automatic intake. None of these workflow checks establishes a correct crystal structure.
