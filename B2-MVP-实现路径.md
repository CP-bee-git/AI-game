# B2 精准就业匹配与求职辅助：第一版实现路径

## 1. 版本目标

第一版只实现候选人端的完整闭环：

```text
上传简历 -> 解析能力画像 -> 用户确认 -> 导入 10-20 个岗位
-> 匹配排序与解释 -> 岗位化简历诊断
-> 文本模拟面试 -> 导出报告
```

第一版暂不包含语音面试、辅导员工作台、自动投递和就业材料真伪核验。材料核验属于后续版本，避免在没有权威数据源时产生不当的真实性结论。

## 2. 系统结构

```text
Next.js/React 前端
        |
        | HTTPS + JWT/Session
        v
FastAPI API
        |
        +-- PostgreSQL + pgvector  (用户、画像、岗位、匹配结果)
        +-- Object Storage         (原始简历和导出文件)
        +-- Redis + Worker          (OCR、Embedding、报告等异步任务)
        +-- LLM Adapter            (Qwen/DeepSeek)
        +-- OCR/Document Adapter   (PaddleOCR、PDF/DOCX 解析)
```

智能体采用可审计的状态机或 LangGraph 工作流。LLM 负责信息抽取、解释和生成；硬条件判断、匹配分数、状态转换和权限检查由后端代码完成。

## 3. 分阶段实施

### S0：基础设施和工程骨架

目标是先让前后端、数据库和异步任务能稳定运行。

实现内容：

- 创建 Next.js 前端和 FastAPI 后端。
- 使用 Docker Compose 启动 PostgreSQL、pgvector、Redis 和 MinIO。
- 增加统一配置：`DATABASE_URL`、`REDIS_URL`、`OBJECT_STORAGE_URL`、`LLM_BASE_URL`、`LLM_API_KEY`。
- 建立统一响应格式：`data`、`error`、`request_id`。
- 建立登录、用户归属检查和基础审计日志。
- 建立 `LLMProvider`、`EmbeddingProvider`、`OCRProvider` 接口，避免业务代码绑定某个模型厂商。

完成标准：用户可以登录，服务可以健康检查，文件可以上传到私有对象存储，后台任务可以提交、重试并记录状态。

### S1：简历上传、解析和 OCR

核心接口：

```text
POST /api/v1/resumes/upload
GET  /api/v1/resumes/{id}/status
GET  /api/v1/resumes/{id}/blocks
```

处理流程：

1. 前端校验扩展名和大小，后端检查 MIME 和文件头。
2. 文件上传到私有对象存储，数据库只保存 `object_key`。
3. PDF 使用 PyMuPDF 提取文本；扫描版 PDF 转图片后使用 PaddleOCR。
4. DOCX 使用 `python-docx` 提取段落和表格。
5. 按页、段落和区域保存 `ResumeBlock`，记录来源位置和 OCR 置信度。
6. 低置信度字段在前端显示“请复核”。

建议状态：

```text
created -> uploaded -> scanning -> extracting -> parsed
                              \-> failed -> retry
```

### S2：能力画像和用户确认

LLM 接收提取出的文本块，使用 JSON Schema 生成画像草稿。每个技能、经历和证书都必须附带原文证据：

```json
{
  "name": "Python",
  "normalized_name": "Python",
  "level": "熟练",
  "evidence": {
    "block_id": "page_1_block_3",
    "quote": "使用 Python 完成数据分析项目"
  },
  "confidence": 0.91
}
```

主要字段：

- 教育经历
- 技能和技能熟练度
- 工作经历
- 项目经历
- 证书和语言能力
- 城市、行业、薪资和到岗偏好

核心接口：

```text
GET   /api/v1/profiles/{id}
PATCH /api/v1/profiles/{id}
POST  /api/v1/profiles/{id}/confirm
```

用户确认后生成不可变的 `profile_version`。后续匹配和诊断都绑定具体版本，用户修改画像后可以重新计算，不覆盖历史结果。

### S3：岗位 JD 导入和结构化

支持粘贴文本、上传文件和 CSV 批量导入。

核心接口：

```text
POST /api/v1/jobsets
POST /api/v1/jobsets/{id}/jobs/import
GET  /api/v1/jobsets/{id}
```

岗位结构至少包括：

```text
岗位名称、公司、地点、学历要求、经验要求、薪资、
必需技能、加分技能、岗位职责、语言要求、其他硬约束
```

岗位解析失败时只标记该岗位失败，其他岗位继续处理。10-20 个岗位全部解析完成后，生成 Embedding 并进入 `ready` 状态。

### S4：匹配、排序和解释

匹配流程固定为：

```text
解析硬约束
 -> 硬约束检查
 -> 技能标准化
 -> Embedding 相似度
 -> 关键词/规则匹配
 -> Reranker 重排
 -> 确定性加权评分
 -> LLM 生成解释
```

建议的初始评分：

```text
技能覆盖度       40%
语义相似度       25%
经历证据强度     15%
教育与经验匹配   10%
用户偏好匹配     10%
```

硬条件不满足的岗位仍然可以展示，但必须分组到“存在硬条件风险”，并明确显示原因。评分结果必须保存分项分、算法版本、证据片段和能力缺口。

核心接口：

```text
POST /api/v1/matches/run
GET  /api/v1/matches?jobset_id={id}
GET  /api/v1/matches/{id}
```

LLM 只能根据已计算的结构化结果生成解释，不能修改分数、添加简历中不存在的技能或改变排序。

### S5：简历诊断和导出

诊断分为规则检查和 LLM 建议两部分。

规则检查：

- 岗位关键词覆盖情况
- 项目是否包含职责和结果
- 是否存在过于空泛的表述
- 是否存在明显缺少的岗位要求
- ATS 是否能正确识别简历结构
- 内容是否与目标岗位相关

LLM 输出结构化建议：问题位置、问题严重程度、修改原因、建议文本、引用的简历证据和是否需要用户确认。没有数据时输出“待补充”，不能编造数字、经历和证书。

接口：

```text
POST /api/v1/reports
GET  /api/v1/reports/{id}
GET  /api/v1/reports/{id}/download
```

报告先保存为 JSON，再渲染为 HTML 和 PDF。导出文件使用短期签名链接。

### S6：文本模拟面试

面试会话状态：

```text
created -> question_ready -> awaiting_answer -> evaluating
         -> followup_or_next -> completed -> exported
```

面试计划绑定当前岗位和画像版本，建议每次生成 5-8 道题，包含自我介绍、项目深挖、技术问题、行为问题和岗位动机。

每次回答后按以下维度评分：

- 相关性
- 结构完整性
- 事实和项目证据
- 技术准确性
- 表达清晰度

核心接口：

```text
POST /api/v1/interviews
POST /api/v1/interviews/{id}/answer
POST /api/v1/interviews/{id}/finish
GET  /api/v1/interviews/{id}/feedback
```

面试评估结果必须是结构化 JSON，并保存模型版本和提示词版本，方便复现。

## 4. 核心数据表

```text
User
Resume
ResumeBlock
CandidateProfile
ProfileVersion
JobSet
Job
JobRequirement
MatchResult
DiagnosticReport
InterviewSession
InterviewTurn
ExportArtifact
ProcessingTask
AuditEvent
```

所有业务表至少包含 `id`、`owner_id`、`created_at`、`updated_at`。匹配结果还要包含 `algorithm_version`，报告和面试结果要包含 `model_version`、`prompt_version`。

## 5. 模型调用方式

第一版使用 Qwen 或 DeepSeek 的 OpenAI 兼容接口，所有调用统一经过适配层：

```python
class LLMProvider:
    def generate_json(self, schema, messages, model, temperature=0): ...
    def embed(self, texts, model): ...
    def rerank(self, query, documents, model): ...
```

推荐配置：

- 中文结构化抽取：Qwen Instruct 系列
- 复杂诊断：DeepSeek 系列，可异步调用
- Embedding：BGE-M3 或 Qwen Embedding
- Reranker：BGE Reranker 或 Qwen Reranker
- OCR：PaddleOCR

先建立脱敏样本集和调用日志，再考虑 LoRA 微调。第一版不从头训练基础模型。

## 6. 验收和测试

准备至少 10 份脱敏简历和 20-50 个岗位，建立人工标注结果。

主要验收项：

- 简历能完成 PDF、DOCX、图片三类输入。
- 能生成可编辑、可追溯的能力画像。
- 能导入 10-20 个岗位并输出排序。
- 每个排序结果都有分项分、证据和缺口。
- 诊断报告没有虚构经历或数字。
- 模拟面试可以完成多轮问答和评分。
- 报告可以导出为 PDF。
- 失败任务可以单独重试。

评测指标：

```text
抽取字段 Precision / Recall / F1
岗位匹配 Recall@5、NDCG@10
硬条件误放率
证据引用准确率
诊断报告人工评分
面试评分与人工评分的一致性
OCR 字段准确率
```

## 7. 公网部署顺序

开发环境使用 Docker Compose。测试环境部署前端、API、Worker、PostgreSQL、Redis 和对象存储。生产环境使用云服务器或容器服务，并配置：

- HTTPS 和自定义域名
- 私有对象存储和短期签名链接
- 登录、权限、限流和配额
- 文件类型检查和恶意文件扫描
- PII 加密、删除接口和审计日志
- 前端、API、数据库分离
- `staging` 与 `production` 两套环境变量

域名后续再绑定，不应把任何 `localhost` 地址写入业务代码。

## 8. 建议的执行顺序

```text
第 1 阶段：项目骨架、数据库、对象存储、模型适配层
第 2 阶段：简历上传、OCR、文档解析、画像确认
第 3 阶段：JD 导入、Embedding、匹配评分和解释
第 4 阶段：简历诊断、HTML/PDF 导出
第 5 阶段：文本模拟面试和反馈报告
第 6 阶段：样本评测、安全处理和公网部署
```

最终演示脚本固定为：上传简历、确认画像、导入岗位、查看 Top 5 匹配、打开一个诊断报告、完成一轮模拟面试、下载诊断和面试报告。
