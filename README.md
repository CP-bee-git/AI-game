# CareerPilot B2 MVP

第一版实现 B2 的候选人端闭环：上传简历、生成能力画像、导入岗位、匹配排序、简历诊断、文本模拟面试和报告导出。

## 目录

```text
backend/       FastAPI API、文件存储、模型适配层
frontend/      Next.js 操作界面
docker-compose.yml  PostgreSQL/pgvector、Redis、MinIO
B2-MVP-实现路径.md  产品和工程实现路径
```

## 开发启动

1. 安装 Node 24、pnpm 和 Python 3.12。
2. 复制 `.env.example` 为 `.env`，按实际环境修改。
3. 创建后端环境并安装依赖：

   ```bash
   python3.12 -m venv .venv
   .venv/bin/pip install -e backend
   ```

4. 安装前端依赖并启动：

   ```bash
   pnpm --dir frontend install
   make dev-api
   make dev-web
   ```

5. 打开 `http://localhost:3000`，API 文档在 `http://localhost:8000/docs`。

第一轮闭环烟测：

```bash
make smoke
```

烟测使用模拟模型返回，不消耗云端额度，覆盖上传、画像、确认、岗位导入、匹配、诊断、面试和导出。

没有 Docker 时，API 可以使用 `STORAGE_BACKEND=local` 启动；PostgreSQL、Redis 和 MinIO 的 Compose 配置已经预留，接入持久化任务时再启动。

## 云端模型接入

后端使用 OpenAI-compatible client，默认配置为通义千问云端接口。复制 `.env.example` 后填写 API Key：

```dotenv
MODEL_PROVIDER=qwen
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_API_KEY=你的云端 API Key
OPENAI_MODEL=qwen-plus
```

切换 DeepSeek 时只需修改：

```dotenv
MODEL_PROVIDER=deepseek
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-chat
```

模型密钥只放在后端环境变量，不提交到 Git。配置后可以调用 `POST /api/v1/model/ping` 检查云端接口。

## 当前 API 闭环

```text
POST /api/v1/resumes/upload
POST /api/v1/resumes/{resume_id}/profile
POST /api/v1/resumes/{resume_id}/profile/confirm
POST /api/v1/jobsets
POST /api/v1/jobsets/{jobset_id}/jobs/import
POST /api/v1/matches/run
POST /api/v1/reports/diagnosis
POST /api/v1/interviews
POST /api/v1/interviews/{session_id}/answer
```

当前岗位匹配使用可复现的技能覆盖、学历和城市偏好规则。Embedding 接口已经在模型配置中预留，接入供应商 Embedding 后再替换语义相似度部分。

## 后端持久化

PostgreSQL/pgvector 的 SQLAlchemy 模型位于 `backend/app/models.py`，初始化脚本为：

```bash
PYTHONPATH=backend .venv/bin/python backend/scripts/init_db.py
```

生产环境安装 `backend[production]` 后再执行；当前开发流程默认使用内存状态，重启 API 会清空演示数据。

## 需要你补充或确认

详见 [`docs/待你配置.md`](docs/待你配置.md)。没有 API Key 时，健康检查和文件上传仍可运行；配置云端模型后可以生成能力画像。

