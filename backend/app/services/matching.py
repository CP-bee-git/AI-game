import re
from typing import Iterable


EDUCATION_RANK = {"高中": 1, "大专": 2, "专科": 2, "本科": 3, "学士": 3, "硕士": 4, "研究生": 4, "博士": 5}


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
        total = round(skill_score * 0.65 + preference_score * 0.15 + (100 if not education_fail else 0) * 0.2, 2)
        results.append({
            "job_title": job["title"],
            "company": job.get("company", "未填写"),
            "location": job.get("location", "不限"),
            "eligible": not hard_fail_reasons,
            "hard_fail_reasons": hard_fail_reasons,
            "total_score": total,
            "score_breakdown": {
                "skill_coverage": round(skill_score, 2),
                "semantic_similarity": round(skill_score, 2),
                "education_match": 0 if education_fail else 100,
                "preference_fit": preference_score,
            },
            "matched_skills": matched_required + matched_preferred,
            "skill_gaps": gaps,
            "evidence": [f"画像技能命中：{', '.join(matched_required)}"] if matched_required else [],
        })

    return sorted(results, key=lambda item: (item["eligible"], item["total_score"]), reverse=True)


def demo() -> None:
    result = match_jobs({"skills": [{"name": "Python"}], "education": [{"degree": "本科"}]}, [{"title": "分析师", "required_skills": ["Python"]}])
    assert result[0]["eligible"] and result[0]["total_score"] > 0


if __name__ == "__main__":
    demo()

