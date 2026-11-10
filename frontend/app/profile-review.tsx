"use client";

type RecordValue = Record<string, unknown>;
const groups = [
  { key: "education", title: "教育经历", fields: [["school", "学校"], ["degree", "学历"], ["major", "专业"], ["graduation_year", "毕业时间"]] },
  { key: "experiences", title: "实践经历", fields: [["company", "单位"], ["role", "职责或岗位"], ["period", "时间"], ["responsibilities", "具体做过的事"]] },
  { key: "projects", title: "项目经历", fields: [["name", "项目名称"], ["role", "个人职责"], ["period", "时间"], ["results", "可核对的结果"]] },
] as const;

export default function ProfileReview({ profile, onChange, disabled }: {
  profile: { education: RecordValue[]; experiences: RecordValue[]; projects: RecordValue[]; preferences: RecordValue };
  onChange: (key: "education" | "experiences" | "projects" | "preferences", value: RecordValue[] | RecordValue) => void;
  disabled: boolean;
}) {
  return <details className="profile-review"><summary>核对教育、经历和求职偏好</summary><p className="field-help">保留事实，修正识别错误。修改内容仍需由你确认，原文没有的部分不会自动变成评分证据。</p>
    {groups.map((group) => <section key={group.key}><h3>{group.title}</h3>{profile[group.key].length === 0 ? <p className="muted">未提取到明确记录。</p> : profile[group.key].map((record, index) => <fieldset key={index} disabled={disabled}><legend>{group.title} {index + 1}</legend><div className="review-fields">{group.fields.map(([field, label]) => {
      const value = record[field];
      const display = Array.isArray(value) ? value.join("；") : typeof value === "string" || typeof value === "number" ? String(value) : "";
      return <label key={field}>{label}<input className="text-input" value={display} maxLength={2000} onChange={(event) => onChange(group.key, profile[group.key].map((item, itemIndex) => itemIndex === index ? { ...item, [field]: Array.isArray(value) ? event.target.value.split("；").filter(Boolean) : event.target.value } : item))} /></label>;
    })}</div></fieldset>)}</section>)}
    <section><h3>求职偏好</h3><div className="review-fields">{[["cities", "意向城市"], ["roles", "意向岗位"]].map(([key, label]) => <label key={key}>{label}<input className="text-input" disabled={disabled} value={Array.isArray(profile.preferences[key]) ? profile.preferences[key].join("、") : ""} onChange={(event) => onChange("preferences", { ...profile.preferences, [key]: event.target.value.split(/[,，、]/).map((item) => item.trim()).filter(Boolean) })} /></label>)}</div></section>
  </details>;
}
