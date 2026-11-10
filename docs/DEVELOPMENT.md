# 开发者使用说明

技术栈：Next.js 16 / React 19、FastAPI / Python 3.12+、SQLite；Node.js 24、pnpm 11。单实例、单 API 进程。

Dify 多模型升级的模块分工、部署与实际验收状态见 [DIFY.md](DIFY.md)。设置 `AI_BACKEND=dify` 后，业务接口只经 Dify 工作流调用本机 Agent 工具；未配置时返回明确错误，旧接口模式通过 `AI_BACKEND=legacy` 保留。

页面基础样式在 `frontend/app/globals.css`，最终工作台规范在 `frontend/app/workspace.css`：暖白画布、墨色正文、墨绿强调，主要文字14.5px、辅助文字12px、标题22/30px。衬线仅用于标题，数字保持Sans与等宽数字特性。组件和接口职责见 [FRONTEND.md](FRONTEND.md)。

网页字体通过 `next/font/local` 随站点提供，正文IBM Plex Sans SC，标题Noto Serif CJK SC，均保留400/500两种字重；许可与来源各自保存在 `frontend/app/fonts/`。桌面步骤栏、主工作区、可折叠上下文栏，900px以下变为上下排列，620px以下报告与面试单列。动效只在内容出现和用户操作时发生，减弱动效下全部关闭。

## 启动与发布

```bash
./start.sh --setup-only      # 安装依赖
./start.sh --dify            # 已配置本机Dify时，构建并启动3000/8010/8091
./start.sh --public          # 使用私有 .env 中 CPOLAR_AUTHTOKEN 开启免费隧道
make stop                   # 停止本项目进程
```

工作流模式由管理员维护服务端凭据，网页展示DeepSeek、千问和豆包的当前分工，不接收供应商Key。旧版可用 `./start.sh --legacy`，再在「千问连接设置」填写百炼通用Key；该模式的临时Key只保存在浏览器会话对应的服务器内存，不写入业务数据库。

连接后可直接聊天，无需简历。每次携带最多10轮上下文、24000字符，不自动附带简历或岗位。网页清空仅移除本页记录，Dify日志可能保留输入输出，不承诺服务端同时删除。

可选服务器默认值：复制 `.env.example` 为私有 `.env`，填写 `DASHSCOPE_API_KEY`、`QWEN_REGION`。公开演示建议默认 Key 留空，让用户在页面连接。

## 关键接口

| 接口（前缀 `/api/v1`） | 用途 |
| --- | --- |
| `POST /model/configure` | `{api_key, region, model}`，先验证非思考 JSON 能力，再保存 |
| `DELETE /model/configure` | 清除当前浏览器 Key |
| `POST /chat` | `{messages:[{role:"user"\|"assistant",content}]}` → `{reply}`；无需简历，必须以用户问题结束；单条最多 4,000 字符 |
| `POST /resumes/upload` | multipart 文件 + `privacy_acknowledged=true` |
| `POST /resumes/{id}/profile` | 云模型抽取；随后 `/profile/confirm` 人工确认 |
| `GET /resumes/{id}/analysis` | 五维星级、证据与 10 个职业匹配；必须已确认 |
| `POST /exports` | `{type:"profile"\|"diagnosis"\|"interview", resource_id, format:"html"\|"json"}` |

其余岗位导入、诊断、面试接口见 `http://127.0.0.1:8000/docs`。程序调用先 GET `/model-config` 建立 cookie，再始终复用 cookie；不支持跨浏览器读取私有资料。

## 验证与排错

```bash
make smoke                  # 云 HTTP 替身 + 业务闭环 + 会话隔离
make check                  # Python 编译 + TS + 生产构建
make e2e                    # 浏览器完整流程
.venv/bin/python backend/scripts/check_careers.py
.venv/bin/python backend/scripts/check_reports.py
.venv/bin/python backend/scripts/smoke_flow.py --real
```

`--real` 从私有 `.env` 读取 Key 做一次小额真实 JSON 请求，成功退出 0、调用失败 1、未配置 Key 2；不打印 Key。未填真实 Key 的模拟通过不代表真实账户可用。

新版工作空间 Key 可能包含句点，按完整 Bearer 凭证处理；不要删改其中的 `.`。

云错误返回 `{detail,error_code}`：401 鉴权/地域、402 账单/额度、403 权限、404 模型、422 Key 类型/参数、429 限流、503 网络/云服务、504 超时。`cloud_billing` / `Arrearage` 表示阿里云账户计费状态异常，需在「费用与成本」处理；不会通过重试或更改 Key 格式自动解除。配置失败保留旧 Key。日志在 `.runtime/logs/`，只按错误类别记录，不回显上游含密钥的正文。

职业库在 `backend/app/data/occupations.json`：55 个中国职业名称、代码与官方分类事实，经技能人才评价工作网逐条核对；场景说明、常见岗位称呼和关键词由项目独立编写。关键词等权，匹配仅说明技能对应，非官方能力评分、资格认定或实时招聘。更新时核对来源与记录哈希，再运行 `check_careers.py`；可用 `--verify-source` 向官方网页端点逐条复核（仅维护使用，端点不保证稳定），或 `--source-dir` 检查已下载的事实记录。不要给官方数据标注不存在的开放许可；详见 `docs/CHINA_CAREER_SOURCES.md`。

报告模板在 `backend/app/services/exporter.py`，HTML 自包含、带星图，浏览器可打印为 PDF。上传与结果保存在 `backend/storage/`；`.env`、`.runtime`、`.private` 均禁止提交。当前尚无自动删除/保留期管理。
