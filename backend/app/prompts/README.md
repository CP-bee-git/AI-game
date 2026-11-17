# 产品模型提示词

本目录的提示词对应服务端源码中使用的系统指令，与 JSON Schema、工具输入和后端校验一起生效。

| 文件 | 使用位置 | 用途 |
| --- | --- | --- |
| `domain.md` | 所有简历/场景节点 | 领域总则：事实/证据/通用方法/未知信息四类区分 |
| `resume_guidance.md` | `services/resume_docs.py` | 简历提升指南 |
| `resume_rewrite.md` | `services/resume_docs.py` | 段落润色对照 |
| `resume_draft.md` | `services/resume_docs.py` | 事实锁定简历草稿 |
| `scenario_evidence.md` | `services/scenarios.py` | 检索证据整理 |
| `scenario_strategy.md` | `services/scenarios.py` | 场景攻略生成 |
| `scenario_review.md` | `services/scenarios.py` | 事实与引用复核 |

约束：提示词不替代后端校验；`fact_id`/`source_id` 只能来自服务端提供的数据；外部要求与用户经历分开处理；未联网时明确标注"未联网核验"。
