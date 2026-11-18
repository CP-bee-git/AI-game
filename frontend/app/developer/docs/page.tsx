import Link from "next/link";
import { ArrowLeft } from "lucide-react";

const stateTables = [
  { name: "resume_blocks", content: "简历原文分块", key: "resume_id", note: "解析后的文本块，含 block_id / page，润色对照只引用这里的原文" },
  { name: "profiles", content: "能力画像", key: "resume_id", note: "确认后带 source_revision；改版后旧指南与草稿标记失效" },
  { name: "jobsets", content: "岗位清单", key: "jobset_id", note: "每次导入 1–20 条，字段见接口契约" },
  { name: "interviews", content: "面试会话", key: "session_id", note: "逐题回答、评分与复盘；跨会话读取返回 404" },
  { name: "reports", content: "诊断报告", key: "report_id", note: "千问写作、DeepSeek 评审后的结构化结果" },
  { name: "exports", content: "导出工件", key: "export_id", note: "HTML / JSON 内容快照，仅当前会话可取" },
  { name: "match_runs", content: "匹配运行", key: "resume_id:jobset_id", note: "画像确认或修改时自动作废重算" },
  { name: "consents", content: "隐私同意", key: "resume_id", note: "上传时的政策版本与时间" },
  { name: "analyses", content: "五维分析", key: "resume_id", note: "规则评分 + 职业参考缓存" },
  { name: "media", content: "媒体任务", key: "task_id", note: "职业影像（当前关闭）" },
  { name: "resume_guidance", content: "简历提升指南", key: "guidance_id", note: "记录 source_revision 与生成时间" },
  { name: "resume_drafts", content: "简历草稿", key: "draft_id", note: "分节内容、占位符清单、用户编辑" },
  { name: "scenario_runs", content: "场景攻略任务", key: "run_id", note: "request_id 去重指纹、状态机、来源与复核" },
];

const ruleTables = {
  matching: [
    ["技能匹配 skill_coverage", "必需技能命中 80% + 优先技能命中 20%", "25%"],
    ["经历相关 experience_relevance", "实习/工作经历 35 + 项目 20 + 职责与结果描述 20 + 技能有原文佐证 25", "25%"],
    ["学历 education_match", "达到岗位要求记 100，否则 0 并进入 hard_fail；画像写明 985/211/双一流时计入证据", "15%"],
    ["科研成果 research_output", "论文/学术发表 40 分 + 科研项目/课题 30 分 + 专利/软著 30 分，按画像原文识别", "15%"],
    ["奖项竞赛 awards_competition", "学生职务 30 分 + 竞赛层级（校级 40 / 省级 55 / 国家级·国际 70，取最高档）", "10%"],
    ["求职意向 preference_fit", "城市与求职偏好一致记 100，否则 0", "10%"],
  ],
  education: [
    ["高中", "1"], ["大专 / 专科", "2"], ["本科 / 学士", "3"], ["硕士 / 研究生", "4"], ["博士", "5"],
  ],
  careers: [
    ["技能对应", "60% × 已对应技能数 ÷ 用户技能数（至少 3 项为基数）"],
    ["证据广度", "40% × min(已对应技能数 ÷ 6, 1)"],
    ["星级", "规则分 ÷ 20 后四舍五入，最高 5 星；只表示资料对应程度"],
  ],
  interview: [
    ["回应岗位技能关键词", "+1 分（无关键词时默认给分）"],
    ["回答达到 80 字（背景 / 职责 / 结果）", "+1 分"],
    ["包含数量、比例或时间等可核对信息", "+1 分"],
    ["基础分", "2 分；总分封顶 5 分；云模型模式下由 DeepSeek 按四维评分"],
  ],
  facts: [
    ["事实编号 fact_id", "由服务端按 education / skills / experiences / projects 生成，模型不得自创"],
    ["原文核对", "润色的 original 必须逐字属于所选段落；fact_ids 必须属于当前版本"],
    ["版本失效", "画像重新确认后 source_revision 变化，旧指南 / 草稿提示重新生成"],
    ["引用核对", "攻略的 verified_facts 必须带工具返回的 source_id 与逐字片段，否则剔除"],
  ],
};

const endpoints = [
  ["POST", "/resumes/upload", "上传简历（需隐私同意）"],
  ["POST", "/resumes/{id}/profile", "生成画像（千问 / Dify）"],
  ["POST", "/resumes/{id}/profile/confirm", "确认画像并生成 source_revision"],
  ["GET", "/resumes/{id}/analysis", "五维分析 + 职业参考"],
  ["POST", "/matches/run", "岗位规则匹配"],
  ["POST", "/reports/diagnosis", "诊断报告（千问 + DeepSeek）"],
  ["POST", "/interviews", "创建面试（千问出题）"],
  ["POST", "/interviews/{id}/answer", "提交回答（DeepSeek 评分）"],
  ["POST", "/resume-guidance", "简历提升指南"],
  ["POST", "/resume-rewrites", "段落润色对照"],
  ["POST", "/resume-drafts", "事实锁定简历草稿"],
  ["PATCH", "/resume-drafts/{id}", "保存编辑（版本冲突检查）"],
  ["POST", "/scenario-runs", "创建场景攻略任务（202，request_id 去重）"],
  ["GET", "/scenario-runs/{id}", "查询状态 / 结果（仅当前会话）"],
  ["POST", "/exports", "导出 profile / diagnosis / interview / resume_draft / scenario"],
];

const agents = [
  ["千问 qwen-flash", "画像整理、报告写作、面试出题与复盘、指南 / 润色 / 草稿 / 攻略生成", "阿里云百炼"],
  ["DeepSeek v4.1-flash", "五维评分、岗位复核、回答评分、攻略事实复核", "同一百炼通道"],
  ["Qwen-VL", "图片与扫描件 OCR", "百炼多模态"],
  ["Tavily（可选）", "场景攻略的公开信息检索", "未配置时标注「未联网核验」"],
  ["豆包 Seedream / Seedance", "职业影像（当前关闭）", "独立 Ark 凭据"],
];

export default function DeveloperDocs() {
  return (
    <main className="privacy-page dev-docs">
      <Link href="/developer" className="privacy-back"><ArrowLeft size={15} />返回开发者工作台</Link>
      <h1>开发者查阅：数据与规则</h1>
      <p>本页汇总平台的数据存储、规则引擎与接口契约，便于开发者核对行为与排查问题。所有存储按浏览器会话隔离，跨会话读取返回 404。</p>

      <h2>数据库总览（SQLite · 单表命名空间）</h2>
      <p>所有业务状态保存在 <code>backend/storage/careerpilot.sqlite3</code> 的 <code>app_state</code> 表中，结构为 <code>(namespace, key, value)</code>，主键 <code>(namespace, key)</code>，实际键为 <code>命名空间:会话ID:键</code>。WAL 模式，单实例部署。</p>
      <div className="doc-table-wrap">
        <table className="doc-table">
          <thead><tr><th>命名空间</th><th>内容</th><th>主键</th><th>说明</th></tr></thead>
          <tbody>
            {stateTables.map((row) => (
              <tr key={row.name}><td><code>{row.name}</code></td><td>{row.content}</td><td><code>{row.key}</code></td><td>{row.note}</td></tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>规则引擎</h2>
      <p>以下规则在服务端代码中固定，不经过模型；模型输出必须通过这些校验才会被采用。</p>

      <h3>岗位匹配（services/matching.py）</h3>
      <div className="doc-table-wrap">
        <table className="doc-table">
          <thead><tr><th>维度</th><th>规则</th><th>权重</th></tr></thead>
          <tbody>{ruleTables.matching.map((row) => <tr key={row[0]}><td>{row[0]}</td><td>{row[1]}</td><td>{row[2]}</td></tr>)}</tbody>
        </table>
      </div>
      <p>总分 = 技能 × 25% + 经历 × 25% + 学历 × 15% + 科研 × 15% + 奖项 × 10% + 意向 × 10%，保留两位小数；每缺一项必需技能再折减 15 分（总分下限 25 分，借鉴 Rhed-Dev/resume-screening-toolkit 的 gate 折减设计），权重归一化思路借鉴 resume-screening-agent 的 rubric 设计。学历或城市不满足时 <code>eligible=false</code> 并列出原因。科研、奖项与经历维度只识别画像中明确写出的原文，不编造经历；没有相关经历时该维度计 0 分。Dify 链路下技能/学历/意向由 DeepSeek 评分，其余维度始终由规则引擎计算。</p>

      <h3>学历档位（EDUCATION_RANK）</h3>
      <div className="doc-table-wrap">
        <table className="doc-table doc-table-narrow">
          <thead><tr><th>学历关键词</th><th>档位</th></tr></thead>
          <tbody>{ruleTables.education.map((row) => <tr key={row[0]}><td>{row[0]}</td><td>{row[1]}</td></tr>)}</tbody>
        </table>
      </div>

      <h3>职业参考评分（services/careers.py）</h3>
      <div className="doc-table-wrap">
        <table className="doc-table">
          <thead><tr><th>构成</th><th>规则</th></tr></thead>
          <tbody>{ruleTables.careers.map((row) => <tr key={row[0]}><td>{row[0]}</td><td>{row[1]}</td></tr>)}</tbody>
        </table>
      </div>
      <p>技能同义词按固定别名表合并（如 Python3 → Python、JS → JavaScript），单字母技能不做模糊匹配；同分职业按领域轮换展示。数据来自本地 55 条中国职业条目（<code>backend/app/data/occupations.json</code>），不是实时招聘。</p>

      <h3>面试规则评分（services/interview.py）</h3>
      <div className="doc-table-wrap">
        <table className="doc-table">
          <thead><tr><th>检查项</th><th>计分</th></tr></thead>
          <tbody>{ruleTables.interview.map((row) => <tr key={row[0]}><td>{row[0]}</td><td>{row[1]}</td></tr>)}</tbody>
        </table>
      </div>

      <h3>事实与版本约束</h3>
      <div className="doc-table-wrap">
        <table className="doc-table">
          <thead><tr><th>机制</th><th>规则</th></tr></thead>
          <tbody>{ruleTables.facts.map((row) => <tr key={row[0]}><td>{row[0]}</td><td>{row[1]}</td></tr>)}</tbody>
        </table>
      </div>

      <h2>模型与供应商分工</h2>
      <div className="doc-table-wrap">
        <table className="doc-table">
          <thead><tr><th>模型 / 服务</th><th>职责</th><th>通道</th></tr></thead>
          <tbody>{agents.map((row) => <tr key={row[0]}><td>{row[0]}</td><td>{row[1]}</td><td>{row[2]}</td></tr>)}</tbody>
        </table>
      </div>

      <h2>接口契约（前缀 /api/v1）</h2>
      <div className="doc-table-wrap">
        <table className="doc-table">
          <thead><tr><th>方法</th><th>路径</th><th>用途</th></tr></thead>
          <tbody>{endpoints.map((row) => <tr key={row[1] + row[0]}><td><code>{row[0]}</code></td><td><code>{row[1]}</code></td><td>{row[2]}</td></tr>)}</tbody>
        </table>
      </div>

      <h2>场景攻略任务状态机</h2>
      <p><code>queued → searching → generating → reviewing → completed</code>；分支状态为 <code>needs_clarification</code>（信息不足）、<code>failed</code>（保留输入可重试）。缺少目标单位、届次或赛道时返回澄清问题，不会擅自替换成另一届或另一个流程；未配置检索服务时结果标注「未联网核验」。</p>

      <h2>安全边界</h2>
      <p>简历原文、姓名、电话不进入搜索词；网页内容一律视为不可信数据；用户提供的链接在服务端校验协议与解析地址，回环 / 私网 / 链路本地与云元数据地址被拦截；相同 request_id 重复提交返回原任务，不重复计费。</p>
      <p className="privacy-warning">本页是行为说明，不是能力承诺：模型输出仍可能出错，所有「已查证」结论都应能点开来源逐字核对。</p>
    </main>
  );
}
