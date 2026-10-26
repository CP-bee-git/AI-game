from uuid import UUID


def build_diagnosis(report_id: UUID, job: dict, result: dict) -> dict:
    matched = result.get("matched_skills", [])
    gaps = result.get("skill_gaps", [])
    strengths = [f"已在画像中找到岗位技能证据：{', '.join(matched)}"] if matched else ["当前简历尚未提供可直接对应的必需技能证据"]
    must_fix = [f"补充或突出技能：{skill}" for skill in gaps]
    if result.get("hard_fail_reasons"):
        must_fix.extend(result["hard_fail_reasons"])
    optional = [f"在项目经历中增加 {skill} 的使用场景、个人职责和结果数据" for skill in matched]
    keywords = sorted(set(matched + gaps))
    checklist = [
        "每个重点项目至少包含背景、个人职责和可验证结果",
        "只保留与目标岗位相关的技能和经历，并由本人确认改写内容",
        "导出前检查联系方式、教育经历和时间线的一致性",
    ]
    return {
        "report_id": report_id,
        "job_title": job["title"],
        "company": job.get("company", "未填写"),
        "strengths": strengths,
        "must_fix": must_fix,
        "optional_improve": optional,
        "ats_keywords": keywords,
        "checklist": checklist,
    }

