"""Check Chinese occupation facts and explainable matching.

Run offline: python backend/scripts/check_careers.py
Recheck cached official records: add --source-dir .runtime/china-career-sources
Recheck the live official endpoint (maintenance only): add --verify-source
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.careers import career_matches  # noqa: E402


def check(source_dir: Path | None = None, verify_source: bool = False) -> None:
    path = Path(__file__).resolve().parents[1] / "app" / "data" / "occupations.json"
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    occupations, catalog = snapshot["occupations"], snapshot["catalog"]
    assert len(occupations) == 55
    assert len({item["code"] for item in occupations}) == len(occupations)
    assert len({item["category"] for item in occupations}) >= 7
    assert catalog["id"].startswith("china-occupation-")
    assert catalog["source_url"] == "https://www.osta.org.cn/career"
    assert "项目" in catalog["notice"] and "官方资格" in catalog["notice"]
    assert catalog["accessed_on"] == "2026-10-30"
    assert all(term not in json.dumps(snapshot, ensure_ascii=False).lower() for term in ["o*net", "onetonline.org", "usdol", "cc by 4.0"])
    for item in occupations:
        assert re.fullmatch(r"[1-8]-\d{2}-\d{2}-\d{2}", item["code"])
        assert all(item[key] for key in ("title", "official_title", "description", "keywords", "typical_jobs"))
        assert re.sub(r"[LS/]+$", "", item["official_title"]).strip() == item["title"]
        assert len(item["official_classification"]) == 3
        expected_url = snapshot["provenance"]["detail_url_template"].format(code=item["code"])
        assert item["source_url"] == expected_url
        assert urlparse(expected_url).netloc == "www.osta.org.cn"
        assert re.fullmatch(r"[0-9a-f]{64}", item["source_record_sha256"])
        assert len(item["keywords"]) == len(set(item["keywords"]))
        assert len(item["keywords"]) >= 5
        if source_dir or verify_source:
            if verify_source:
                with urlopen(expected_url, timeout=25) as response:
                    official = json.load(response)["body"]
            else:
                official = json.loads((source_dir / (item["code"] + ".json")).read_text())
            facts = {key: official[key] for key in snapshot["provenance"]["source_fields"]}
            digest = hashlib.sha256(json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            assert item["source_record_sha256"] == digest, item["code"]
            assert facts["careerCode"] == item["code"] and facts["name"] == item["official_title"]
            assert [facts[key] for key in ("bigName", "centreName", "smallName")] == item["official_classification"]
    profiles = [{}, {"skills": ["Python", "SQL", {"name": "Excel"}]}, {"skills": ["Figma", "Photoshop"]}, {"skills": ["教学", "沟通"]}, {"skills": ["未知专长XYZ", {"name": None}, 123]}]
    for profile in profiles:
        output = career_matches(profile)
        results = output["results"]
        assert output["total"] == len(occupations)
        assert len(results) == len({item["code"] for item in results}) == 10
        assert [r["score"] for r in results] == sorted([r["score"] for r in results], reverse=True)
        for item in results:
            assert 0 <= item["score"] <= 100 and isinstance(item["stars"], int) and 0 <= item["stars"] <= 5
            assert item["reason"] and item["source_title"] and item["typical_jobs"]
    empty = career_matches({})["results"]
    assert all(item["score"] == item["stars"] == 0 and not item["matched_skills"] for item in empty)
    assert len({item["category"] for item in empty}) >= 7
    assert all(item["score"] == 0 for item in career_matches({"skills": ["未知专长XYZ"]})["results"])
    assert career_matches({"skills": ["Figma", "Photoshop"]})["results"][0]["code"] == "2-09-06-01"
    assert career_matches({"skills": ["教学", "沟通"]})["results"][0]["code"].startswith("2-08-")
    assert career_matches({"skills": ["会计核算", "财务报表", "金蝶"]})["results"][0]["title"] == "会计专业人员"
    assert career_matches({"skills": ["SQL", "Excel", "Pandas", "Python", "数据清洗", "数据可视化"]})["results"][0]["code"] in {"2-02-38-03", "2-02-30-09"}
    single = career_matches({"skills": ["Python"]})["results"]
    aliases = career_matches({"skills": ["Python", "Python3", "Python编程"]})["results"]
    assert [(r["code"], r["score"]) for r in single] == [(r["code"], r["score"]) for r in aliases]
    assert all(item["score"] <= 26.7 for item in aliases)
    assert sum(bool(item["matched_skills"]) for item in career_matches({"skills": ["R"]})["results"]) == 1
    for limit in (1, 5, 100):
        assert len(career_matches({}, limit)["results"]) == min(limit, 10)
    if source_dir or verify_source:
        print(f"Official Chinese source check passed: {len(occupations)} title/code/category records and hashes.")
    print(f"Career checks passed: {len(occupations)} Chinese occupations, top 10, alias deduplication, zero evidence and source provenance.")


def check_scoring_dimensions() -> None:
    from app.services.matching import match_jobs

    jobs = [{"title": "算法工程师", "required_skills": ["Python"], "education_required": "硕士"}]
    plain = {"skills": [{"name": "Python"}], "education": [{"degree": "硕士", "school": "某高校"}]}
    rich = {
        "skills": [{"name": "Python"}],
        "education": [{"degree": "硕士", "school": "某双一流高校"}],
        "projects": [{"name": "以一作发表 SCI 论文一篇"}, {"name": "参与国家自然科学基金课题"}],
        "experiences": [
            {"role": "班长"},
            {"role": "队长", "responsibilities": "获全国大学生数学建模竞赛国家级一等奖"},
            {"role": "算法实习生", "responsibilities": "负责模型训练与优化"},
        ],
    }
    base = match_jobs(plain, jobs)[0]
    boosted = match_jobs(rich, jobs)[0]
    for key in ("skill_coverage", "experience_relevance", "education_match", "research_output", "awards_competition", "preference_fit"):
        assert key in boosted["score_breakdown"], key
    assert boosted["score_breakdown"]["research_output"] == 70.0  # 论文40+课题30
    assert boosted["score_breakdown"]["awards_competition"] == 100.0  # 职务30+国家级70
    assert boosted["score_breakdown"]["experience_relevance"] > base["score_breakdown"]["experience_relevance"]
    assert base["score_breakdown"]["research_output"] == 0.0
    assert boosted["total_score"] > base["total_score"]
    assert any("科研经历" in item for item in boosted["evidence"])
    assert any("奖项与竞赛" in item for item in boosted["evidence"])
    assert 0 <= boosted["total_score"] <= 100
    # 缺失必需技能的门槛折减：缺 3 项时总分应明显低于同画像满分情形
    gapped = match_jobs(rich, [{"title": "全栈工程师", "required_skills": ["Python", "Go", "K8s", "React"]}])[0]
    assert gapped["total_score"] < boosted["total_score"] * 0.6
    assert gapped["total_score"] >= 25 * 0.5


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--verify-source", action="store_true")
    parser.add_argument("--scoring", action="store_true")
    args = parser.parse_args()
    if args.scoring:
        check_scoring_dimensions()
        print("Scoring dimension checks passed.")
    else:
        check(args.source_dir, args.verify_source)
