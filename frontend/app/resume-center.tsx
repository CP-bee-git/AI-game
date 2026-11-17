"use client";

import { useState } from "react";
import { ArrowRight, Download, FileText, Loader2, Sparkles, Wand2 } from "lucide-react";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";

type Guidance = {
  guidance_id: string;
  priorities: Array<{ section: string; problem: string; reason: string; action: string; question_to_user?: string | null }>;
  strengths: string[];
  improvement_guide: string[];
  submission_checklist: string[];
  stale_notice?: string;
};

type Rewrite = {
  block_id: string; original: string; suggested: string; reason: string;
  missing_information: string[]; questions: string[];
};

type DraftSection = { key: string; title: string; items: Array<{ heading?: string; lines: string[] }> };

type Draft = {
  draft_id: string;
  name_line: string; contact_line: string; objective: string;
  sections: DraftSection[];
  missing_information: string[];
  placeholders: string[];
  draft_status: string;
  stale_notice?: string;
};

type Props = {
  resumeId: string;
  sourceRevision: string;
  jobTitle?: string;
  blocks: Array<{ block_id: string; text: string }>;
};

export default function ResumeCenter({ resumeId, sourceRevision, jobTitle, blocks }: Props) {
  const [guidance, setGuidance] = useState<Guidance | null>(null);
  const [rewrites, setRewrites] = useState<Rewrite[]>([]);
  const [accepted, setAccepted] = useState<Record<string, boolean>>({});
  const [draft, setDraft] = useState<Draft | null>(null);
  const [template, setTemplate] = useState<"campus" | "social">("campus");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  async function post(path: string, body: Record<string, unknown>) {
    const response = await fetch(`${apiBase}${path}`, {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "操作失败，请稍后重试。");
    return data;
  }

  async function runGuidance() {
    setBusy("guidance"); setError("");
    try {
      setGuidance(await post("/resume-guidance", { resume_id: resumeId, source_revision: sourceRevision, job_title: jobTitle ?? "" }));
    } catch (failure) { setError(failure instanceof Error ? failure.message : "生成失败"); }
    finally { setBusy(""); }
  }

  async function runRewrite() {
    setBusy("rewrite"); setError(""); setAccepted({});
    try {
      const ids = blocks.filter((block) => block.text.trim().length >= 8).slice(0, 6).map((block) => block.block_id);
      const data = await post("/resume-rewrites", { resume_id: resumeId, source_revision: sourceRevision, block_ids: ids, job_title: jobTitle ?? "" });
      setRewrites(data.rewrites);
    } catch (failure) { setError(failure instanceof Error ? failure.message : "生成失败"); }
    finally { setBusy(""); }
  }

  async function runDraft() {
    setBusy("draft"); setError("");
    try {
      setDraft(await post("/resume-drafts", { resume_id: resumeId, source_revision: sourceRevision, template, job_title: jobTitle ?? "" }));
    } catch (failure) { setError(failure instanceof Error ? failure.message : "生成失败"); }
    finally { setBusy(""); }
  }

  async function exportDraft() {
    if (!draft) return;
    setBusy("export"); setError("");
    try {
      const data = await post("/exports", { type: "resume_draft", resource_id: draft.draft_id, format: "html" });
      const url = URL.createObjectURL(new Blob([data.content], { type: data.content_type }));
      const link = document.createElement("a");
      link.href = url; link.download = data.filename;
      document.body.appendChild(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (failure) { setError(failure instanceof Error ? failure.message : "导出失败"); }
    finally { setBusy(""); }
  }

  return (
    <section className="resume-center" id="resume-center" aria-label="简历中心">
      <div className="resume-center-head">
        <h2><Sparkles size={17} /> 简历中心</h2>
        <p>基于已确认的事实生成指导、润色与可导出草稿；不会替你编造经历。</p>
      </div>
      <div className="resume-center-actions">
        <button type="button" className="secondary-button" disabled={!!busy} onClick={runGuidance}>
          {busy === "guidance" ? <Loader2 size={15} className="spin" /> : <FileText size={15} />}提升指南
        </button>
        <button type="button" className="secondary-button" disabled={!!busy} onClick={runRewrite}>
          {busy === "rewrite" ? <Loader2 size={15} className="spin" /> : <Wand2 size={15} />}段落润色对照
        </button>
        <label className="template-picker">模板
          <select value={template} onChange={(event) => setTemplate(event.target.value as "campus" | "social")}>
            <option value="campus">技术校招</option>
            <option value="social">技术社招</option>
          </select>
        </label>
        <button type="button" className="primary-button compact" disabled={!!busy} onClick={runDraft}>
          {busy === "draft" ? <Loader2 size={15} className="spin" /> : <ArrowRight size={15} />}生成简历草稿
        </button>
      </div>
      {error && <p className="dev-error" role="alert">{error}</p>}

      {guidance && (
        <div className="resume-block">
          {guidance.stale_notice && <p className="dev-warn">{guidance.stale_notice}</p>}
          {!!guidance.priorities.length && <div className="resume-block-section"><h3>优先改进</h3>
            {guidance.priorities.map((item, index) => (
              <div className="guidance-item" key={index}>
                <b>{item.section}：{item.problem}</b>
                <p>{item.reason}</p>
                <p className="guidance-action">建议：{item.action}</p>
                {item.question_to_user && <p className="dev-muted">需要你确认：{item.question_to_user}</p>}
              </div>
            ))}
          </div>}
          {!!guidance.strengths.length && <div className="resume-block-section"><h3>已有优势</h3><ul>{guidance.strengths.map((item, index) => <li key={index}>{item}</li>)}</ul></div>}
          {!!guidance.improvement_guide.length && <div className="resume-block-section"><h3>整理步骤</h3><ul>{guidance.improvement_guide.map((item, index) => <li key={index}>{item}</li>)}</ul></div>}
          {!!guidance.submission_checklist.length && <div className="resume-block-section"><h3>投递前检查</h3><ul>{guidance.submission_checklist.map((item, index) => <li key={index}>{item}</li>)}</ul></div>}
        </div>
      )}

      {!!rewrites.length && (
        <div className="resume-block">
          <h3>润色对照（逐条采纳，不覆盖原文）</h3>
          {rewrites.map((item) => (
            <div className="rewrite-item" key={item.block_id}>
              <div className="rewrite-columns">
                <div><span className="rewrite-label">原文</span><p>{item.original}</p></div>
                <div><span className="rewrite-label">建议改写</span><p>{item.suggested}</p></div>
              </div>
              <p className="dev-muted">{item.reason}</p>
              {!!item.questions.length && <p className="dev-muted">待确认：{item.questions.join("；")}</p>}
              <div className="rewrite-actions">
                <button type="button" className={accepted[item.block_id] ? "dev-tag" : "secondary-button compact"}
                  onClick={() => setAccepted((previous) => ({ ...previous, [item.block_id]: !previous[item.block_id] }))}>
                  {accepted[item.block_id] ? "已采纳（点击撤销）" : "采纳此条"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {draft && (
        <div className="resume-block">
          {draft.stale_notice && <p className="dev-warn">{draft.stale_notice}</p>}
          <div className="draft-preview" aria-label="简历草稿预览">
            <div className="draft-head"><b>{draft.name_line}</b><span>{draft.contact_line}</span></div>
            {draft.objective && <p className="draft-objective">{draft.objective}</p>}
            {draft.sections.map((section) => (
              <div className="draft-section" key={section.key}>
                <h4>{section.title}</h4>
                {section.items.map((item, index) => (
                  <div className="draft-item" key={index}>
                    {item.heading && <b>{item.heading}</b>}
                    <ul>{item.lines.map((line, lineIndex) => <li key={lineIndex}>{line.includes("[需本人补充真实信息]") ? <mark>{line}</mark> : line}</li>)}</ul>
                  </div>
                ))}
              </div>
            ))}
          </div>
          {!!draft.missing_information.length && (
            <p className="dev-warn">待补充：{draft.missing_information.join("；")}</p>
          )}
          <div className="resume-center-actions">
            <button type="button" className="primary-button compact" disabled={!!busy} onClick={exportDraft}>
              {busy === "export" ? <Loader2 size={15} className="spin" /> : <Download size={15} />}
              {draft.placeholders.length ? "导出草稿（含待补充项）" : "导出简历 HTML / 打印 PDF"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
