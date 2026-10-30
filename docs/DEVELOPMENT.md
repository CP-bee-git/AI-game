# 开发者使用说明

技术栈：Next.js 16 / React 19、FastAPI / Python 3.12+、SQLite；Node.js 24、pnpm 11。单实例、单 API 进程。

页面样式集中在 `frontend/app/globals.css`：画布 `#F7F7F8`、正文与辅助文字统一为黑色 `#000000`，蓝紫 `#59558F` 用于按钮、选中状态和图表。标题 400、区块标题 500，通过字号、字重和留白区分信息层级；数字随正文使用比例字形，只有 API Key 等代码字段使用等宽字体。

网页字体通过 `next/font/local` 随站点提供，字形源自 IBM Plex Sans SC，保留 400 / 500 两种字重，界面小字库预加载，GB2312 补充字库按需加载；缺字回退到系统中文字体。子集重命名为 CareerPilot Sans / UI，来源、版本与 OFL 许可见 `frontend/app/fonts/`，无需访问外部字体服务。桌面使用侧栏与双栏工作区，900px 以下导航移至顶部，620px 以下内容单列；步骤读取真实会话状态，长说明默认收起。

## 启动与发布

```bash
./start.sh --setup-only      # 安装依赖
./start.sh                   # 构建并后台启动 http://127.0.0.1:3000
./start.sh --public          # 使用私有 .env 中 CPOLAR_AUTHTOKEN 开启免费隧道
make stop                   # 停止本项目进程
```

网页展开「千问连接设置」填写**百炼通用 API Key**，默认 `qwen-plus`。中国内地/新加坡的 Key 与地域必须一致；AccessKey ID、账号密码、Coding/Token 专属 Key 不能用于通用接口。Key 只留在当前浏览器对应的服务端内存，8 小时会话、重启清除；不写入业务数据库。

连接后即可使用「直接聊天」，无需上传或确认简历。对话仅保留在页面内存，刷新或清空后移除；每次调用携带最多 10 轮上下文、总计 24,000 字符，不自动附带简历或岗位数据。

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

职业库快照和来源在 `backend/app/data/occupations.json`；中文名及关键词映射由项目维护，职业代码和原文保留。匹配为资料规则覆盖，非实时招聘、非中国职业资格认定；星级为证据完整度，不是能力测评。更新快照时必须保留来源、版本和许可，并运行职业库检查。

报告模板在 `backend/app/services/exporter.py`，HTML 自包含、带星图，浏览器可打印为 PDF。上传与结果保存在 `backend/storage/`；`.env`、`.runtime`、`.private` 均禁止提交。当前尚无自动删除/保留期管理。
