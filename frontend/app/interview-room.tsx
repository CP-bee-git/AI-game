"use client";

import { useEffect, useRef } from "react";
import { ArrowRight } from "lucide-react";
import type { InterviewSession } from "./workspace-types";

export default function InterviewRoom({ interview, answer, answering, exporting, retrying, onAnswer, onSubmit, onRetry, onExport }: {
  interview: InterviewSession;
  answer: string;
  answering: boolean;
  exporting: boolean;
  retrying: boolean;
  onAnswer: (value: string) => void;
  onSubmit: () => void;
  onRetry: () => void;
  onExport: (format: "html" | "json") => void;
}) {
  const input = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (interview.status === "active") input.current?.focus({ preventScroll: true });
  }, [interview.session_id, interview.turns.length, interview.status]);
  return <section className="interview-panel" id="interview" aria-labelledby="interview-title" aria-busy={answering || retrying}>
    <header className="document-heading"><div><p className="page-label">练习室 / 一题一答</p><h2 id="interview-title">{interview.job_title} · 模拟面试</h2></div><span className="stage-tag">{interview.status === "completed" ? `平均评分 ${interview.overall_score ?? "-"}/5` : `第 ${interview.turns.length + 1} 题`}</span></header>
    {interview.status === "active" && <div className="interview-workspace">
      <div className="interview-prompt"><p className="page-label">当前问题</p><p className="interview-question">{interview.current_question}</p><p className="muted">说清背景、你做了什么、结果如何。没有做过的部分可以直接说明。</p></div>
      <form onSubmit={(event) => { event.preventDefault(); onSubmit(); }}><label className="field-label" htmlFor="interview-answer">你的回答</label><textarea ref={input} className="job-input" id="interview-answer" value={answer} onChange={(event) => onAnswer(event.target.value)} placeholder="从一个具体的经历讲起…" rows={7} maxLength={10000} disabled={answering} required /><div className="answer-footer"><small>{answer.length} / 10000</small><button className="primary-button compact" disabled={answering || !answer.trim()} type="submit">{answering ? "正在评分…" : "提交回答"}<ArrowRight size={15} /></button></div></form>
    </div>}
    {interview.turns.length > 0 && <div className="interview-turns" aria-label="回答与反馈记录">{interview.turns.map((turn, index) => <article className="interview-turn" key={index}><div><strong>第 {index + 1} 题</strong><span>{turn.score ?? "-"} / 5</span></div><p>{turn.question}</p><details><summary>查看我的回答</summary><p className="turn-answer">{turn.answer}</p></details><p className="turn-feedback">反馈：{turn.feedback ?? "暂无反馈"}</p></article>)}</div>}
    {interview.status === "completed" && <><div className="interview-summary"><h3>本次复盘</h3>{interview.summary.map((item) => <p key={item}>{item}</p>)}</div>{interview.summary_pending && <button type="button" className="secondary-button compact" disabled={retrying} onClick={onRetry}>{retrying ? "正在生成复盘…" : "重新生成复盘"}</button>}<div className="action-row"><button className="secondary-button compact" disabled={exporting} onClick={() => onExport("html")} type="button">下载面试反馈 HTML</button><button className="secondary-button compact" disabled={exporting} onClick={() => onExport("json")} type="button">导出 JSON</button></div></>}
  </section>;
}
