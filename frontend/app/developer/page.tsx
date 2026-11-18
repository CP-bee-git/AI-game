"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ArrowRight, Download, Globe, Loader2, RefreshCw } from "lucide-react";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";

type ScenarioType = "job_search" | "interview" | "competition";

type RunRecord = {
  run_id: string;
  status: string;
  scenario?: Record<string, unknown>;
  retrieval?: { status?: string; searched_at?: string | null };
  evidence?: { evidence_status?: string; verified_facts?: Array<{ text: string; source_ids: string[]; quote?: string }>; conflicts?: string[]; missing_information?: string[] };
  strategy?: { summary?: string; priorities?: Array<{ action: string; deliverable?: string; check?: string; priority?: number }>; plan?: string[]; practice_questions?: Array<{ question: string; kind?: string; purpose?: string }>; uncertainties?: string[] };
  sources?: Array<{ id: string; title: string; url: string; fetched_at?: string; kind?: string }>;
  clarification?: Array<{ field: string; question: string }>;
  error?: string;
  warnings?: string[];
};

const typeOptions: Array<{ value: ScenarioType; label: string }> = [
  { value: "job_search", label: "求职" },
  { value: "interview", label: "面试" },
  { value: "competition", label: "比赛" },
];

const statusText: Record<string, string> = {
  queued: "排队中", searching: "联网查证中", generating: "生成攻略中", reviewing: "事实复核中",
  completed: "已完成", needs_clarification: "需要补充信息", failed: "未完成", partial: "部分完成",
};

function requestId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID().replace(/-/g, "").slice(0, 24)
    : `req-${Date.now()}`;
}

export default function DeveloperWorkbench() {
  const [type, setType] = useState<ScenarioType>("interview");
  const [targetName, setTargetName] = useState("");
  const [yearOrEdition, setYearOrEdition] = useState("");
  const [roleOrTrack, setRoleOrTrack] = useState("");
  const [stage, setStage] = useState("");
  const [goal, setGoal] = useState("");
  const [officialUrls, setOfficialUrls] = useState("");
  const [preparationDays, setPreparationDays] = useState("");
  const [dailyMinutes, setDailyMinutes] = useState("");
  const [background, setBackground] = useState("");
  const [generalMode, setGeneralMode] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [run, setRun] = useState<RunRecord | null>(null);
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const requestIdRef = useRef<string>(requestId());

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  async function poll(runId: string) {
    try {
      const response = await fetch(`${apiBase}/scenario-runs/${runId}`, { credentials: "same-origin", cache: "no-store" });
      if (!response.ok) return;
      const data: RunRecord = await response.json();
      setRun(data);
      if (!["queued", "searching", "generating", "reviewing"].includes(data.status)) stopPolling();
    } catch { /* keep polling */ }
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setRun(null);
    stopPolling();
    try {
      const payload = {
        request_id: requestIdRef.current,
        type,
        target_name: targetName.trim(),
        year_or_edition: yearOrEdition.trim(),
        role_or_track: roleOrTrack.trim(),
        stage: stage.trim(),
        goal: goal.trim(),
        official_urls: officialUrls.split(/\n+/).map((line) => line.trim()).filter(Boolean).slice(0, 5),
        preparation_days: preparationDays ? Number(preparationDays) : null,
        daily_minutes: dailyMinutes ? Number(dailyMinutes) : null,
        background_summary: background.trim(),
        general_mode: generalMode,
      };
      const response = await fetch(`${apiBase}/scenario-runs`, {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "提交失败，请检查输入。");
      requestIdRef.current = requestId();
      setRun({ run_id: data.run_id, status: data.status });
      pollRef.current = setInterval(() => void poll(data.run_id), 2000);
      void poll(data.run_id);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "提交失败。");
    } finally {
      setSubmitting(false);
    }
  }

  async function exportStrategy(format: "html" | "json") {
    if (!run) return;
    setExporting(true);
    try {
      const response = await fetch(`${apiBase}/exports`, {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type: "scenario", resource_id: run.run_id, format }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "导出失败");
      const url = URL.createObjectURL(new Blob([data.content], { type: data.content_type }));
      const link = document.createElement("a");
      link.href = url;
      link.download = data.filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "导出失败。");
    } finally {
      setExporting(false);
    }
  }

  const busy = submitting || (run ? ["queued", "searching", "generating", "reviewing"].includes(run.status) : false);

  return (
    <div className="dev-page">
      <header className="dev-topbar">
        <div>
          <p className="dev-kicker">就业罗盘 / 开发者工作台</p>
          <h1>为一个明确目标，准备下一次表现。</h1>
          <p className="dev-sub">技术求职、面试与比赛：确认场景 → 联网查证 → 行动攻略</p>
        </div>
        <Link className="dev-back" href="/"><ArrowLeft size={15} />返回求职工作台</Link>
      </header>
      <nav className="dev-docs-nav" aria-label="开发者资料">
        <Link href="/developer/docs">数据库总览与规则引擎 <ArrowRight size={14} /></Link>
        <Link href="/privacy">数据与隐私说明 <ArrowRight size={14} /></Link>
      </nav>
      <div className="dev-grid">
        <section className="dev-panel" aria-label="场景定制">
          <h2>场景定制</h2>
          <div className="dev-types" role="tablist" aria-label="场景类型">
            {typeOptions.map((option) => (
              <button key={option.value} type="button" role="tab" aria-selected={type === option.value}
                className={type === option.value ? "active" : ""} onClick={() => setType(option.value)}>
                {option.label}
              </button>
            ))}
          </div>
          <form onSubmit={submit} className="dev-form">
            <label className="dev-check"><input type="checkbox" checked={generalMode} onChange={(event) => setGeneralMode(event.target.checked)} /> 通用训练（不定位具体公司 / 届次）</label>
            {!generalMode && (
              <>
                <label>目标公司 / 比赛全称<input value={targetName} onChange={(event) => setTargetName(event.target.value)} placeholder={type === "competition" ? "例如：蓝桥杯全国软件和信息技术专业人才大赛" : "例如：某公司（以官方名称为准）"} /></label>
                <label>年份 / 届次<input value={yearOrEdition} onChange={(event) => setYearOrEdition(event.target.value)} placeholder={type === "competition" ? "例如：第十六届 / 2026" : "例如：2026 届校招"} /></label>
              </>
            )}
            <label>{type === "competition" ? "赛道 / 组别" : "岗位"}<input value={roleOrTrack} onChange={(event) => setRoleOrTrack(event.target.value)} placeholder={type === "competition" ? "例如：Web 应用开发赛道" : "例如：后端开发工程师"} /></label>
            <label>{type === "competition" ? "比赛阶段 / 目标" : "面试环节"}<input value={stage} onChange={(event) => setStage(event.target.value)} placeholder={type === "competition" ? "例如：作品提交 / 现场答辩" : "例如：技术一面"} /></label>
            <label>我想解决的问题<textarea value={goal} onChange={(event) => setGoal(event.target.value)} rows={2} placeholder="例如：准备一个能突出个人贡献的项目讲解" /></label>
            <label>官方链接（可选，每行一个）<textarea value={officialUrls} onChange={(event) => setOfficialUrls(event.target.value)} rows={2} placeholder="https://…" /></label>
            <div className="dev-row">
              <label>准备天数<input type="number" min={1} max={365} value={preparationDays} onChange={(event) => setPreparationDays(event.target.value)} /></label>
              <label>每天可用分钟<input type="number" min={5} max={1440} value={dailyMinutes} onChange={(event) => setDailyMinutes(event.target.value)} /></label>
            </div>
            <label>我的基础（可选）<textarea value={background} onChange={(event) => setBackground(event.target.value)} rows={2} placeholder="例如：掌握 Python，有一个课程项目" /></label>
            <button className="dev-submit" type="submit" disabled={busy ?? false}>
              {busy ? <Loader2 size={16} className="spin" /> : <Globe size={16} />}
              {busy ? "正在处理…" : "生成专属攻略"}
            </button>
            {error && <p className="dev-error" role="alert">{error}</p>}
          </form>
        </section>
        <section className="dev-panel dev-result" aria-label="攻略文档" aria-live="polite">
          {!run && <div className="dev-empty"><h2>攻略文档</h2><p>填写左侧场景后生成。结果会区分“已查证”的官方信息、通用建议与待确认项，并附可点击来源。</p></div>}
          {run && (
            <>
              <div className="dev-status-row">
                <span className={`dev-status status-${run.status}`}>{statusText[run.status] ?? run.status}</span>
                {run.retrieval?.searched_at && <span className="dev-muted">检索时间 {run.retrieval.searched_at}</span>}
                {busy ? <RefreshCw size={14} className="spin" /> : null}
              </div>
              {run.error && <p className="dev-error">{run.error}</p>}
              {run.warnings?.map((warning) => <p className="dev-warn" key={warning}>{warning}</p>)}
              {run.status === "needs_clarification" && (
                <div className="dev-block"><h3>需要补充的信息</h3><ul>{run.clarification?.map((item) => <li key={item.field}>{item.question}</li>)}</ul></div>
              )}
              {run.strategy?.summary && <div className="dev-block"><h3>场景摘要</h3><p>{run.strategy.summary}</p></div>}
              {!!run.evidence?.verified_facts?.length && (
                <div className="dev-block"><h3>已查证要求</h3>
                  {run.evidence.verified_facts?.map((fact, index) => (
                    <div className="dev-fact" key={index}><p>{fact.text}</p>
                      {fact.quote && <blockquote>{fact.quote}</blockquote>}
                      <span className="dev-muted">来源 {fact.source_ids.join("、")}</span></div>
                  ))}
                </div>
              )}
              {!!run.strategy?.priorities?.length && (
                <div className="dev-block"><h3>优先动作</h3>
                  <ol>{run.strategy.priorities?.map((item, index) => (
                    <li key={index}><b>{item.action}</b>
                      <p className="dev-muted">产出：{item.deliverable || "—"} · 自查：{item.check || "—"}</p></li>
                  ))}</ol>
                </div>
              )}
              {!!run.strategy?.plan?.length && <div className="dev-block"><h3>阶段计划</h3><ul>{run.strategy.plan?.map((item, index) => <li key={index}>{item}</li>)}</ul></div>}
              {!!run.strategy?.practice_questions?.length && (
                <div className="dev-block"><h3>练习问题</h3>
                  <ul>{run.strategy.practice_questions?.map((q, index) => (
                    <li key={index}>{q.question} <span className="dev-tag">{q.kind === "publicly_documented" ? "公开真题" : "预测题"}</span></li>
                  ))}</ul>
                </div>
              )}
              {!!run.strategy?.uncertainties?.length && <div className="dev-block"><h3>不确定与待确认</h3><ul>{run.strategy.uncertainties?.map((item, index) => <li key={index}>{item}</li>)}</ul></div>}
              {!!run.sources?.length && (
                <div className="dev-block"><h3>资料来源</h3>
                  <ul className="dev-sources">{run.sources?.map((source) => (
                    <li key={source.id}>[{source.id}] <a href={source.url} target="_blank" rel="noreferrer">{source.title || source.url} ↗</a>
                      <span className="dev-muted"> {source.fetched_at}</span></li>
                  ))}</ul>
                </div>
              )}
              {run.status === "completed" && (
                <div className="dev-actions">
                  <Link className="dev-link" href="/#interview">开始练习 <ArrowRight size={14} /></Link>
                  <Link className="dev-link" href="/#report">查看简历提升指南 <ArrowRight size={14} /></Link>
                  <button type="button" className="dev-export" disabled={exporting} onClick={() => void exportStrategy("html")}><Download size={14} />导出攻略</button>
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </div>
  );
}
