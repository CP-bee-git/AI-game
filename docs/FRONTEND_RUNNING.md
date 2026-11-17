# 前端运行说明

更新：2026-11-17。项目目录：`/home/w-ubuntu/桌面/AI game`。页面定位为中国校招、社招的简历分析与中文面试训练。

## 本机访问

| 服务 | 地址 | 用途 |
| --- | --- | --- |
| 正式前端 | <http://127.0.0.1:3000> | 上传、核对、分析简历与练习面试 |
| 业务 API | <http://127.0.0.1:8010/docs> | 业务接口文档 |
| Dify 控制台 | <http://127.0.0.1:8088> | 工作流管理；依赖 Docker 正常运行 |

前端使用 Next.js 16 / React 19，运行需要 Node.js 24+、pnpm 11；后端需要 Python 3.12+。本机已有 Node 24.18.0、pnpm 11.22.0 和项目依赖，不需要重新安装。

## 进入项目并准备终端

```bash
cd '/home/w-ubuntu/桌面/AI game'
source "$HOME/.nvm/nvm.sh"
nvm use 24
node --version
pnpm --version
```

如果显示 `node: not found`，先执行上述 nvm 命令。本机服务通过 Node 的绝对路径启动，不受终端 PATH 是否加载影响。

## 启动已有部署

```bash
bash dify/services.sh start
bash dify/services.sh status
```

打开 <http://127.0.0.1:3000>。这会启动已安装的前端、业务 API 和模型工具用户服务；**不会修复或自动启动失败的 Docker 服务**。真实资料分析还需要 Docker、Dify 容器和服务端模型凭据可用。

新环境首次准备依赖、构建与安装用户服务时使用：

```bash
./start.sh --setup-only
./start.sh --dify
```

完整 Docker/Dify 初始化、工作流导入和凭据配置见 [DIFY.md](DIFY.md)。供应商 Key 与 Dify 应用 Key 只保存在服务端私有配置中，不填进前端代码或浏览器。

## 修改前端后的构建与重启

```bash
API_INTERNAL_URL=http://127.0.0.1:8010 pnpm --dir frontend build
systemctl --user restart careerpilot-web
```

Next.js 的 `/api/*` 转发目标在构建时确定；更换后端地址需要重新构建，仅在启动时改环境变量不够。新构建完成后重启正式前端，使进程加载对应版本。修改模型提示词后，还需重启相应后端服务：

```bash
systemctl --user restart careerpilot-agent-tools careerpilot-dify-api
```

本项目的领域提示词位于后端源码，Dify 工作流通过 HTTP 节点调用模型工具；只改提示词不需要重新导入工作流。

## 开发模式

已有正式前端占用 3000 时，在另一端口运行开发页：

```bash
API_INTERNAL_URL=http://127.0.0.1:8010 CAREERPILOT_TEST_BUILD=1 pnpm --dir frontend dev --hostname 127.0.0.1 --port 3006
```

访问 <http://127.0.0.1:3006>，按 `Ctrl+C` 停止。这里使用 `.next-test`，避免开发构建覆盖正式 `.next`。开发模式同样连接 8010，真实资料操作可能调用付费云模型；运行自动浏览器测试前先停止该开发进程，避免共用构建目录。

## 页面使用顺序

1. 点击「载入示例」，再点击「确认信息，查看匹配」，查看五维检查和 10 个职业参考。
2. 点击「开始匹配」，在岗位行点击「诊断」或「面试」。示例使用本地规则，不调用模型。
3. 测试真实资料时，先脱敏并确认数据处理说明，再上传 PDF、DOCX、PNG 或 JPG；核对并确认整理结果。
4. 导入目标岗位，生成分析、诊断和面试题；逐题提交回答，查看反馈和最终复盘，可导出 HTML/JSON。

页面显示「服务已配置」只说明密钥配置存在，不等于 Dify 和云模型实际可用；实际请求的结果才是判断依据。

## 测试和运行日志

```bash
make smoke
make e2e
make check
journalctl --user -u careerpilot-web -u careerpilot-dify-api -u careerpilot-agent-tools -n 80 --no-pager
```

`make e2e` 自动启动 3005 测试网页和 8020 隔离业务 API，使用 `.next-test` 与临时数据；测试时保持这两个端口空闲，不需要先手动启动测试服务。`make smoke` 与浏览器回归使用模拟云调用或本地合成数据，不证明真实模型链路可用。

可运行真实链路测试（使用合成简历，会消耗云模型额度）：

```bash
.venv/bin/python scripts/check_dify_live.py
```

## 2026-11-17 实测结果与故障恢复

- 正式前端 3000 与业务 API 8010 均返回 HTTP 200；页面标题已更新为「中国简历分析与面试训练」。
- 在正式 3000 页面完成合成示例操作：确认资料、五维分析与 10 个职业参考、10 岗位匹配、诊断和 6 轮面试复盘均通过；该流程为本地规则示例，不调用真实云模型。
- `make smoke` 通过：模拟云请求、业务闭环、职业库、报告与 7 项 Dify 契约检查。
- `make e2e` 通过：17/17，覆盖简历示例、岗位匹配、诊断、面试、导出、手机布局与错误重试。
- Docker/Dify 修复后，真实链路测试 18/18 通过，耗时约 49 秒：合成简历上传、千问抽取、确认、DeepSeek 五维评分与职业匹配、岗位比较、诊断写作与复核、HTML 导出、4 轮面试评分、复盘、JSON 导出和浏览器会话隔离。使用真实 Dify 与云模型，未提交媒体生成；验收记录保存在私有 `.private/dify/live-check.json`。
- 正式 3000 页面真实咨询通过：在浏览器输入合成校招场景，经前端代理、业务 API 与 Dify 返回回复；回复保留“使用Python完成1000条课程数据的清洗”，对未提供的操作和结果提出补充问题。两种调用模式统一复用 `backend/app/services/chat.py` 的领域及事实约束提示词；模型建议仍应由本人核对。
- Docker 启动崩溃已修复。`/var/lib/docker/network/files/local-kv.db` 检查发现 39 处结构错误；原文件先备份到 `/var/lib/docker/careerpilot-network-backup/20261117T033623498240Z/local-kv.db`，再从私有副本重建。重建保留全部 78 条可读取的逻辑记录，合并 14 次内容完全一致的重复引用；逻辑记录哈希一致且 bbolt 结构检查通过，Docker 29.1.3 已成功启动。恢复后按 Compose 定义补回 sandbox、api_websocket、plugin_daemon、weaviate 缺失的网络连接，并重新创建无网络连接的 web 容器；13 个服务均已运行，API、沙箱、PostgreSQL 与 Redis 健康。数据卷和 Dify 业务数据库保留。
- Next.js 已从 16.4.3 升级到 16.4.6，修复 `GHSA-mfr8-8qww-v76h`（受影响范围为 16.3.0–16.4.4）；`pnpm audit --prod --json` 当前报告 0 项漏洞，`make check` 与升级后 17/17 浏览器回归通过。正式前端已构建并重启，日志确认运行 16.4.6。

当 3000 能打开但真实分析失败时，先检查 Docker/Dify，而不是重复上传或更换网页 Key：

```bash
systemctl status docker --no-pager
journalctl -u docker -b -n 80 --no-pager
bash dify/compose.sh ps
```

Docker 恢复后，应等待 Dify API 完成启动迁移并进入 healthy 状态，再测试模型。本机系统与容器位于 USB 磁盘，冷启动时磁盘可能接近满负荷，迁移和 Python 服务初始化需要数分钟，期间 8088 可能返回 502；应结合容器状态和启动日志判断，避免反复重启打断初始化。工具服务若曾在 Docker 故障时启动，可能退回绑定 127.0.0.1，需重新启动，确认监听 Docker 桥接地址：

```bash
systemctl --user restart careerpilot-agent-tools careerpilot-dify-api
ss -ltnp '( sport = :8091 )'
docker exec docker-api-1 curl --max-time 10 -fsS http://127.0.0.1:5001/health
curl --max-time 10 -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8088/signin
```

本机工具地址为 `172.17.0.1:8091`；Dify API 容器内的 `/health` 与控制台 `/signin` 应返回 HTTP 200。不要用 `8088/health` 检查 API，该路径会转发到控制台网页。原始网络数据库备份和 `.private/dify/network-recovery/` 中的恢复记录应保留，以便后续核查；不要直接删除 Docker 数据目录或数据卷。

## 停止服务

```bash
bash dify/services.sh stop
```

这只停止本项目的三个用户服务，Dify 容器单独管理。不要用删除目录、清空 Docker 卷的方式停服，简历文件和数据库需要保留。
