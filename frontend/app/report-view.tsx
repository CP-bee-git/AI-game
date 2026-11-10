import { CheckCircle2, Download } from "lucide-react";
import type { DiagnosticReport } from "./workspace-types";

export default function ReportView({ report, exporting, onExport }: {
  report: DiagnosticReport;
  exporting: boolean;
  onExport: (format: "html" | "json") => void;
}) {
  return <article className="report-panel document-view" id="report" aria-labelledby="report-title">
    <header className="document-heading"><div><p className="page-label">求职笔记 / 简历诊断</p><h2 id="report-title">{report.job_title}</h2><p>{report.company}</p></div><span className="stage-tag">{report.engine === "rules" ? "规则示例" : "修改建议"}</span></header>
    <div className="document-layout">
      <div className="document-body">
        <section><h3>已经写清楚的部分</h3>{report.strengths.map((item) => <p key={item}>{item}</p>)}</section>
        <section><h3>需要核对的部分</h3>{report.must_fix.length ? report.must_fix.map((item) => <p key={item}>{item}</p>) : <p>当前没有明确的待核对项，请继续对照原始经历检查。</p>}</section>
        {report.optional_improve.length > 0 && <section className="report-notes"><h3>可以这样修改</h3><ol>{report.optional_improve.map((item) => <li key={item}>{item}</li>)}</ol></section>}
      </div>
      <aside className="document-margin" aria-label="岗位关键词与投递检查">
        <h3>岗位关键词</h3><div className="skill-list">{report.ats_keywords.length ? report.ats_keywords.map((keyword) => <span key={keyword}>{keyword}</span>) : <p>暂无关键词</p>}</div>
        {report.checklist.length > 0 && <div className="report-checklist"><h3>投递前检查</h3><ul>{report.checklist.map((item) => <li key={item}><CheckCircle2 size={14} />{item}</li>)}</ul></div>}
      </aside>
    </div>
    <div className="action-row"><button className="secondary-button compact" disabled={exporting} onClick={() => onExport("html")} type="button"><Download size={15} />下载诊断报告 HTML</button><button className="secondary-button compact" disabled={exporting} onClick={() => onExport("json")} type="button">导出 JSON</button></div>
  </article>;
}
