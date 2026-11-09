from app.schemas import MatchResult
from app.services.agent_contracts import MatchAssessments, ScoringResult
from app.services.careers import career_matches
from app.services.dify import DifyClient
from app.services.llm import CloudModelError
from app.services.matching import match_jobs


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
        result = {**result, "score_breakdown": {"skill_coverage": item.skill_coverage, "education_match": item.education_match, "preference_fit": item.preference_fit},
                  "total_score": round(item.skill_coverage * .65 + item.education_match * .2 + item.preference_fit * .15, 2),
                  "evidence": [evidence.quote for evidence in item.evidence] + [item.reason]}
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
    careers["catalog"]["scoring_method"] = "规则召回10个职业方向，再由 Dify / DeepSeek 对技能、学历与偏好评分（65% / 20% / 15%）。不是全库语义检索或录用概率。"
    return {
        "dimensions": [{"name": item.name, "score": round(item.score / 20, 2), "score_100": item.score,
                        "evidence": [evidence.quote for evidence in item.evidence], "note": item.note} for item in scoring.dimensions],
        "notice": "DeepSeek 评估资料完整度并经复核；星级为百分制评分除以20，不评估人格、职业资格或录用可能性。",
        "careers": careers, "engine": "dify",
    }
