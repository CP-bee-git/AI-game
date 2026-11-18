import re
from typing import Iterable


EDUCATION_RANK = {"高中": 1, "大专": 2, "专科": 2, "本科": 3, "学士": 3, "硕士": 4, "研究生": 4, "博士": 5}

# 学校层次仅按画像中明确写出的标签识别，不做院校排名推断。
ELITE_SCHOOL_MARKERS = ("985", "211", "双一流")

RESEARCH_KEYWORDS = {
    "publication": ("论文", "SCI", "EI", "核心期刊", "期刊发表", "会议论文", "一作", "共同一作", "publication", "paper"),
    "project": ("科研项目", "课题", "国家自然科学基金", "基金项目", "实验室", "科研经历", "research"),
    "patent": ("专利", "软著", "软件著作权", "patent"),
}

LEADERSHIP_KEYWORDS = ("班长", "团支书", "学生会", "主席", "部长", "社长", "队长", "负责人", "组织委员", "leader", "president", "书记")

COMPETITION_TIERS = (
    (("国家级", "全国", "国赛", "国际"), 3, "国家级/国际级"),
    (("省级", "省部级", "省赛", "大区"), 2, "省级/大区"),
    (("校级", "市级", "院级"), 1, "校级/市级"),
)
COMPETITION_AWARD_HINTS = ("一等奖", "二等奖", "三等奖", "金奖", "银奖", "铜奖", "冠军", "亚军", "季军", "特等奖", "优秀奖", "获奖", "入围决赛", "finalist", "award", "prize")

INTERNSHIP_MARKERS = ("实习", "intern")
EXPERIENCE_QUALITY_MARKERS = ("负责", "主导", "独立", "设计", "开发", "搭建", "优化", "提升", "降低", "完成", "交付")

# 六维画像权重，参考公开简历筛选 rubric（技能与经历为主，教育为门槛项）并结合中国校招语境调整。
# 借鉴来源：Rhed-Dev/resume-screening-toolkit（技能0.40/语义0.25/资深度0.35、缺失门槛折减15%）、
# himanshuaggarwal04380/resume-screening-agent（rubric 权重归一化到100）。
SIX_DIMENSION_WEIGHTS = {
    "skill_coverage": 0.25,
    "experience_relevance": 0.25,
    "education_match": 0.15,
    "research_output": 0.15,
    "awards_competition": 0.10,
    "preference_fit": 0.10,
}
# 每个缺失的必需技能对总分的折减（借鉴 gate.penalty_per_missing=0.15），总分下限 25 分。
MISSING_SKILL_PENALTY = 15.0
SCORE_FLOOR = 25.0

SIX_DIMENSION_LABELS = {
    "skill_coverage": "技能匹配",
    "experience_relevance": "经历相关",
    "education_match": "学历背景",
    "research_output": "科研成果",
    "awards_competition": "奖项竞赛",
    "preference_fit": "求职意向",
}


def _flat_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(_flat_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flat_text(item) for item in value)
    return str(value)


def elite_school_flag(education: Iterable[dict]) -> bool:
    text = _flat_text(list(education))
    return any(marker in text for marker in ELITE_SCHOOL_MARKERS)


def research_score(profile: dict) -> tuple[float, list[str]]:
    """0-100 科研维度：论文/科研项目/专利各占一档，证据只引用画像原文。"""
    sources = list(profile.get("education", [])) + list(profile.get("projects", [])) + list(profile.get("experiences", []))
    text = _flat_text(sources)
    hits = []
    score = 0.0
    for label, keywords in RESEARCH_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            score += 40 if label == "publication" else 30
            hits.append({"publication": "论文/学术发表", "project": "科研项目/课题", "patent": "专利/软著"}[label])
    return min(score, 100.0), hits


def awards_competition_score(profile: dict) -> tuple[float, list[str]]:
    """0-100 奖项与竞赛维度：竞赛层级取最高档，学生职务与领导经历作为佐证。"""
    sources = list(profile.get("experiences", [])) + list(profile.get("projects", [])) + list(profile.get("education", []))
    text = _flat_text(sources)
    score = 0.0
    hits = []
    if any(keyword in text for keyword in LEADERSHIP_KEYWORDS):
        score += 30
        hits.append("学生职务/社团负责人")
    best_tier = 0
    best_label = ""
    if any(hint in text for hint in COMPETITION_AWARD_HINTS) or "竞赛" in text or "比赛" in text or "大赛" in text:
        for keywords, tier, label in COMPETITION_TIERS:
            if any(keyword in text for keyword in keywords) and tier > best_tier:
                best_tier, best_label = tier, label
    if best_tier:
        score += 25 + best_tier * 15  # 校级40 / 省级55 / 国家级70
        hits.append(f"竞赛获奖（{best_label}）")
    return min(score, 100.0), hits


def experience_relevance_score(profile: dict, matched: list[str]) -> tuple[float, list[str]]:
    """0-100 经历相关维度：实习/正式经历、经历质量词与技能证据的交叉验证。"""
    experiences = list(profile.get("experiences", []))
    projects = list(profile.get("projects", []))
    score = 0.0
    hits = []
    if any(any(marker in _flat_text(item) for marker in INTERNSHIP_MARKERS) for item in experiences):
        score += 35
        hits.append("有实习经历")
    elif experiences:
        score += 25
        hits.append("有实践/工作经历")
    if projects:
        score += 20
        hits.append(f"项目经历 {len(projects)} 段")
    quality_text = _flat_text(experiences + projects)
    if any(marker in quality_text for marker in EXPERIENCE_QUALITY_MARKERS):
        score += 20
        hits.append("经历写有具体职责与结果")
    if matched and any(normalize(skill) in normalize(quality_text) for skill in matched):
        score += 25
        hits.append("技能在经历原文中有佐证")
    return min(score, 100.0), hits


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff+#.]", "", value.lower())


def skill_names(skills: Iterable[dict | str]) -> set[str]:
    names = set()
    for skill in skills:
        value = skill if isinstance(skill, str) else skill.get("normalized_name") or skill.get("name")
        if value:
            names.add(normalize(value))
    return names


def highest_education(education: Iterable[dict]) -> int:
    rank = 0
    for item in education:
        degree = str(item.get("degree") or item.get("学历") or "")
        for name, value in EDUCATION_RANK.items():
            if name in degree:
                rank = max(rank, value)
    return rank


def required_education(value: str | None) -> int:
    if not value:
        return 0
    return max((rank for name, rank in EDUCATION_RANK.items() if name in value), default=0)


def match_jobs(profile: dict, jobs: list[dict]) -> list[dict]:
    candidate_skills = skill_names(profile.get("skills", []))
    candidate_education = highest_education(profile.get("education", []))
    preferences = profile.get("preferences", {})
    preferred_cities = {normalize(str(item)) for item in preferences.get("cities", [])}
    results = []

    for job in jobs:
        required = {normalize(skill) for skill in job.get("required_skills", []) if skill}
        preferred = {normalize(skill) for skill in job.get("preferred_skills", []) if skill}
        matched_required = sorted(required & candidate_skills)
        matched_preferred = sorted(preferred & candidate_skills)
        gaps = sorted(required - candidate_skills)
        education_fail = required_education(job.get("education_required")) > candidate_education
        location = normalize(job.get("location") or "不限")
        location_fail = bool(preferred_cities and location not in {"不限", "全国"} and location not in preferred_cities)
        hard_fail_reasons = []
        if education_fail:
            hard_fail_reasons.append(f"学历要求为{job.get('education_required')}，当前画像未提供满足证据")
        if location_fail:
            hard_fail_reasons.append(f"工作地点为{job.get('location')}，与当前城市偏好不一致")

        required_score = 100 if not required else len(matched_required) / len(required) * 100
        preferred_score = 100 if not preferred else len(matched_preferred) / len(preferred) * 100
        skill_score = required_score * 0.8 + preferred_score * 0.2
        preference_score = 0 if location_fail else 100
        education_score = 0 if education_fail else 100
        research, research_hits = research_score(profile)
        awards, awards_hits = awards_competition_score(profile)
        experience, experience_hits = experience_relevance_score(profile, matched_required)

        weighted = (
            skill_score * SIX_DIMENSION_WEIGHTS["skill_coverage"]
            + experience * SIX_DIMENSION_WEIGHTS["experience_relevance"]
            + education_score * SIX_DIMENSION_WEIGHTS["education_match"]
            + research * SIX_DIMENSION_WEIGHTS["research_output"]
            + awards * SIX_DIMENSION_WEIGHTS["awards_competition"]
            + preference_score * SIX_DIMENSION_WEIGHTS["preference_fit"]
        )
        # 门槛折减：每缺一项必需技能折减总分，但保留下限，不会因技能缺口归零。
        capped = max(SCORE_FLOOR, 100.0 - len(gaps) * MISSING_SKILL_PENALTY) / 100.0
        total = round(weighted * capped, 2)
        breakdown = {
            "skill_coverage": round(skill_score, 2),
            "experience_relevance": round(experience, 2),
            "education_match": education_score,
            "research_output": round(research, 2),
            "awards_competition": round(awards, 2),
            "preference_fit": preference_score,
        }
        results.append({
            "job_title": job["title"],
            "company": job.get("company", "未填写"),
            "location": job.get("location", "不限"),
            "eligible": not hard_fail_reasons,
            "hard_fail_reasons": hard_fail_reasons,
            "total_score": total,
            "score_breakdown": breakdown,
            "matched_skills": matched_required + matched_preferred,
            "skill_gaps": gaps,
            "evidence": (
                [f"画像技能命中：{', '.join(matched_required)}"] if matched_required else []
            ) + ([f"经历相关：{'、'.join(experience_hits)}"] if experience_hits else [])
            + ([f"科研经历：{'、'.join(research_hits)}"] if research_hits else [])
            + ([f"奖项与竞赛：{'、'.join(awards_hits)}"] if awards_hits else []),
        })

    return sorted(results, key=lambda item: (item["eligible"], item["total_score"]), reverse=True)


def demo() -> None:
    base = {"skills": [{"name": "Python"}], "education": [{"degree": "本科"}]}
    result = match_jobs(base, [{"title": "分析师", "required_skills": ["Python"]}])
    assert result[0]["eligible"] and result[0]["total_score"] > 0
    richer = {
        **base,
        "education": [{"degree": "硕士", "school": "某双一流高校"}],
        "projects": [{"name": "核心期刊论文一篇（一作）"}, {"name": "负责搭建 Python 数据分析流水线"}],
        "experiences": [{"role": "学生会主席"}, {"role": "队长", "responsibilities": "带队获全国大学生数学建模竞赛国家级二等奖"}, {"role": "数据分析实习生", "company": "某公司"}],
    }
    boosted = match_jobs(richer, [{"title": "分析师", "required_skills": ["Python"], "education_required": "硕士"}])[0]
    assert boosted["score_breakdown"]["research_output"] > 0
    assert boosted["score_breakdown"]["awards_competition"] > 0
    assert boosted["score_breakdown"]["experience_relevance"] > result[0]["score_breakdown"]["experience_relevance"]
    assert boosted["total_score"] > result[0]["total_score"]


if __name__ == "__main__":
    demo()
