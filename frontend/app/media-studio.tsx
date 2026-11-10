"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowRight, CircleAlert, ImagePlus, Video } from "lucide-react";
import type { Orchestration } from "./workspace-types";

type Task = { task_id: string; request_id: string; kind: "image" | "video"; status: string; urls: string[] };
const labels: Record<string, string> = { submitting: "正在提交", queued: "排队中", running: "生成中", succeeded: "已完成", failed: "生成失败", unknown: "结果待核对" };

export default function MediaStudio({ apiBase, service }: { apiBase: string; service: Orchestration | null }) {
  const [kind, setKind] = useState<"image" | "video">("image");
  const [prompt, setPrompt] = useState("");
  const [consent, setConsent] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [task, setTask] = useState<Task | null>(null);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const requestId = useRef<string | null>(null);
  const [pollSequence, setPollSequence] = useState(0);
  const enabled = service?.backend === "dify" && service.media_enabled && Boolean(service.media_capabilities?.[kind]);

  async function refresh(signal?: AbortSignal) {
    if (!task) return;
    setRefreshing(true);
    try {
      const response = await fetch(`${apiBase}/media/${task.task_id}`, { signal, credentials: "same-origin", cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "任务状态暂时无法读取。");
      setTask(data);
      setError("");
    } catch (failure) {
      if (!signal?.aborted) setError(failure instanceof Error ? failure.message : "任务状态读取失败。");
    } finally {
      if (!signal?.aborted) { setRefreshing(false); setPollSequence((value) => value + 1); }
    }
  }

  useEffect(() => {
    if (!task || !["queued", "running"].includes(task.status)) return;
    const controller = new AbortController();
    const timer = setTimeout(() => { void refresh(controller.signal); }, error ? 15000 : 5000);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [task, pollSequence]);

  async function submit() {
    if (!enabled || !consent || prompt.trim().length < 5 || submitting) return;
    requestId.current ??= crypto.randomUUID();
    setSubmitting(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/media`, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kind, prompt: prompt.trim(), consent: true, request_id: requestId.current }) });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "提交失败，请先核对原任务再重试。");
      setTask(data);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "提交失败。同一内容重试将沿用任务编号。");
    } finally {
      setSubmitting(false);
    }
  }

  function resetRequest() { requestId.current = null; setTask(null); }
  return <section className="media-studio" id="media" aria-labelledby="media-title" aria-busy={submitting}>
    <div className="section-heading"><div><p className="page-label">职业表达 / 可选工具</p><h2 id="media-title">把工作场景，变成一幅画</h2></div><span className="stage-tag">{enabled ? "按需生成" : "尚未启用"}</span></div>
    <p className="section-description">为职业介绍准备场景插图或短片。生成内容用于表达职业想象，请勿作为真实工作经历的证明。</p>
    {!enabled && <p className="media-unavailable">图片与视频需要独立开通豆包服务。当前百炼连接支持评分和报告，尚未接通豆包生成；这里不会发起收费任务。</p>}
    <form onSubmit={(event) => { event.preventDefault(); void submit(); }}>
      <div className="media-kind" role="group" aria-label="生成类型">{(["image", "video"] as const).map((value) => <button key={value} type="button" className={kind === value ? "selected" : ""} aria-pressed={kind === value} disabled={submitting} onClick={() => { setKind(value); resetRequest(); }}>{value === "image" ? <ImagePlus size={16} /> : <Video size={16} />}{value === "image" ? "场景插图" : "职业短片"}</button>)}</div>
      <label className="field-label" htmlFor="media-prompt">描述你想呈现的场景</label><textarea id="media-prompt" className="job-input" rows={3} maxLength={2000} minLength={5} value={prompt} onChange={(event) => { setPrompt(event.target.value); resetRequest(); }} disabled={!enabled || submitting} placeholder="例如：一位数据分析师在明亮的办公室里核对报表，画面简洁，不出现公司标识。" required />
      {enabled && <label className="privacy-consent"><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} disabled={submitting} /><span>我同意把这段描述交给豆包处理，并了解生成会消耗管理员配置的云额度。</span></label>}
      <button className="primary-button compact" type="submit" disabled={!enabled || !consent || prompt.trim().length < 5 || submitting}>{submitting ? "正在提交…" : "生成内容"}<ArrowRight size={15} /></button>
    </form>
    {error && <div className="notice error" role="alert"><CircleAlert size={16} /><span>{error}</span></div>}
    {task && <div className="media-result"><p role="status">{labels[task.status] ?? "状态待核对"} · {task.kind === "image" ? "场景插图" : "职业短片"}</p>{task.urls.filter((url) => url.startsWith("https://")).map((url) => task.kind === "video" ? <video key={url} src={url} controls preload="metadata" aria-label="生成的职业短片" /> : <a key={url} href={url} target="_blank" rel="noreferrer"><img src={url} alt="根据描述生成的职业场景插图" loading="lazy" /></a>)}{task.status !== "succeeded" && <button className="secondary-button compact" type="button" disabled={refreshing} onClick={() => { void refresh(); }}>{refreshing ? "正在查询…" : "查询任务状态"}</button>}<small>由豆包生成。结果链接可能过期，请及时保存。状态不明时先查询，不要重复创建任务。</small></div>}
  </section>;
}
