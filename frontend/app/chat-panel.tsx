"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { ArrowRight, CircleAlert } from "lucide-react";

type Message = { role: "user" | "assistant"; content: string };

export default function ChatPanel({ apiBase, connected, ready, onConnect }: {
  apiBase: string;
  connected: boolean;
  ready: boolean;
  onConnect: () => void;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const log = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (log.current) log.current.scrollTop = log.current.scrollHeight;
  }, [messages]);

  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = draft.trim();
    if (!ready || !connected || sending || !content) return;
    const question: Message = { role: "user", content };
    const context = [...messages.slice(-20), question];
    while (context.reduce((length, message) => length + message.content.length, 0) > 24000 && context.length > 1) {
      context.splice(0, 2);
    }
    setSending(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/chat`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: context }),
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "暂时无法回复，请稍后重试。");
      if (typeof data?.reply !== "string" || !data.reply.trim()) throw new Error("模型没有返回可用内容，请重试。");
      const answer: Message = { role: "assistant", content: data.reply };
      setMessages((previous) => [...previous, question, answer].slice(-100));
      setDraft("");
    } catch (failure) {
      setError(failure instanceof TypeError ? "网络连接中断，请稍后重试。" : failure instanceof Error ? failure.message : "发送失败，请稍后重试。");
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="chat-section" id="chat" aria-labelledby="chat-title" aria-busy={sending}>
      <div className="section-heading"><h2 id="chat-title">直接聊天</h2><span className="stage-tag">无需上传简历</span></div>
      <p className="section-description">职业方向、岗位选择、面试准备，都可以直接问。</p>
      {!connected && <div className="chat-connection"><p>先连接千问，再发送问题。聊天不需要提交简历。</p><button className="secondary-button compact" type="button" onClick={onConnect}>连接千问<ArrowRight size={14} /></button></div>}
      {messages.length > 0 && <div className="chat-messages" ref={log} role="log" aria-label="聊天记录" aria-live="polite" aria-relevant="additions text">
        {messages.map((message, index) => <article className={`chat-message ${message.role}`} key={index}><span>{message.role === "user" ? "你" : "千问"}</span><p>{message.content}</p></article>)}
      </div>}
      <form onSubmit={send}>
        <label className="field-label" htmlFor="chat-message">想聊什么</label>
        <textarea className="job-input chat-input" id="chat-message" value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="例如：没有实习经历，面试时该怎么介绍自己？" maxLength={4000} rows={3} disabled={sending} aria-describedby="chat-privacy" required />
        <p className="chat-privacy" id="chat-privacy">发送的内容会交给阿里云处理；对话仅保留在本页，刷新或清空后移除。请避免填写电话、证件号等信息。<a href="/privacy">聊天数据说明</a></p>
        <div className="chat-actions"><button className="primary-button compact" type="submit" disabled={!ready || !connected || sending || !draft.trim()}>{sending ? "正在回复…" : "发送"}<ArrowRight size={15} /></button>{messages.length > 0 && <button className="secondary-button compact" type="button" disabled={sending} onClick={() => { setMessages([]); setDraft(""); setError(""); }}>清空对话</button>}{sending && <span className="chat-pending" role="status">千问正在回复，请稍候。</span>}</div>
      </form>
      {error && <div className="notice error" role="alert"><CircleAlert size={16} /><span>{error}</span></div>}
    </section>
  );
}
