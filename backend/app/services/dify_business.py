from app.schemas import MatchResult
from app.services.agent_contracts import MatchAssessments, ScoringResult
from app.services.careers import career_matches
from app.services.dify import DifyClient
from app.services.llm import CloudModelError
from app.services.matching import (
    MISSING_SKILL_PENALTY,
    SCORE_FLOOR,
    SIX_DIMENSION_WEIGHTS,
    awards_competition_score,
    experience_relevance_score,
    match_jobs,
    research_score,
)


async def score_matches(client: DifyClient, profile: dict, blocks: list[dict], jobs: list[dict]) -> list[dict]:
    assessments = await client.run("match", {"profile": profile, "blocks": blocks, "jobs": jobs}, MatchAssessments)
    if sorted(item.job_index for item in assessments.results) != list(range(len(jobs))):
        raise CloudModelError(502, "dify_invalid_output", "Dify 未返回每个岗位的唯一评分。")
    sources = {block["block_id"]: block["text"] for block in blocks}
    results = []
    for item in assessments.results:
        job = jobs[item.job_index]
        if any(evidence.quote not in sources.get(evidence.block_id, "") for evidence in item.evidence):
            raise CloudModelError(502, "dify_invalid_evidence", "岗位匹配引文未通过原文核对。")
        result = match_jobs(profile, [job])[0]
        research, research_hits = research_score(profile)
        awards, awards_hits = awards_competition_score(profile)
        matched = [normalize_name for normalize_name in result.get("matched_skills", [])]
        experience, experience_hits = experience_relevance_score(profile, matched)
        weighted = (
            item.skill_coverage * SIX_DIMENSION_WEIGHTS["skill_coverage"]
            + experience * SIX_DIMENSION_WEIGHTS["experience_relevance"]
            + item.education_match * SIX_DIMENSION_WEIGHTS["education_match"]
            + research * SIX_DIMENSION_WEIGHTS["research_output"]
            + awards * SIX_DIMENSION_WEIGHTS["awards_competition"]
            + item.preference_fit * SIX_DIMENSION_WEIGHTS["preference_fit"]
        )
        capped = max(SCORE_FLOOR, 100.0 - len(result.get("skill_gaps", [])) * MISSING_SKILL_PENALTY) / 100.0
        result = {**result,
                  "score_breakdown": {"skill_coverage": item.skill_coverage, "experience_relevance": round(experience, 2),
                                      "education_match": item.education_match, "research_output": round(research, 2),
                                      "awards_competition": round(awards, 2), "preference_fit": item.preference_fit},
                  "total_score": round(weighted * capped, 2),
                  "evidence": [evidence.quote for evidence in item.evidence] + [item.reason]
                              + ([f"经历相关：{'、'.join(experience_hits)}"] if experience_hits else [])
                              + ([f"科研经历：{'、'.join(research_hits)}"] if research_hits else [])
                              + ([f"奖项与竞赛：{'、'.join(awards_hits)}"] if awards_hits else [])}
        results.append(MatchResult.model_validate(result).model_dump(mode="json"))
    return sorted(results, key=lambda result: (result["eligible"], result["total_score"]), reverse=True)


async def analyze(client: DifyClient, profile: dict, blocks: list[dict]) -> dict:
    scoring = await client.run("analysis", {"profile": profile, "blocks": blocks}, ScoringResult)
    sources = {block["block_id"]: block["text"] for block in blocks}
    for dimension in scoring.dimensions:
        if any(evidence.quote not in sources.get(evidence.block_id, "") for evidence in dimension.evidence):
            raise CloudModelError(502, "dify_invalid_evidence", "评分引文未通过原文核对。")
    careers = career_matches(profile, limit=10)
    candidates = careers["results"]
    jobs = [{"title": candidate["title"], "required_skills": candidate["matched_skills"] + candidate["skill_gaps"]} for candidate in candidates]
    ranked = await score_matches(client, profile, blocks, jobs)
    by_title = {result["job_title"]: result for result in ranked}
    for candidate in candidates:
        result = by_title[candidate["title"]]
        candidate.update(score=result["total_score"], stars=round(result["total_score"] / 20, 1), reason="；".join(result["evidence"]))
    careers["results"] = sorted(candidates, key=lambda candidate: candidate["score"], reverse=True)
    careers["catalog"]["scoring_method"] = "规则召回10个职业方向，再按六维画像评分：技能25%、经历相关25%、学历15%、科研15%、奖项竞赛10%、求职意向10%；每缺一项必需技能总分折减15分（下限25分）。科研、奖项与经历维度由规则引擎按画像原文识别（论文/课题/专利、竞赛层级、实习与职责）。权重设计借鉴公开简历筛选 rubric（Rhed-Dev/resume-screening-toolkit、resume-screening-agent）。不是全库语义检索或录用概率。"
    return {
        "dimensions": [{"name": item.name, "score": round(item.score / 20, 2), "score_100": item.score,
                        "evidence": [evidence.quote for evidence in item.evidence], "note": item.note} for item in scoring.dimensions],
        "notice": "DeepSeek 评估资料完整度并经复核；星级为百分制评分除以20，不评估人格、职业资格或录用可能性。",
        "careers": careers, "engine": "dify",
    }
