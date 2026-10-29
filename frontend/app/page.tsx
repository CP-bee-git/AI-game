"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowRight, Check, CheckCircle2, CircleAlert, Cloud, Compass, Download, FileUp, LockKeyhole, ScanSearch, ShieldCheck, Sparkles, Unplug } from "lucide-react";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";

type ModelConfig = {
  model: string;
  provider: string;
  image_ocr: string;
  matching: string;
  chat_configured: boolean;
  vision_configured: boolean;
  region?: "china" | "singapore";
};

type UploadResult = {
  resume_id: string;
  filename: string;
  size_bytes: number;
  task?: { status: string; message?: string };
};

type ProfileDraft = {
  skills: Array<{ name?: string; normalized_name?: string; level?: string; [key: string]: unknown }>;
  education: Array<Record<string, unknown>>;
  experiences: Array<Record<string, unknown>>;
  projects: Array<Record<string, unknown>>;
  preferences: Record<string, unknown>;
  warnings: string[];
  status?: string;
};

type ProfileAnalysis = {
  resume_id: string;
  dimensions: Array<{ name: string; score: number; evidence: string[]; note: string }>;
  notice: string;
  careers: {
    catalog: { id: string; name: string; version: string; source_url: string; license: string; accessed_on: string; notice: string; attribution?: string; scoring_method?: string };
    total: number;
    results: Array<{
      code: string; title: string; original_title: string; description: string; source_url: string;
      score: number; stars: number; matched_skills: string[]; skill_gaps: string[]; reason: string;
    }>;
  };
};

type JobInput = {
  title: string;
  company: string;
  location: string;
  education_required?: string | null;
  experience_required?: string | null;
  required_skills: string[];
  raw_text?: string | null;
};

type DemoInfo = { notice: string; sources: Array<{ title: string; url: string }> };

type MatchResult = {
  job_title: string;
  company: string;
  location: string;
  eligible: boolean;
  total_score: number;
  hard_fail_reasons: string[];
  matched_skills: string[];
  skill_gaps: string[];
  evidence?: string[];
  score_breakdown: Record<string, number>;
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
const regions = { china: "中国内地 · 北京", singapore: "国际 · 新加坡" } as const;

function errorMessage(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item) => typeof item?.msg === "string" ? item.msg : "输入不符合要求").join("；");
  return fallback;
}

function StarRating({ score, label }: { score: number; label: string }) {
  const value = Math.min(5, Math.max(0, score));
  return <span className="star-rating" role="img" aria-label={`${label}：${value} / 5 星`}>
    {Array.from({ length: 5 }, (_, index) => <span className="star" aria-hidden="true" key={index}>★<span style={{ width: `${Math.min(1, Math.max(0, value - index)) * 100}%` }}>★</span></span>)}
  </span>;
}

export default function Home() {
  const [model, setModel] = useState<ModelConfig | null>(null);
  const [apiState, setApiState] = useState<"checking" | "online" | "offline">("checking");
  const [uploading, setUploading] = useState(false);
  const [selectedFilename, setSelectedFilename] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [region, setRegion] = useState<keyof typeof regions>("china");
  const [modelName, setModelName] = useState("qwen-plus");
  const configFieldsEdited = useRef({ region: false, model: false });
  const [configuring, setConfiguring] = useState(false);
  const [clearingConfig, setClearingConfig] = useState(false);
  const [configError, setConfigError] = useState("");
  const [configNotice, setConfigNotice] = useState("");
  const [privacyAccepted, setPrivacyAccepted] = useState(false);
  const [upload, setUpload] = useState<UploadResult | null>(null);
  const [profile, setProfile] = useState<ProfileDraft | null>(null);
  const [generatingProfile, setGeneratingProfile] = useState(false);
  const [skillText, setSkillText] = useState("");
  const [confirmingProfile, setConfirmingProfile] = useState(false);
  const [analysis, setAnalysis] = useState<ProfileAnalysis | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState("");
  const analysisRequest = useRef<AbortController | null>(null);
  const [jobLines, setJobLines] = useState("");
  const [jobsetId, setJobsetId] = useState<string | null>(null);
  const [jobCount, setJobCount] = useState(0);
  const [importedJobs, setImportedJobs] = useState<JobInput[]>([]);
  const [demoInfo, setDemoInfo] = useState<DemoInfo | null>(null);
  const [demoActive, setDemoActive] = useState(false);
  const [loadingDemo, setLoadingDemo] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [importingJobs, setImportingJobs] = useState(false);
  const [matching, setMatching] = useState(false);
  const [matches, setMatches] = useState<MatchResult[]>([]);
  const [report, setReport] = useState<DiagnosticReport | null>(null);
  const [reporting, setReporting] = useState(false);
  const [interview, setInterview] = useState<InterviewSession | null>(null);
  const [interviewAnswer, setInterviewAnswer] = useState("");
  const [answering, setAnswering] = useState(false);
  const [startingInterview, setStartingInterview] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    const options = { signal: controller.signal, credentials: "same-origin" as const, cache: "no-store" as const };
    async function initialize() {
      try {
        // Establish one browser session before any parallel API requests.
        const config = await fetch(`${apiBase}/model-config`, options);
        if (!config.ok) throw new Error("API offline");
        const configuration: ModelConfig = await config.json();
        if (controller.signal.aborted) return;
        setModel(configuration);
        if (configuration.region && !configFieldsEdited.current.region) setRegion(configuration.region);
        if (configuration.chat_configured && !configFieldsEdited.current.model) setModelName(configuration.model);
        const [health, demo] = await Promise.all([
          fetch(`${apiBase}/health`, options),
          fetch(`${apiBase}/demo/china`, options),
        ]);
        if (!health.ok) throw new Error("API offline");
        if (demo.ok) setDemoInfo(await demo.json());
        if (!controller.signal.aborted) setApiState("online");
      } catch {
        if (!controller.signal.aborted) setApiState("offline");
      }
    }
    void initialize();
    return () => {
      controller.abort();
      analysisRequest.current?.abort();
    };
  }, []);

  async function refreshModel() {
    const response = await fetch(`${apiBase}/model-config`, { cache: "no-store", credentials: "same-origin" });
    if (!response.ok) throw new Error("暂时无法读取连接状态，请稍后刷新页面。");
    const configuration: ModelConfig = await response.json();
    setModel(configuration);
    setApiState("online");
  }

  async function configureModel(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setConfiguring(true);
    setConfigError("");
    setConfigNotice("");
    const submittedKey = apiKey.trim();
    try {
      const response = await fetch(`${apiBase}/model/configure`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: submittedKey, region, model: modelName.trim() }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(errorMessage(data.detail, "连接验证失败，请检查 API Key、区域和模型权限。"));
      setApiKey("");
      await refreshModel();
      setConfigNotice("连接验证成功，可以开始处理简历了。密钥输入已清空。");
    } catch (configError) {
      const message = configError instanceof Error ? configError.message : "暂时无法连接，请稍后重试。";
      setConfigError(submittedKey ? message.replaceAll(submittedKey, "[密钥已隐藏]") : message);
    } finally {
      setConfiguring(false);
    }
  }

  async function clearModel() {
    setClearingConfig(true);
    setConfigError("");
    setConfigNotice("");
    try {
      const response = await fetch(`${apiBase}/model/configure`, { method: "DELETE", credentials: "same-origin" });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(errorMessage(data.detail, "连接清除失败，请稍后重试。"));
      }
      setApiKey("");
      await refreshModel();
      setConfigNotice("当前浏览器的临时密钥已清除。");
    } catch (clearError) {
      setConfigError(clearError instanceof Error ? clearError.message : "连接清除失败，请稍后重试。");
    } finally {
      setClearingConfig(false);
    }
  }

  function resetAnalysis() {
    analysisRequest.current?.abort();
    setAnalysis(null);
    setAnalyzing(false);
    setAnalysisError("");
  }

  async function loadAnalysis(resumeId: string) {
    analysisRequest.current?.abort();
    const controller = new AbortController();
    analysisRequest.current = controller;
    setAnalyzing(true);
    setAnalysisError("");
    try {
      const response = await fetch(`${apiBase}/resumes/${resumeId}/analysis`, { credentials: "same-origin", cache: "no-store", signal: controller.signal });
      const data = await response.json();
      if (!response.ok) throw new Error(errorMessage(data.detail, "画像分析暂时不可用，请重试。"));
      if (!controller.signal.aborted) setAnalysis(data);
    } catch (analysisError) {
      if (!controller.signal.aborted) setAnalysisError(analysisError instanceof Error ? analysisError.message : "画像分析暂时不可用，请重试。");
    } finally {
      if (!controller.signal.aborted) setAnalyzing(false);
    }
  }

  async function loadDemo() {
    resetAnalysis();
    setLoadingDemo(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/demo/china/start`, { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(errorMessage(data.detail, "样例加载失败"));
      setUpload(data.resume);
      setProfile(data.profile);
      setSkillText(data.profile.skills.map((skill: { normalized_name?: string; name?: string }) => skill.normalized_name ?? skill.name ?? "").filter(Boolean).join(", "));
      setJobsetId(data.jobset.jobset_id);
      setJobCount(data.jobset.jobs.length);
      setImportedJobs(data.jobset.jobs);
      setJobLines("");
      setMatches([]);
      setReport(null);
      setInterview(null);
      setInterviewAnswer("");
      setDemoActive(true);
      setDemoInfo((previous) => ({ notice: data.notice, sources: previous?.sources ?? [] }));
    } catch (demoError) {
      setError(demoError instanceof Error ? demoError.message : "样例加载失败");
    } finally {
      setLoadingDemo(false);
    }
  }

  async function exportReport(type: "profile" | "diagnosis" | "interview", resourceId: string, format: "html" | "json") {
    setExporting(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/exports`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type, resource_id: resourceId, format }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(errorMessage(data.detail, "报告导出失败"));
      const url = URL.createObjectURL(new Blob([data.content], { type: data.content_type }));
      const link = document.createElement("a");
      link.href = url;
      link.download = data.filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (exportError) {
      setError(exportError instanceof Error ? exportError.message : "报告导出失败");
    } finally {
      setExporting(false);
    }
  }

  async function handleUpload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const input = form.elements.namedItem("resume") as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    setUploading(true);
    setError("");
    resetAnalysis();
    setUpload(null);
    setProfile(null);
    setSkillText("");
    setJobsetId(null);
    setJobCount(0);
    setImportedJobs([]);
    setDemoActive(false);
    setMatches([]);
    setReport(null);
    setInterview(null);
    const body = new FormData();
    body.append("file", file);
    body.append("privacy_acknowledged", String(privacyAccepted));
    try {
      const response = await fetch(`${apiBase}/resumes/upload`, { method: "POST", body });
      const data = await response.json();
      if (!response.ok) throw new Error(errorMessage(data.detail, "上传失败"));
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
      if (!response.ok) throw new Error(errorMessage(data.detail, "画像生成失败"));
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
        body: JSON.stringify({ ...profile, skills: skillText.split(/[,，]/).map((name) => name.trim()).filter(Boolean).map((name) => profile.skills.find((skill) => (skill.normalized_name ?? skill.name) === name) ?? ({ name, normalized_name: name })) }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(errorMessage(data.detail, "画像确认失败"));
      setProfile(data);
      await loadAnalysis(upload.resume_id);
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
      if (!createResponse.ok) throw new Error(errorMessage(created.detail, "岗位清单创建失败"));
      const importResponse = await fetch(`${apiBase}/jobsets/${created.jobset_id}/jobs/import`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ jobs }) });
      const imported = await importResponse.json();
      if (!importResponse.ok) throw new Error(errorMessage(imported.detail, "岗位导入失败"));
      setJobsetId(created.jobset_id);
      setJobCount(imported.jobs.length);
      setImportedJobs(imported.jobs);
      setMatches([]);
      setReport(null);
      setInterview(null);
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
      if (!response.ok) throw new Error(errorMessage(data.detail, "匹配失败"));
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
      if (!response.ok) throw new Error(errorMessage(data.detail, "诊断生成失败"));
      setReport(data);
    } catch (reportError) {
      setError(reportError instanceof Error ? reportError.message : "诊断生成失败");
    } finally {
      setReporting(false);
    }
  }

  async function startInterview(jobTitle: string) {
    if (!upload || !jobsetId) return;
    setStartingInterview(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/interviews`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ resume_id: upload.resume_id, jobset_id: jobsetId, job_title: jobTitle }) });
      const data = await response.json();
      if (!response.ok) throw new Error(errorMessage(data.detail, "面试创建失败"));
      setInterview(data);
      setInterviewAnswer("");
    } catch (interviewError) {
      setError(interviewError instanceof Error ? interviewError.message : "面试创建失败");
    } finally {
      setStartingInterview(false);
    }
  }

  async function answerCurrentQuestion() {
    if (!interview || !interviewAnswer.trim()) return;
    setAnswering(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/interviews/${interview.session_id}/answer`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ answer: interviewAnswer }) });
      const data = await response.json();
      if (!response.ok) throw new Error(errorMessage(data.detail, "回答提交失败"));
      setInterview(data);
      setInterviewAnswer("");
    } catch (answerError) {
      setError(answerError instanceof Error ? answerError.message : "回答提交失败");
    } finally {
      setAnswering(false);
    }
  }

  const activeStep = interview ? 4 : report ? 3 : profile?.status === "confirmed" ? 2 : upload ? 1 : 0;

  return (
    <main className="shell">
      <a className="skip-link" href="#workspace">跳到求职工作台</a>
      <header className="topbar">
        <a className="brand" href="/" aria-label="CareerPilot 首页">
          <span className="brand-mark"><Compass size={22} strokeWidth={1.8} /></span>
          <span>CareerPilot<small>就业罗盘</small></span>
        </a>
        <nav className="topnav" aria-label="主导航"><a href="#workspace">工作台</a><a href="#analysis">职业方向</a><a href="#cloud-config">模型连接</a></nav>
        <div className="topbar-meta" aria-live="polite">
          <span className={`status-dot ${apiState}`} />
          <span>{apiState === "online" ? model?.chat_configured ? "云模型已连接" : "服务就绪 · 待连接模型" : apiState === "offline" ? "服务暂未连接" : "连接中"}</span>
        </div>
      </header>

      <section className="workspace-intro" aria-labelledby="workspace-title">
        <div><p className="eyebrow">CAREER WORKSPACE</p><h1 id="workspace-title">下一步，从了解自己开始。</h1><p>读懂简历，连接职业方向，准备下一次机会。</p></div>
        <a className="text-link" href="#workspace">开始分析 <ArrowRight size={16} /></a>
      </section>

      <nav className="stepper" aria-label="求职流程">
        {steps.map((step, index) => (
          <a href={index < 2 || profile?.status !== "confirmed" ? "#workspace" : index === 2 ? "#analysis" : "#jobs"} className={`step ${index === activeStep ? "active" : ""} ${index < activeStep ? "complete" : ""}`} aria-current={index === activeStep ? "step" : undefined} key={step}>
            <span className="step-index">{index < activeStep ? <Check size={14} /> : String(index + 1).padStart(2, "0")}</span>
            <span>{step}</span>
            {index < steps.length - 1 && <ArrowRight size={14} className="step-arrow" />}
          </a>
        ))}
      </nav>

      <section className="cloud-panel" id="cloud-config" aria-labelledby="cloud-title">
        <div className="cloud-intro"><span className="section-icon"><Cloud size={21} /></span><p className="eyebrow">MODEL CONNECTION</p><h2 id="cloud-title">连接云端模型</h2><p>输入阿里云百炼 / 千问 API Key，选择密钥所属区域。验证成功后，即可处理你的简历。</p><div className="cloud-state"><span className={`status-dot ${model?.chat_configured ? "online" : "checking"}`} /><span>{model?.chat_configured ? `已连接 · ${model.model}` : "尚未连接 · 可先体验合成样例"}</span></div></div>
        <form className="cloud-form" onSubmit={configureModel} autoComplete="off">
          <div className="cloud-form-head"><strong><LockKeyhole size={16} />云端模型配置</strong><span className={`connection-badge ${model?.chat_configured ? "connected" : ""}`}>{model?.chat_configured ? "连接已验证" : "等待连接"}</span></div>
          <label className="field-label" htmlFor="api-key">千问 / 阿里云 API Key</label>
          <input className="text-input key-input" id="api-key" name="api-key" type="password" aria-describedby="api-key-help" autoComplete="new-password" spellCheck={false} value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder="请输入你的 API Key" required maxLength={512} disabled={configuring || clearingConfig} />
          <p className="key-help" id="api-key-help">使用百炼通用 API Key，密钥与服务区域须一致。阿里云 AccessKey、Coding / Token 套餐专属密钥不适用。</p>
          <div className="config-fields"><div><label className="field-label" htmlFor="region">服务区域</label><select className="text-input" id="region" value={region} onChange={(event) => { configFieldsEdited.current.region = true; setRegion(event.target.value as keyof typeof regions); }} disabled={configuring || clearingConfig}>{Object.entries(regions).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></div><div><label className="field-label" htmlFor="model-name">聊天模型</label><input className="text-input" id="model-name" list="qwen-models" value={modelName} onChange={(event) => { configFieldsEdited.current.model = true; setModelName(event.target.value); }} placeholder="qwen-plus" required maxLength={100} disabled={configuring || clearingConfig} /><datalist id="qwen-models"><option value="qwen-plus" /><option value="qwen-turbo" /><option value="qwen-max" /></datalist></div></div>
          <p className="config-privacy"><ShieldCheck size={14} /><span>密钥只临时保存在服务器内存，仅用于当前浏览器会话；不会写入浏览器持久存储。云 API 调用按你的阿里云账户计费。</span></p>
          <div className="action-row"><button className="primary-button compact" type="submit" disabled={apiState !== "online" || !apiKey.trim() || !modelName.trim() || configuring || clearingConfig}>{configuring ? "正在验证连接…" : model?.chat_configured ? "验证并更新连接" : "验证并连接"}<ArrowRight size={16} /></button>{model?.chat_configured && <button className="secondary-button compact" type="button" onClick={clearModel} disabled={configuring || clearingConfig}><Unplug size={15} />{clearingConfig ? "清除中…" : "清除临时密钥"}</button>}</div>
          {configError && <div className="notice error" role="alert"><CircleAlert size={16} /><span>{configError}</span></div>}
          {configNotice && <div className="notice success" role="status"><CheckCircle2 size={16} /><span>{configNotice}</span></div>}
        </form>
      </section>

      <section className="demo-panel" id="demo" aria-label="中国数据演示">
        <div>
          <p className="eyebrow">QUICK PREVIEW</p>
          <h2>用一份合成简历，体验完整流程</h2>
          <p>无需密钥。先确认样例画像，再查看职业方向、岗位匹配与面试反馈。</p>
          <p className="demo-disclosure">样例画像为预先编写，不是模型抽取结果；本轮匹配、诊断和面试反馈使用基础规则，可在未连接模型时演示。</p>
          {demoInfo && <details className="demo-sources"><summary>样例说明与来源</summary><p>{demoInfo.notice}</p><div className="source-links">{demoInfo.sources.map((source) => <a href={source.url} target="_blank" rel="noreferrer" key={source.url}>{source.title} ↗</a>)}</div></details>}
        </div>
        <div className="demo-actions">
          <button className="primary-button compact" disabled={apiState !== "online" || loadingDemo || uploading} onClick={loadDemo} type="button">{loadingDemo ? "加载中..." : "加载中国样例 · 合成简历"}<ArrowRight size={16} /></button>
          <a className="secondary-button compact" href={`${apiBase}/demo/china/resume`} download>下载合成简历 DOCX</a>
        </div>
      </section>

      <section className="workspace-grid" id="workspace">
        <div className="upload-section">
          <div className="section-heading">
            <div><p className="eyebrow">01 / 从这里开始</p><h2>上传你的简历</h2></div>
            <span className="stage-tag">{demoActive ? "合成样例" : upload ? "已上传" : "待开始"}</span>
          </div>
          <form onSubmit={handleUpload}>
            <label className="dropzone" htmlFor="resume">
              <span className="upload-icon"><FileUp size={23} /></span>
              <span className="drop-title">{selectedFilename || "点击选择你的简历"}</span>
              <span className="drop-hint">PDF、DOCX、PNG、JPG · 最大 10 MB</span>
              <input id="resume" name="resume" type="file" accept=".pdf,.docx,.png,.jpg,.jpeg" onChange={(event) => setSelectedFilename(event.target.files?.[0]?.name ?? "")} required aria-label="选择简历文件" />
            </label>
            <label className="privacy-consent"><input type="checkbox" checked={privacyAccepted} onChange={(event) => setPrivacyAccepted(event.target.checked)} /><span>上传简历前，请阅读<a href="/privacy">数据处理说明</a>。图片及扫描件由千问云端视觉模型识别；生成画像、诊断和面试时，相关文本会发送至你选择区域的阿里云服务。请先脱敏。</span></label>
            <button className="primary-button" disabled={apiState !== "online" || uploading || !privacyAccepted || !selectedFilename} type="submit">
              {uploading ? "上传中..." : "上传并解析"}<ArrowRight size={17} />
            </button>
          </form>
          {error && <div className="notice error" role="alert"><CircleAlert size={16} /><span>{error}</span></div>}
          {upload && <div className="notice success" role="status"><CheckCircle2 size={16} /><span><strong>{upload.filename}</strong> 已接收。{upload.task?.message}</span></div>}
          {upload && !profile && <button className="secondary-button" disabled={generatingProfile} onClick={generateProfile} type="button"><Sparkles size={16} />{generatingProfile ? "正在生成画像..." : "生成能力画像"}</button>}
          {profile && <div className="profile-preview"><div className="profile-preview-head"><strong>能力画像{profile.status === "confirmed" ? "" : "草稿"}</strong><span>{profile.status === "confirmed" ? "已确认" : "待你确认"}</span></div><label className="field-label" htmlFor="skills">技能（可修改，逗号分隔）</label><input className="text-input" id="skills" value={skillText} onChange={(event) => setSkillText(event.target.value)} disabled={profile.status === "confirmed"} /><div className="skill-list">{profile.skills.length ? profile.skills.slice(0, 12).map((skill, index) => <span key={`${skill.name}-${index}`}>{skill.normalized_name ?? skill.name ?? "未命名技能"}</span>) : <small>模型未从简历中提取到明确技能</small>}</div>{profile.warnings.length > 0 && <p className="profile-warning">{profile.warnings[0]}</p>}{profile.status !== "confirmed" && <button className="secondary-button" disabled={confirmingProfile} onClick={confirmProfile} type="button">{confirmingProfile ? "保存中..." : "确认画像并进入岗位匹配"}<ArrowRight size={15} /></button>}</div>}
        </div>

        <aside className="info-panel">
          <div className="panel-title"><ScanSearch size={17} /><span>你的求职概览</span></div>
          <div className="info-list">
            <div><span>画像状态</span><strong>{profile?.status === "confirmed" ? "已确认" : profile ? "待确认" : upload ? "可生成" : "尚未建立"}</strong></div>
            <div><span>职业方向</span><strong>{analysis ? `${analysis.careers.results.length} 个参考方向` : "确认画像后生成"}</strong></div>
            <div><span>目标岗位</span><strong>{jobCount} / 20</strong></div>
            <div><span>面试状态</span><strong>{interview?.status === "completed" ? "已完成" : interview ? "进行中" : "未开始"}</strong></div>
          </div>
          <div className="model-card">
            <div className="model-card-head"><span className="mini-dot" />模型连接</div>
            {model ? <><strong>{model.model}</strong><span>{model.provider}</span><small>聊天 · {model.chat_configured ? "已配置" : "请在上方输入 API Key"}</small><small>图片识别 · {model.image_ocr}</small><small>岗位匹配 · {model.matching}</small></> : <span className="muted">读取模型配置中</span>}
          </div>
          <div className="workspace-tip"><ShieldCheck size={17} /><p>你始终掌握最终决定权。画像先由你确认，再用于匹配；建议与评分仅作求职参考。</p></div>
        </aside>
      </section>

      {profile?.status === "confirmed" && <section className="analysis-section" id="analysis" aria-labelledby="analysis-title" aria-busy={analyzing}>
        <div className="section-heading"><div><p className="eyebrow">02 / PROFILE & CAREERS</p><h2 id="analysis-title">画像与职业方向</h2></div><span className="stage-tag">已确认的简历证据</span></div>
        {analyzing && <p className="loading-copy" role="status">正在整理画像星图与职业库匹配…</p>}
        {analysisError && <div className="analysis-retry"><div className="notice error" role="alert"><CircleAlert size={16} /><span>{analysisError}</span></div><button className="secondary-button compact" type="button" onClick={() => upload && loadAnalysis(upload.resume_id)} disabled={analyzing}>重新加载分析</button></div>}
        {analysis && <>
          <div className="profile-analysis">
            <div className="analysis-heading"><h3>画像星图</h3><span>简历证据覆盖程度 · 5 星制</span></div>
            <div className="dimension-grid">{analysis.dimensions.map((dimension) => <article className="dimension" key={dimension.name}>
              <div className="dimension-head"><h4>{dimension.name}</h4><StarRating score={dimension.score} label={dimension.name} /></div>
              <p>{dimension.note}</p>
              {dimension.evidence.length > 0 && <details><summary>查看简历依据</summary><ul>{dimension.evidence.map((item, index) => <li key={index}>{item}</li>)}</ul></details>}
            </article>)}</div>
            <p className="analysis-notice">{analysis.notice}</p>
            {upload && <div className="action-row"><button className="secondary-button compact" disabled={exporting} type="button" onClick={() => exportReport("profile", upload.resume_id, "html")}><Download size={15} />下载完整画像报告 HTML</button><button className="secondary-button compact" disabled={exporting} type="button" onClick={() => exportReport("profile", upload.resume_id, "json")}>导出画像 JSON</button></div>}
          </div>
          <div className="career-section">
            <div className="analysis-heading"><div><h3>10 个具体职业参考</h3><p>从职业库连接你的技能与可能的方向。</p></div><span className="stage-tag">{analysis.careers.results.length} 个方向</span></div>
            <div className="career-list">{analysis.careers.results.map((career, index) => <article className="career-row" key={career.code}>
              <span className="career-rank">{String(index + 1).padStart(2, "0")}</span>
              <div className="career-content"><div className="career-title"><h4>{career.title}</h4><span>{career.original_title} · {career.code}</span></div><p className="career-reason">{career.reason}</p><div className="career-skills"><p><b>技能命中</b>{career.matched_skills.join("、") || "暂无明确证据"}</p><p><b>待补充</b>{career.skill_gaps.join("、") || "暂无已识别缺口"}</p></div><details className="career-source"><summary>职业定义与来源</summary><p lang="en">{career.description}</p><a href={career.source_url} target="_blank" rel="noreferrer">查看职业库原始条目 ↗</a></details></div>
              <div className="career-fit"><strong>{Math.round(career.score)}<small>/ 100</small></strong><StarRating score={career.stars} label={`${career.title}匹配证据`} /><span>证据匹配分</span></div>
            </article>)}</div>
            <div className="catalog-note"><strong>{analysis.careers.catalog.name} · {analysis.careers.catalog.version}</strong><p>{analysis.careers.catalog.notice}</p><p>职业库共 {analysis.careers.total} 个条目 · {analysis.careers.catalog.license} · 获取日期 {analysis.careers.catalog.accessed_on}</p><a href={analysis.careers.catalog.source_url} target="_blank" rel="noreferrer">职业库来源 ↗</a><details><summary>评分方法与许可声明</summary><p>{analysis.careers.catalog.scoring_method}</p><p lang="en">{analysis.careers.catalog.attribution}</p></details></div>
          </div>
        </>}
      </section>}

      {profile?.status === "confirmed" && <section className="next-stage" id="jobs">
        <div className="section-heading"><div><p className="eyebrow">03 / TARGET JOBS</p><h2>目标岗位与求职练习</h2></div><span className="stage-tag">{jobCount ? `${jobCount} 个岗位` : "待导入"}</span></div>
        <p className="section-description">这里使用你导入的招聘岗位 JD，单独分析岗位要求，并生成诊断与面试练习。合成样例岗位仅用于功能演示。</p>
        {importedJobs.length > 0 && <details className="job-preview"><summary>已载入 {importedJobs.length} 个岗位，查看岗位与条件</summary><div className="job-table-scroll"><table><thead><tr><th>岗位 / 单位</th><th>地点</th><th>学历要求</th><th>必需技能</th></tr></thead><tbody>{importedJobs.map((job, index) => <tr key={`${job.title}-${index}`}><td>{job.title}<small>{job.company}</small></td><td>{job.location}</td><td>{job.education_required ?? "未注明"}</td><td>{job.required_skills.join("、") || "未注明"}</td></tr>)}</tbody></table></div></details>}
        <p className="field-help">{jobsetId ? "岗位已准备好，可直接开始匹配。也可输入新清单替换：" : "每行一条："}岗位名称 | 公司 | 城市 | 必需技能（逗号分隔）。</p>
        <textarea className="job-input" aria-label="岗位清单" value={jobLines} onChange={(event) => setJobLines(event.target.value)} placeholder="数据分析师 | 示例公司 | 上海 | Python, SQL\n产品运营 | 示例科技 | 杭州 | 用户研究, Excel" rows={5} />
        <div className="action-row"><button className="primary-button compact" disabled={importingJobs} onClick={importJobs} type="button">{importingJobs ? "导入中..." : "导入岗位"}<ArrowRight size={16} /></button>{jobsetId && <button className="secondary-button compact" disabled={matching} onClick={runMatches} type="button">{matching ? "计算中..." : "开始匹配"}<ScanSearch size={15} /></button>}</div>
        {matches.length > 0 && <div className="match-list"><div className="match-list-head"><strong>匹配结果</strong><span>合格岗位优先</span></div>{matches.map((match, index) => <div className="match-row" key={`${match.job_title}-${index}`}><div className="match-rank">{String(index + 1).padStart(2, "0")}</div><div className="match-main"><strong>{match.job_title}</strong><span>{match.company} · {match.location}</span><small>技能 {Math.round(match.score_breakdown.skill_coverage ?? 0)} · 学历 {Math.round(match.score_breakdown.education_match ?? 0)} · 偏好 {Math.round(match.score_breakdown.preference_fit ?? 0)}{match.score_breakdown.semantic_similarity === undefined ? " · 规则匹配" : ` · 语义 ${Math.round(match.score_breakdown.semantic_similarity)}`}</small><small>匹配技能：{match.matched_skills.join("、") || "暂无"}</small><small>{match.skill_gaps.length ? `能力缺口：${match.skill_gaps.join(", ")}` : "已命中必需技能"}</small>{match.hard_fail_reasons.map((reason) => <small className="constraint-warning" key={reason}>{reason}</small>)}{match.evidence && match.evidence.length > 0 && <details className="match-evidence"><summary>查看匹配依据</summary>{match.evidence.map((item) => <p key={item}>{item}</p>)}</details>}<div className="match-actions"><button type="button" disabled={reporting} onClick={() => createDiagnosis(match.job_title)}>{reporting ? "生成中..." : "诊断"}</button><button type="button" disabled={startingInterview} onClick={() => startInterview(match.job_title)}>{startingInterview ? "准备中…" : "面试"}</button></div></div><div className={`match-score ${match.eligible ? "eligible" : "risk"}`}>{Math.round(match.total_score)}<small>{match.eligible ? "匹配" : "风险"}</small></div></div>)}</div>}
        {report && <div className="report-panel">
          <div className="match-list-head"><strong>{report.job_title} · 简历诊断</strong><span>{report.company}</span></div>
          <div className="report-columns">
            <div><b>优势</b>{report.strengths.map((item) => <p key={item}>{item}</p>)}</div>
            <div><b>必须改进</b>{report.must_fix.length ? report.must_fix.map((item) => <p key={item}>{item}</p>) : <p>暂无硬性缺口</p>}</div>
            <div><b>ATS 关键词</b><p>{report.ats_keywords.join("、") || "暂无"}</p></div>
          </div>
          {report.optional_improve.length > 0 && <div className="report-notes"><b>进一步优化</b>{report.optional_improve.map((item) => <p key={item}>{item}</p>)}</div>}
          {report.checklist.length > 0 && <div className="report-checklist"><b>投递前检查</b><ul>{report.checklist.map((item) => <li key={item}><CheckCircle2 size={13} />{item}</li>)}</ul></div>}
          <div className="action-row">
            <button className="secondary-button compact" disabled={exporting} onClick={() => exportReport("diagnosis", report.report_id, "html")} type="button">下载诊断报告 HTML</button>
            <button className="secondary-button compact" disabled={exporting} onClick={() => exportReport("diagnosis", report.report_id, "json")} type="button">导出 JSON</button>
          </div>
        </div>}
        {interview && <div className="interview-panel">
          <div className="match-list-head"><strong>{interview.job_title} · 模拟面试</strong><span>{interview.status === "completed" ? `总分 ${interview.overall_score ?? "-"}/5` : `第 ${interview.turns.length + 1} 题`}</span></div>
          {interview.turns.length > 0 && <div className="interview-turns">{interview.turns.map((turn, index) => <div className="interview-turn" key={index}>
            <div><strong>第 {index + 1} 题</strong><span>{turn.score ?? "-"} / 5</span></div>
            <p>{turn.question}</p><p className="turn-answer">{turn.answer}</p><p className="turn-feedback">反馈：{turn.feedback ?? "暂无反馈"}</p>
          </div>)}</div>}
          {interview.status === "active" ? <>
            <p className="interview-question">{interview.current_question}</p>
            <label className="field-label" htmlFor="interview-answer">你的回答</label><textarea className="job-input" id="interview-answer" value={interviewAnswer} onChange={(event) => setInterviewAnswer(event.target.value)} placeholder="输入你的回答..." rows={4} />
            <button className="primary-button compact" disabled={answering || !interviewAnswer.trim()} onClick={answerCurrentQuestion} type="button">{answering ? "评分中..." : "提交回答"}<ArrowRight size={16} /></button>
          </> : <>
            <div className="interview-summary">{interview.summary.map((item) => <p key={item}>{item}</p>)}</div>
            <div className="action-row">
              <button className="secondary-button compact" disabled={exporting} onClick={() => exportReport("interview", interview.session_id, "html")} type="button">下载面试反馈 HTML</button>
              <button className="secondary-button compact" disabled={exporting} onClick={() => exportReport("interview", interview.session_id, "json")} type="button">导出 JSON</button>
            </div>
          </>}
        </div>}
      </section>}

      <footer><a className="brand footer-brand" href="/"><Compass size={18} /><span>CareerPilot <small>就业罗盘</small></span></a><span>基于简历证据的职业探索工具 · 结果供求职参考</span><a href="/privacy">隐私与数据处理说明 <ArrowRight size={13} /></a></footer>
    </main>
  );
}

