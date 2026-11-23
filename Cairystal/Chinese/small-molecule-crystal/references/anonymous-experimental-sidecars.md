# 匿名实验元数据补充

盲测输入准备时可能故意只提供元素、晶胞和 HKL。不能将未带入求解端的实验参数视为原始采集数据缺失，也不能让求解端读取参考 CIF 寻找答案。需要补充时由独立数据准备端导出白名单 sidecar；原盲测输入不覆盖，补全后仍是同一开发集或任务的续跑。

`experimental_sidecar.py` schema 1 仅支持晶体外形、衍射仪型号、晶胞测定反射数、晶胞测定 theta min/max、晶胞测定温度、衍射采集温度这7个字段。每项保存合法 CIF raw_token、解析 value 和单位；按匿名 case_id 绑定 manifest、input.json 和原始 HKL 的 SHA256。来源只包含整份源文件与选定块的 opaque hash，不包含路径/块名、身份、分子式、空间群或模型内容。

```text
python scripts/experimental_sidecar.py --sidecar experimental_metadata.json --manifest INPUT_ROOT/manifest.json --input-root INPUT_ROOT --output NEW_METADATA_DIR
```

输出每例只有7字段的 `experimental_metadata.cif`（它不是结构 CIF）、兼容已有 `experiment_metadata_state.py collect` 的 `ledger_sources.json`，及 `temperature_plan.json`。验证拒绝额外字段、CIF token 注入、错误温标、输入串例/哈希变化和覆盖旧目录。不要把这个仅含元数据的 CIF 当作结构交付。

也可在 collect 配置的 sources 中使用 `kind: anonymous_sidecar`，同时明确 path/source_sha256/hkl_sha256/same_experiment_confirmed/basis/case_id/manifest/input_json；导入相同白名单并保留原始不确定度。其余 collect/synchronize/TEMP 门禁继续有效。

两个温度分别保留，存在小差别并非自动错误。TEMP 取已确认的衍射采集温度，摄氏值为 K−273.15；若当前 RES 缺少或不一致，保留旧模型，准备新 INS，核对 AFIX/HFIX、特殊位置氢及水氢限制，做必要的 SHELXL 续精修，再在新 CIF 中同步有证据的实验参数。不能只改 CIF 温度来消除 B196。其他字段冲突保留并记录依据，不以参考模型替代当前模型。

最终新旧验证对照应区分实验信息完整性与模型质量；官网报告对应确切最终 CIF，中英文 Word 重新生成。不得保证所有警告消失。未经授权，不扩大白名单、读取答案、公开原始数据或增加官网上传范围。
