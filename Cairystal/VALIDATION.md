# 验证范围 / Validation scope

本次修改是交付状态同步，不改写晶体学计算、官方验证或报表生成算法。中英文各执行完整离线回归，精确数量与结果见仓库 docs/validation.json；测试数不等于晶体数。

实际测试使用一份本次比较实验中刚交付的真实数据包：原顶层 needs_attention / chemical_graph_required，子流程及四类交付已完成。执行 sync-delivery → resume → status → resume，均返回 complete；774 个子流程文件与17个交付文件逐字节不变，包括最终 CIF、3页 IUCr 官网 PDF、各6页中英文 Word。状态修复期间禁止启动外部程序和网络；没有重新解结构、精修、上传或渲染。

新增负面测试覆盖缺失 PDF、Word 被改动、错误样本 HKL、交付未复核、运行锁、错误导出回执等；重复导出到 Cairystal/运行_时间 的目录同样支持。科学质量判断并未因任务完成而被自动改为已确认。

Earlier native-continuation changes retain the tested same-specimen route from a reviewed native candidate without replaying solution or graph matching. The previously completed real package is evidence of delivery/state consistency, not a new independent blind solve, structural-accuracy benchmark, token measurement or cross-agent/host certification. Experimental data, structures and reports are retained locally, not published. Old versions remain available.
