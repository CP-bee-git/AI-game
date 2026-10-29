"""Offline checks; optionally verify the snapshot against downloaded official CSVs.

Run: python backend/scripts/check_careers.py [--source-dir /tmp]
The source directory may contain <table>.csv or career-complete-<table>.csv.
"""

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.careers import career_matches  # noqa: E402


def check(source_dir: Path | None = None) -> None:
    path = Path(__file__).resolve().parents[1] / "app" / "data" / "occupations.json"
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    occupations = snapshot["occupations"]
    catalog = snapshot["catalog"]
    assert len(occupations) >= 30
    assert len({item["code"] for item in occupations}) == len(occupations)
    assert len({item["category"] for item in occupations}) >= 7
    assert catalog["version"] == "31.0" and catalog["license"] == "CC BY 4.0"
    assert catalog["accessed_on"] == "2026-10-29" and "中文" in catalog["notice"]
    assert "USDOL/ETA" in catalog["attribution"]
    for item in occupations:
        assert re.fullmatch(r"\d{2}-\d{4}\.\d{2}", item["code"])
        assert all(item[key] for key in ("title", "original_title", "description", "software_skills"))
        assert item["source_url"] == "https://www.onetonline.org/link/summary/" + item["code"]
        for skill in item["skills"] + item["software_skills"]:
            assert skill["original_name"] and skill["element_id"]
            assert skill["source_table"] in {"essential_skills", "transferable_skills", "software_skills"}
    for profile in ({}, {"skills": ["Python", "SQL", {"name": "Excel"}]}, {"skills": ["Figma", "Photoshop"]}, {"skills": ["教学", "沟通"]}, {"skills": ["未知专长XYZ", {"name": None}, 123]}):
        output = career_matches(profile)
        results = output["results"]
        assert output["total"] == len(occupations)
        assert len(results) == len({item["code"] for item in results}) == 10
        assert [r["score"] for r in results] == sorted([r["score"] for r in results], reverse=True)
        for item in results:
            assert 0 <= item["score"] <= 100 and isinstance(item["stars"], int) and 0 <= item["stars"] <= 5
            assert item["reason"] and item["source_url"]
    empty = career_matches({})["results"]
    assert all(item["score"] == item["stars"] == 0 and not item["matched_skills"] for item in empty)
    assert all(item["score"] == 0 for item in career_matches({"skills": ["未知专长XYZ"]})["results"])
    assert career_matches({"skills": ["Figma", "Photoshop"]})["results"][0]["code"] in {"27-1024.00", "15-1255.00", "27-1021.00"}
    assert career_matches({"skills": ["教学", "沟通"]})["results"][0]["code"].startswith("25-")
    single = career_matches({"skills": ["Python"]})["results"]
    aliases = career_matches({"skills": ["Python", "Python3"]})["results"]
    assert [(r["code"], r["score"]) for r in single] == [(r["code"], r["score"]) for r in aliases]
    assert all(item["score"] <= 26.7 for item in aliases)
    if source_dir:
        source = {}
        for item in snapshot["source_files"]:
            original = source_dir / (item["name"] + ".csv")
            if not original.exists():
                original = source_dir / ("career-complete-" + item["name"] + ".csv")
            assert hashlib.sha256(original.read_bytes()).hexdigest() == item["sha256"]
            with original.open(encoding="utf-8", newline="") as stream:
                source[item["name"]] = list(csv.DictReader(stream))
            assert len(source[item["name"]]) == item["source_record_count"]
            assert item["url"].startswith("https://www.onetcenter.org/dl_files/database/db_31_0_csv/")
        official = {row["O*NET-SOC Code"]: row for row in source["occupation_data"]}
        software = {(r["O*NET-SOC Code"], r["Workplace Example"], r["Element ID"]) for r in source["software_skills"]}
        essential = {(r["O*NET-SOC Code"], r["Element Name"], r["Element ID"]) for name in ("essential_skills", "transferable_skills") for r in source.get(name, []) if r["Scale ID"] == "IM"}
        for item in occupations:
            raw = official[item["code"]]
            assert raw["Title"] == item["original_title"] and raw["Description"] == item["description"]
            assert all((item["code"], s["original_name"], s["element_id"]) in software for s in item["software_skills"])
            assert all((item["code"], s["original_name"], s["element_id"]) in essential for s in item["skills"])
        print(f"Official source check passed: {len(official)} source occupations, {len(software)} software records.")
    print(f"Career checks passed: {len(occupations)} real occupations, unique descending top 10, zero-evidence handling, attribution and source schema.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path)
    check(parser.parse_args().source_dir)
