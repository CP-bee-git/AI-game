# 工作台结构与接口交接

更新：2026-11-10。前端已接Dify业务API，3000代理到8010，供应商密钥不经过浏览器。

## 组件职责

| 文件 | 职责 |
| --- | --- |
| `app/page.tsx` | 本次简历／岗位／报告／面试状态与API编排 |
| `app/workspace-types.ts` | 服务能力、报告、面试响应契约 |
| `app/workspace-context.tsx` | 可折叠本次记录栏、键盘操作与展开状态 |
| `app/profile-review.tsx` | 教育／项目／实践／偏好核对，保留原始证据记录 |
| `app/report-view.tsx` | 诊断文档、页边关键词和投递检查、导出 |
| `app/interview-room.tsx` | 当前问题、回答、反馈时间线、独立复盘重试 |
| `app/chat-panel.tsx` | 有限上下文咨询、滚动跟随、错误后保留输入 |
| `app/media-studio.tsx` | 同意、稳定request_id、创建任务／查询／媒体展示 |
| `app/globals.css` | 基础控件和结果组件样式 |
| `app/workspace.css` | 最终设计规范、三栏布局、响应式、组件展示 |

## 连接策略

初始化先读取 `/model-config` 建立浏览器会话，然后读取健康与示例数据。`backend=dify` 时额外读取 `/orchestration` 并展示服务分工；不显示Key表单，不访问Dify管理接口。legacy模式保留原配置流程。

服务已配置仅表示应用密钥存在，不代表本次模型调用成功。等待、错误、结果均以实际业务请求为准。真实资料分析与合成规则示例有独立标签。工作流状态错误不会禁止用户体验本地规则示例。

## API增补

- `/model-config` 新增 `backend`（legacy / dify）。
- `/orchestration` 返回工作流布尔状态、Agent分工、媒体开关和image/video能力。
- 面试响应新增 `summary_pending`；`POST /interviews/{id}/summary` 单独重试总结，避免重评回答。
- `POST /media` 需要kind、prompt、consent=true、16–64位request_id；相同内容重试沿用request_id。
- `GET /media/{id}` 查询当前浏览器任务；公共响应不暴露供应商任务ID和输入指纹。

前端媒体能力开启后才允许输入和提交；超时／错误保留request_id，视频五秒查一次，查询失败放慢到十五秒。未开启只展示说明，不主动生成样例媒体。

## 排版与可访问性

暖白背景、深墨色正文、墨绿强调。正文14.5px，注释至少12px，主要标题22/30px；数值使用正文数字字体。宋体与Sans各有单独OFL说明，本地next/font加载，无外部字体服务。

报告用语义article/section/aside；访谈为form，禁用状态不会丢回答。侧栏折叠按钮有aria-expanded/controls，折叠不移动焦点。输入始终有label，通知使用status/alert。减弱动效时关闭动画和过渡。没有声称已运行Lighthouse或取得特定分数。

## 验证与运行

Playwright使用独立3005网页、8020业务服务和临时SQLite；测试输出在`.next-test`，生产输出在`.next`，不会互相覆盖。真实模型请求通过mock拦截，CI构建时显式设置测试代理，不复用本机Co-Worker 8000。

生产前端由 `careerpilot-web.service` 管理，Node绝对路径写在私有systemd配置；默认3000。构建后用 `bash dify/services.sh install` 同步服务定义，普通重启可用 `systemctl --user restart careerpilot-web`。
