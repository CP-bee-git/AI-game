"use client";

import { useEffect, useState } from "react";
import { ArrowRight, CheckCircle2, CircleAlert, FileUp, Gauge, ScanSearch, Sparkles } from "lucide-react";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

type ModelConfig = {
  base_url: string;
  model: string;
  embedding_model: string;
  embedding_dimensions: number;
};

type UploadResult = {
  resume_id: string;
  filename: string;
  size_bytes: number;
  task?: { status: string; message?: string };
};

type ProfileDraft = {
  skills: Array<{ name?: string; normalized_name?: string; level?: string }>;
  education: Array<Record<string, string>>;
  experiences: Array<Record<string, string>>;
  projects: Array<Record<string, string>>;
  preferences: Record<string, unknown>;
  warnings: string[];
  status?: string;
};

type MatchResult = {
  job_title: string;
  company: string;
  location: string;
  eligible: boolean;
  total_score: number;
  hard_fail_reasons: string[];
  matched_skills: string[];
  skill_gaps: string[];
};

type DiagnosticReport = {
  report_id: string;
  job_title: string;
  company: string;
  strengths: string[];
  must_fix: string[];
  optional_improve: string[];
  ats_keywords: string[];
  checklist: string[];
};

type InterviewSession = {
  session_id: string;
  job_title: string;
  status: "active" | "completed";
  current_question?: string;
  turns: Array<{ question: string; answer?: string; score?: number; feedback?: string }>;
  overall_score?: number;
  summary: string[];
};

const steps = ["上传简历", "确认画像", "岗位匹配", "简历诊断", "模拟面试"];

export default function Home() {
  const [model, setModel] = useState<ModelConfig | null>(null);
  const [apiState, setApiState] = useState<"checking" | "online" | "offline">("checking");
  const [uploading, setUploading] = useState(false);
  const [upload, setUpload] = useState<UploadResult | null>(null);
  const [profile, setProfile] = useState<ProfileDraft | null>(null);
  const [generatingProfile, setGeneratingProfile] = useState(false);
  const [skillText, setSkillText] = useState("");
  const [confirmingProfile, setConfirmingProfile] = useState(false);
  const [jobLines, setJobLines] = useState("");
  const [jobsetId, setJobsetId] = useState<string | null>(null);
  const [jobCount, setJobCount] = useState(0);
  const [importingJobs, setImportingJobs] = useState(false);
  const [matching, setMatching] = useState(false);
  const [matches, setMatches] = useState<MatchResult[]>([]);
  const [report, setReport] = useState<DiagnosticReport | null>(null);
  const [reporting, setReporting] = useState(false);
  const [interview, setInterview] = useState<InterviewSession | null>(null);
  const [interviewAnswer, setInterviewAnswer] = useState("");
  const [answering, setAnswering] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([fetch(`${apiBase}/health`), fetch(`${apiBase}/model-config`)]).then(async ([health, config]) => {
      if (!health.ok || !config.ok) throw new Error("API offline");
      setApiState("online");
      setModel(await config.json());
    }).catch(() => setApiState("offline"));
  }, []);

  async function handleUpload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const input = form.elements.namedItem("resume") as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    setUploading(true);
    setError("");
    setUpload(null);
    setProfile(null);
    setSkillText("");
    setJobsetId(null);
    setJobCount(0);
    setMatches([]);
    setReport(null);
    setInterview(null);
    const body = new FormData();
    body.append("file", file);
    try {
      const response = await fetch(`${apiBase}/resumes/upload`, { method: "POST", body });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "上传失败");
      setUpload(data);
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "上传失败");
    } finally {
      setUploading(false);
    }
  }

  async function generateProfile() {
    if (!upload) return;
    setGeneratingProfile(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/resumes/${upload.resume_id}/profile`, { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "画像生成失败");
      setProfile(data);
      setSkillText(data.skills.map((skill: { normalized_name?: string; name?: string }) => skill.normalized_name ?? skill.name ?? "").filter(Boolean).join(", "));
    } catch (profileError) {
      setError(profileError instanceof Error ? profileError.message : "画像生成失败");
    } finally {
      setGeneratingProfile(false);
    }
  }

  async function confirmProfile() {
    if (!upload || !profile) return;
    setConfirmingProfile(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/resumes/${upload.resume_id}/profile/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...profile, skills: skillText.split(",").map((name) => name.trim()).filter(Boolean).map((name) => ({ name, normalized_name: name })) }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "画像确认失败");
      setProfile(data);
    } catch (confirmError) {
      setError(confirmError instanceof Error ? confirmError.message : "画像确认失败");
    } finally {
      setConfirmingProfile(false);
    }
  }

  async function importJobs() {
    if (!profile) return;
    const jobs = jobLines.split("\n").map((line) => line.trim()).filter(Boolean).map((line) => {
      const [title = "未命名岗位", company = "未填写", location = "不限", skills = ""] = line.split("|").map((part) => part.trim());
      return { title, company, location, required_skills: skills.split(",").map((skill) => skill.trim()).filter(Boolean), raw_text: line };
    });
    if (!jobs.length || jobs.length > 20) {
      setError("请按每行一条输入 1–20 个岗位");
      return;
    }
    setImportingJobs(true);
    setError("");
    try {
      const createResponse = await fetch(`${apiBase}/jobsets`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: "本次岗位清单" }) });
      const created = await createResponse.json();
      if (!createResponse.ok) throw new Error(created.detail ?? "岗位清单创建失败");
      const importResponse = await fetch(`${apiBase}/jobsets/${created.jobset_id}/jobs/import`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ jobs }) });
      const imported = await importResponse.json();
      if (!importResponse.ok) throw new Error(imported.detail ?? "岗位导入失败");
      setJobsetId(created.jobset_id);
      setJobCount(imported.jobs.length);
      setMatches([]);
    } catch (jobError) {
      setError(jobError instanceof Error ? jobError.message : "岗位导入失败");
    } finally {
      setImportingJobs(false);
    }
  }

  async function runMatches() {
    if (!upload || !jobsetId) return;
    setMatching(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/matches/run`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ resume_id: upload.resume_id, jobset_id: jobsetId }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "匹配失败");
      setMatches(data.results);
    } catch (matchError) {
      setError(matchError instanceof Error ? matchError.message : "匹配失败");
    } finally {
      setMatching(false);
    }
  }

  async function createDiagnosis(jobTitle: string) {
    if (!upload || !jobsetId) return;
    setReporting(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/reports/diagnosis`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ resume_id: upload.resume_id, jobset_id: jobsetId, job_title: jobTitle }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "诊断生成失败");
      setReport(data);
    } catch (reportError) {
      setError(reportError instanceof Error ? reportError.message : "诊断生成失败");
    } finally {
      setReporting(false);
    }
  }

  async function startInterview(jobTitle: string) {
    if (!upload || !jobsetId) return;
    setError("");
    try {
      const response = await fetch(`${apiBase}/interviews`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ resume_id: upload.resume_id, jobset_id: jobsetId, job_title: jobTitle }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "面试创建失败");
      setInterview(data);
      setInterviewAnswer("");
    } catch (interviewError) {
      setError(interviewError instanceof Error ? interviewError.message : "面试创建失败");
    }
  }

  async function answerCurrentQuestion() {
    if (!interview || !interviewAnswer.trim()) return;
    setAnswering(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/interviews/${interview.session_id}/answer`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ answer: interviewAnswer }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "回答提交失败");
      setInterview(data);
      setInterviewAnswer("");
    } catch (answerError) {
      setError(answerError instanceof Error ? answerError.message : "回答提交失败");
    } finally {
      setAnswering(false);
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="CareerPilot 首页">
          <span className="brand-mark"><Sparkles size={17} /></span>
          <span>CareerPilot</span>
        </a>
        <div className="topbar-meta">
          <span className={`status-dot ${apiState}`} />
          <span>{apiState === "online" ? "服务在线" : apiState === "offline" ? "等待 API" : "连接中"}</span>
          <span className="divider" />
          <span className="quiet">候选人工作台</span>
        </div>
      </header>

      <section className="hero-grid">
        <div className="intro">
          <p className="eyebrow">B2 · 智能求职辅助</p>
          <h1>让每一份经历，<br /><em>找到合适的岗位。</em></h1>
          <p className="intro-copy">从简历中建立能力画像，再用岗位证据解释匹配结果。你的求职路径从这里开始。</p>
          <div className="metric-row">
            <div><strong>01</strong><span>能力画像</span></div>
            <div><strong>02</strong><span>岗位匹配</span></div>
            <div><strong>03</strong><span>面试反馈</span></div>
          </div>
        </div>
        <div className="signal-panel">
          <div className="signal-header"><span>系统准备度</span><Gauge size={16} /></div>
          <div className="signal-score"><strong>01</strong><span>/ 05</span></div>
          <div className="signal-line"><span style={{ width: "20%" }} /></div>
          <p>上传简历后开始建立你的第一版能力画像。</p>
        </div>
      </section>

      <nav className="stepper" aria-label="求职流程">
        {steps.map((step, index) => (
          <div className={`step ${index === 0 ? "active" : ""}`} key={step}>
            <span className="step-index">{String(index + 1).padStart(2, "0")}</span>
            <span>{step}</span>
            {index < steps.length - 1 && <ArrowRight size={14} className="step-arrow" />}
          </div>
        ))}
      </nav>

      <section className="workspace-grid">
        <div className="upload-section">
          <div className="section-heading">
            <div><p className="eyebrow">第一步</p><h2>上传你的简历</h2></div>
            <span className="stage-tag">待开始</span>
          </div>
          <form onSubmit={handleUpload}>
            <label className="dropzone" htmlFor="resume">
              <span className="upload-icon"><FileUp size={23} /></span>
              <span className="drop-title">拖入文件，或点击选择</span>
              <span className="drop-hint">PDF、DOCX、PNG、JPG · 最大 10 MB</span>
              <input id="resume" name="resume" type="file" accept=".pdf,.docx,.png,.jpg,.jpeg" />
            </label>
            <button className="primary-button" disabled={uploading} type="submit">
              {uploading ? "上传中..." : "上传并解析"}<ArrowRight size={17} />
            </button>
          </form>
          {error && <div className="notice error"><CircleAlert size={16} />{error}</div>}
          {upload && <div className="notice success"><CheckCircle2 size={16} /><span><strong>{upload.filename}</strong> 已接收。{upload.task?.message}</span></div>}
          {upload && !profile && <button className="secondary-button" disabled={generatingProfile} onClick={generateProfile} type="button"><Sparkles size={16} />{generatingProfile ? "正在生成画像..." : "生成能力画像"}</button>}
          {profile && <div className="profile-preview"><div className="profile-preview-head"><strong>能力画像{profile.status === "confirmed" ? "" : "草稿"}</strong><span>{profile.status === "confirmed" ? "已确认" : "待你确认"}</span></div><label className="field-label" htmlFor="skills">技能（可修改，逗号分隔）</label><input className="text-input" id="skills" value={skillText} onChange={(event) => setSkillText(event.target.value)} disabled={profile.status === "confirmed"} /><div className="skill-list">{profile.skills.length ? profile.skills.slice(0, 12).map((skill, index) => <span key={`${skill.name}-${index}`}>{skill.normalized_name ?? skill.name ?? "未命名技能"}</span>) : <small>模型未从简历中提取到明确技能</small>}</div>{profile.warnings.length > 0 && <p className="profile-warning">{profile.warnings[0]}</p>}{profile.status !== "confirmed" && <button className="secondary-button" disabled={confirmingProfile} onClick={confirmProfile} type="button">{confirmingProfile ? "保存中..." : "确认画像并进入岗位匹配"}<ArrowRight size={15} /></button>}</div>}
        </div>

        <aside className="info-panel">
          <div className="panel-title"><ScanSearch size={17} /><span>本次工作区</span></div>
          <div className="info-list">
            <div><span>画像状态</span><strong>{profile ? "待确认" : upload ? "可生成" : "尚未建立"}</strong></div>
            <div><span>岗位清单</span><strong>0 / 20</strong></div>
            <div><span>面试状态</span><strong>未开始</strong></div>
          </div>
          <div className="model-card">
            <div className="model-card-head"><span className="mini-dot" />模型连接</div>
            {model ? <><strong>{model.model}</strong><span>{model.base_url}</span><small>Embedding · {model.embedding_dimensions} 维</small></> : <span className="muted">等待后端配置</span>}
          </div>
        </aside>
      </section>

      {profile?.status === "confirmed" && <section className="next-stage">
        <div className="section-heading"><div><p className="eyebrow">第二步</p><h2>导入岗位清单</h2></div><span className="stage-tag">{jobCount ? `${jobCount} 个岗位` : "待导入"}</span></div>
        <p className="field-help">每行一条：岗位名称 | 公司 | 城市 | 必需技能（逗号分隔）。例如：数据分析师 | 示例公司 | 上海 | Python, SQL</p>
        <textarea className="job-input" value={jobLines} onChange={(event) => setJobLines(event.target.value)} placeholder="数据分析师 | 示例公司 | 上海 | Python, SQL\n产品运营 | 示例科技 | 杭州 | 用户研究, Excel" rows={5} />
        <div className="action-row"><button className="primary-button compact" disabled={importingJobs} onClick={importJobs} type="button">{importingJobs ? "导入中..." : "导入岗位"}<ArrowRight size={16} /></button>{jobsetId && <button className="secondary-button compact" disabled={matching} onClick={runMatches} type="button">{matching ? "计算中..." : "开始匹配"}<ScanSearch size={15} /></button>}</div>
        {matches.length > 0 && <div className="match-list"><div className="match-list-head"><strong>匹配结果</strong><span>合格岗位优先</span></div>{matches.map((match, index) => <div className="match-row" key={`${match.job_title}-${index}`}><div className="match-rank">{String(index + 1).padStart(2, "0")}</div><div className="match-main"><strong>{match.job_title}</strong><span>{match.company} · {match.location}</span><small>{match.skill_gaps.length ? `能力缺口：${match.skill_gaps.join(", ")}` : "已命中必需技能"}</small><div className="match-actions"><button type="button" onClick={() => createDiagnosis(match.job_title)}>{reporting ? "生成中..." : "诊断"}</button><button type="button" onClick={() => startInterview(match.job_title)}>面试</button></div></div><div className={`match-score ${match.eligible ? "eligible" : "risk"}`}>{Math.round(match.total_score)}<small>{match.eligible ? "匹配" : "风险"}</small></div></div>)}</div>}
        {report && <div className="report-panel"><div className="match-list-head"><strong>{report.job_title} · 简历诊断</strong><span>{report.company}</span></div><div className="report-columns"><div><b>优势</b>{report.strengths.map((item) => <p key={item}>{item}</p>)}</div><div><b>必须改进</b>{report.must_fix.length ? report.must_fix.map((item) => <p key={item}>{item}</p>) : <p>暂无硬性缺口</p>}</div><div><b>ATS 关键词</b><p>{report.ats_keywords.join("、") || "暂无"}</p></div></div></div>}
        {interview && <div className="interview-panel"><div className="match-list-head"><strong>{interview.job_title} · 模拟面试</strong><span>{interview.status === "completed" ? `总分 ${interview.overall_score ?? "-"}/5` : `第 ${interview.turns.length + 1} 题`}</span></div>{interview.status === "active" ? <><p className="interview-question">{interview.current_question}</p><textarea className="job-input" value={interviewAnswer} onChange={(event) => setInterviewAnswer(event.target.value)} placeholder="输入你的回答..." rows={4} /><button className="primary-button compact" disabled={answering || !interviewAnswer.trim()} onClick={answerCurrentQuestion} type="button">{answering ? "评分中..." : "提交回答"}<ArrowRight size={16} /></button></> : <div className="interview-summary">{interview.summary.map((item) => <p key={item}>{item}</p>)}</div>}</div>}
      </section>}

      <footer><span>CareerPilot / B2 MVP</span><span>模型输出仅供求职辅助参考</span></footer>
    </main>
  );
}

