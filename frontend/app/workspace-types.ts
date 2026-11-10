export type Orchestration = {
  backend: "legacy" | "dify";
  workflows: Record<string, boolean>;
  agents: Record<string, string>;
  media_enabled: boolean;
  media_capabilities?: { image: boolean; video: boolean };
};

export type DiagnosticReport = {
  report_id: string;
  job_title: string;
  company: string;
  strengths: string[];
  must_fix: string[];
  optional_improve: string[];
  ats_keywords: string[];
  checklist: string[];
  engine?: "rules" | "model";
};

export type InterviewSession = {
  session_id: string;
  job_title: string;
  status: "active" | "completed";
  current_question?: string;
  turns: Array<{ question: string; answer?: string; score?: number; feedback?: string }>;
  overall_score?: number;
  summary: string[];
  summary_pending?: boolean;
};
