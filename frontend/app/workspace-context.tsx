"use client";

import { useState, type ReactNode } from "react";
import { PanelRightClose, PanelRightOpen } from "lucide-react";

export default function WorkspaceContext({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  return <aside className={`context-panel ${collapsed ? "is-collapsed" : ""}`} aria-label="本次工作记录">
    <div className="context-heading">
      <span>本次工作</span>
      <button type="button" className="icon-button" aria-label={collapsed ? "展开工作记录" : "收起工作记录"} aria-expanded={!collapsed} aria-controls="context-content" onClick={() => setCollapsed(!collapsed)}>
        {collapsed ? <PanelRightOpen size={18} /> : <PanelRightClose size={18} />}
      </button>
    </div>
    <div id="context-content" hidden={collapsed}>{children}</div>
  </aside>;
}
