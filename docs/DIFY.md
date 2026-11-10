# Dify 后端：结构、启动与验收

2026-11-09。此文是仓库的后端实施说明；前期 `dify-migration-plan.md` 的部署举例以本文为准。

## 1. 当前交付与边界

| 层 | 入口 | 责任 |
| --- | --- | --- |
| 业务 API | `backend/app/main.py`，新实例端口 8010 | 上传、确认、会话隔离、状态存储、报告导出；选择 Dify / 旧云接口 |
| Dify 客户端 | `backend/app/services/dify.py` | Workflow Service API、应用密钥、超时、响应校验；不自动重试付费运行 |
| Dify 业务适配 | `backend/app/services/dify_business.py` | 百分制与星级转换、原文校验、岗位规则约束、评分权重 |
| 工作流 | `dify/workflows/*.yml`，由 `scripts/build_dify_workflows.py` 生成 | 调用次序、评审与一次修订、节点日志 |
| Agent 工具服务 | `backend/app/agent_api.py`，端口 8091 | DeepSeek／千问／Ark 供应商调用、任务契约、OCR、媒体任务 |
| 任务契约 | `backend/app/services/agent_contracts.py` | 五维评分、证据、复核、报告、媒体输入模型 |

本版本使用 Dify 的 HTTP 与 Code 节点编排本机 Agent 工具，**没有第二套 LangGraph 调度循环**。供应商凭据由工具服务从 Co-Worker 的 SQLite 以只读方式取用，或从管理员环境变量取用；提示词及 JSON Schema 在工具服务中版本化。Dify 保存工具 Bearer token，各应用 API Key 存 `.private/dify/app-keys.json`。这与前期方案中“所有供应商 Key／提示词直接存 Dify”不同，目的是先复用本机已验证配置，避免依赖未安装的供应商插件。

```mermaid
flowchart LR
  UI[现有网页] --> BFF[业务 API · 8010]
  BFF --> Dify[Dify 工作流 · 8088]
  Dify --> Tools[Agent 工具 · 8091]
  Tools --> DS[DeepSeek · 打分与复核]
  Tools --> Qwen[千问 · 报告与问答]
  Tools --> Ark[豆包 · 图片与视频]
  BFF --> Store[本地文件与 SQLite]
```

当前代码默认 `AI_BACKEND=legacy`，旧入口可继续用。只有显式设置 `AI_BACKEND=dify` 的实例使用新工作流。**Dify 模式不会在故障时偷偷改走旧模型。** 合成演示仍明确使用本地预置数据和规则。

## 2. Agent 与工作流

| 工作流 ID | 节点顺序 | 输出 |
| --- | --- | --- |
| `profile` | 千问结构化 | education / skills / experiences / projects / preferences / warnings |
| `analysis` | DeepSeek 评分 → DeepSeek 复核 → 通过则原样返回，否则修订一次 | 5 个不同维度；每维 0–100，非零分必须有逐字证据 |
| `match` | DeepSeek 多维比较 | 每个输入岗位恰好一项；技能、学历、偏好各 0–100 |
| `report` | 千问报告 → DeepSeek 评审 → 通过则返回，否则千问修订一次 | strengths / must_fix / optional_improve / ats_keywords / checklist |
| `questions` | 千问出题 | 4–6 题与关键词 |
| `evaluate` | DeepSeek 评分与具体反馈 | score 1–5 / feedback |
| `summary` | 千问复盘 | summary 数组 |
| `chat` | 千问职业咨询 | reply；仅接收本次传入的聊天上下文 |
| `ocr` | 千问视觉识别 | text |
| `media_create` | 豆包图片／视频创建 | 任务 ID、状态、结果 URL |
| `media_status` | 豆包视频查询 | queued / running / succeeded / failed |

评分表示材料证据和岗位要求的对应程度，不是能力测验或录用概率。五维星级 = 百分分数 ÷ 20；岗位总分 = 65% 技能 + 20% 学历 + 15% 偏好。学历、城市的已知硬约束仍由业务规则保留，模型不能越过约束把“不满足”改成“满足”。

职业推荐目前是**本地55条目录规则召回10条，再由 DeepSeek 重排**；`dify/knowledge/` 是带来源的可选知识库导入材料，未启用向量检索或嵌入收费。不得将当前实现描述成全库语义检索。内容与使用边界见 `CHINA_CAREER_SOURCES.md`。

## 3. 本机部署

Dify 固定为官方 **1.19.0**，采用其完整 Docker 目录和 Compose 配置。官方要求 Compose **2.35.0+**；不能只复制一个 YAML，因为它还引用 `envs/`、Nginx 和代理模板。源码由 GitHub API 下载，版本和 commit SHA 记录在 `.private/dify/version.json`。本机 Docker Hub 连接被重置，实际通过 `docker.m.daocloud.io` 拉取同名同版本镜像并重新标记为 Compose 中的原始标签；镜像 ID 和仓库摘要保存在 `.private/dify/image-provenance.json`。记录摘要不等于已经用独立可信渠道验证镜像签名。

实际安装：Ubuntu 26.04 x86_64，Docker Engine **29.1.3**、Compose **2.40.3**；管理员通过系统认证窗口授权安装，Docker 服务已设为开机启动，当前用户已加入 docker 组。13个必需容器正在运行，API、PostgreSQL、Redis和代码Sandbox健康检查通过。独立Agent本地沙箱及其代理未启用。安装后根分区约剩 **2.1GiB**，不适合继续保存大量媒体；未擅自删除用户文件，长期使用前需要释放或扩充存储。

### 3.1 安装 Docker（本机管理员终端）

```bash
cd '/home/w-ubuntu/桌面/AI game'
sudo bash dify/install-docker.sh
sudo docker compose version
```

安装脚本优先使用现有Ubuntu软件源的 `docker.io` 和 `docker-compose-v2`；本机实际从清华镜像下载安装。仅在发行版无对应包时回退阿里云Docker CE源。没有覆盖主机软件源或daemon.json。当前会话若尚未刷新附加组，`dify/compose.sh` 会通过 `sg docker` 执行；重新登录后可直接访问Docker。

### 3.2 准备并拉起 Dify

```bash
python3 scripts/prepare_dify.py prepare
sudo bash dify/compose.sh config --quiet
bash dify/compose.sh up -d --pull never api worker worker_beat api_websocket web nginx db_postgres redis sandbox ssrf_proxy plugin_daemon agent_backend weaviate
bash dify/compose.sh ps
```

以上命令复用本机已缓存镜像；在新主机需先拉取镜像。控制台只发布 `127.0.0.1:8088`，HTTPS备用端口8448，尚未配置HTTPS证书。插件调试端口不向宿主机发布。源文件及卷位于 `.runtime/dify/docker/`，凭据位于 `.private/dify/`；均被Git忽略。首次生成随机数据库、Redis、插件和Sandbox凭据；`SANDBOX_API_KEY` 与 `CODE_EXECUTION_API_KEY` 必须一致，已在真机修正并验通。

管理员已初始化，账号 `admin@careerpilot.local`；随机密码只保存在 `.private/dify/admin.json`，未输出或提交。打开 `http://127.0.0.1:8088/signin` 登录。本机工具地址为 `http://host.docker.internal:8091`；代理仅为该域名允许私网访问，不关闭整套SSRF防护。

### 3.3 启动工具与业务服务

```bash
bash dify/services.sh install
bash dify/services.sh status
curl http://127.0.0.1:8010/api/v1/orchestration
```

已安装并启用持久systemd用户服务，在用户登录后自动启动，不依赖当前shell。未启用linger，不承诺无人登录时业务API自动运行。Docker容器使用restart策略自动恢复。业务API监听127.0.0.1:8010，工具绑定Docker桥接地址172.17.0.1:8091，不占用Co-Worker的8000。普通 start/stop/status 可继续管理服务。

### 3.4 导入工作流并发布

可在 Dify 控制台逐个导入 `dify/workflows/*.yml`（文件采用 JSON 语法，兼容 YAML），填写环境变量 `AGENT_TOOLS_TOKEN`（从私有 `tools.env` 读取）并发布，复制每个应用密钥到 `.private/dify/app-keys.json`。空结构模板见 `dify/app-keys.example.json`。

也提供批量辅助脚本。先在私有文件 `.private/dify/console-session.json` 中保存当前管理员的 Cookie 与 CSRF，格式 `{"cookie":"<完整Cookie>","csrf_token":"<当前CSRF>"}`，权限设600，然后：

```bash
python3 scripts/import_dify_workflows.py --session-file .private/dify/console-session.json
```

`scripts/bootstrap_dify_console.py` 已实测完成首次初始化和登录，把会话私有保存，随后上述批量脚本实际导入发布全部11个应用并保存应用密钥。已有已配置应用跳过；导入出现版本确认或依赖错误时停止。`apps.json` 保存应用ID，`app-keys.json` 保存调用密钥。临时控制台会话文件用完删除；需要再操作时可重新执行bootstrap登录脚本。

## 4. 密钥和媒体

`CO_WORKER_DB_PATH` 默认指向现有 Co-Worker `chat.db`，只读查询配置表，不读取或迁移聊天内容，不改该数据库。显式环境变量 `DASHSCOPE_API_KEY` / `DEEPSEEK_API_KEY` / `ARK_API_KEY` 优先。Dify 模式的网页 `/model/configure` 返回409，供应商凭据不能通过普通业务接口更新。

### 百炼单Key实测（2026-11-09）

| 任务／型号 | 同一百炼Key实测 |
| --- | --- |
| DeepSeek `deepseek-v4.1-flash`，五维打分及引文校验 | HTTP200，通过 |
| 千问 `qwen-flash`，诊断报告结构验证 | HTTP200，通过 |
| 豆包文本 `doubao-seed-2-1-lite-260915` | HTTP404，`model_not_found` |
| Seedream `doubao-seedream-5-0-flash-260915` | 百炼生图入口HTTP400，`InvalidParameter`，未接受生成 |
| Seedance `doubao-seedance-2-0-fast-260128` | 百炼视频入口HTTP400，`InvalidParameter`，未创建任务 |

百炼 `/models` 返回182个型号，包含DeepSeek与千问，不包含doubao／seedream／seedance。因此不能承诺此账号能够用一把百炼Key完成原来三家全部能力，也不把通义生图／通义视频冒充豆包。当前工具服务私有配置启用了 `DEEPSEEK_PROVIDER=bailian` 和 `BAILIAN_DEEPSEEK_MODEL=deepseek-v4.1-flash`，DeepSeek与千问实际共用百炼凭据和接口；Ark仍保留独立Key，媒体关闭。源码默认official，管理员可显式切换。

复测：`PYTHONPATH=backend .venv/bin/python scripts/check_bailian_single_key.py`；可选 `--probe-media` 额外提交一条图片和视频探测（若将来接入成功会产生费用）。模型目录只能说明可列出，不代替真实权限与任务验证。完整结果保存在 `.private/dify/bailian-single-key-check.json`。

媒体默认关闭，需要管理员设置 `MEDIA_ENABLED=true` 以及有权限的 `ARK_IMAGE_MODEL` / `ARK_VIDEO_MODEL`，然后重启工具和8010业务服务。当前已有 Ark 文本模型不能当成视频模型使用。目录中存在模型并不能证明生成权限。

POST `/api/v1/media` 接收 `kind`、`prompt`、`consent:true`、16–64位 `request_id`；相同会话和request_id返回已有任务，相同request_id但内容变化返回409。GET `/api/v1/media/{task_id}` 只查询当前会话任务。图片同步完成，视频异步查询。提交超时会记录为 unknown；未知任务不自动重新收费提交。此版本单工具进程；多实例前需将去重锁迁到共享数据库或队列。

生成结果为供应商临时URL，尚未实现永久资产归档或自动续期。显式同意必须由调用方提供；当前没有改前端媒体入口。

## 5. 数据、日志和恢复

- 简历原始文件在本地，解析后的文本会进入本机 Dify 和模型供应商；扫描OCR会把页面图像经 Dify 传给千问。不能承诺“数据不出本机”。Dify 运行日志可能保存输入、引文和输出，需按实际使用设置保留期。
- 默认不会在异常中回显供应商错误正文、Key 或模型原始无效结果。业务接口与工具接口都校验输出。
- `journalctl --user -u careerpilot-agent-tools -u careerpilot-dify-api` 查看本机服务；`sudo bash dify/compose.sh logs --tail 100` 查看容器。
- 画像重新确认、岗位重新导入会清除相应缓存。面试评分成功但总结失败时先保存回答，`POST /interviews/{id}/summary` 可独立重试总结，避免丢失回答再收费评分。
- 停服备份 `.runtime/dify/docker/volumes`、Dify `.env`、`.private/dify`、`backend/storage`；数据库和文件须保持一致。恢复前不能重新生成原部署密钥。
- 回退运行旧业务入口，保持 `AI_BACKEND=legacy`。Dify 尚未就绪时，不修改当前网站的默认启动方式。前端后续只需把内部代理指向8010，并通过 `/orchestration` 展示后端能力。

## 6. 验收状态

| 项目 | 结果 |
| --- | --- |
| DeepSeek 实际短JSON调用 | 通过，使用Co-Worker已存配置 |
| DeepSeek 真实合成简历评分 → 复核 → 输出 | 通过：5个维度、复核通过、逐字引文验证通过 |
| 千问真实合成诊断 → DeepSeek评审 → 千问修订 | 通过：初稿收到修改意见，修订后5个报告字段均通过格式验证；未进行第二次人工内容验收 |
| 千问 实际短JSON调用 | 通过，使用Co-Worker已存配置 |
| Ark 模型目录读取 | 通过；未执行生图／视频，不能算生成验通 |
| 模拟 Dify 完整求职闭环 | 通过：上传、确认、五维、岗位、诊断、面试、总结、导出 |
| 错误脱敏、不自动重试、原文校验、会话隔离、媒体去重 | 自动测试通过 |
| 原有 smoke / 职业来源 / 报告检查 | 通过 |
| 官方 Compose 与本地覆盖配置解析 | 通过，Compose v5.7.0独立二进制验证；选中16个服务、入口仅绑定127.0.0.1 |
| Dify Docker实际启动、DSL实际导入、跨容器工具访问 | 通过：13个服务、11个应用、本机工具HTTP连接 |
| 三家独立接口，经真实Dify完整闭环 | 通过，合成DOCX上传→画像→五维→匹配→报告→4轮面试→总结→导出→跨浏览器隔离 |
| 百炼单Key，DeepSeek＋千问，经真实Dify完整闭环 | 通过，同上全链路，43秒；没有降级旧接口 |
| 同一百炼Key调用豆包文本／Seedream／Seedance | 未通过，见上表；未生成媒体 |

2026-11-10更新：3000工作台已接8010，生产前端、业务API、Agent工具均由systemd用户服务启用。`/orchestration` 返回11个工作流状态和分类型媒体能力。前端在Dify模式不显示Key表单，支持可折叠工作记录、资料核对、文档式报告、面试复盘重试。旧直连模式仍可显式选择，默认工作台不使用Co-Worker的8000端口。

豆包独立Ark通道也完成了实测：`doubao-seedream-5-0-flash-260915` 图片返回HTTP429／`SetLimitExceeded`，`doubao-seedance-1-0-pro-fast-251015` 视频返回HTTP403／`AccessDenied`，均未接受任务。不是百炼单Key问题的替代成功结果。媒体已恢复关闭，保留模型ID便于管理员修正额度／权限后开启，前端不会提交关闭状态的任务。

检查命令：`make smoke`；部署预检：`python3 scripts/prepare_dify.py doctor`；完整真实Dify闭环：`.venv/bin/python scripts/check_dify_live.py`。真实测试均可能调用模型计费，结果写入`.private/dify/live-check.json`，使用合成资料，不提交测试隐私内容。

最终工作台结构与页面接口见 `FRONTEND.md`，当前验收与清理结果见 `DELIVERY.md`。生产网页3000与浏览器回归3005／8020隔离，测试使用`.next-test`，不覆盖生产构建。
