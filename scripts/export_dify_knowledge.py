import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main():
    snapshot = json.loads((ROOT / "backend/app/data/occupations.json").read_text())
    destination = ROOT / "dify/knowledge"
    destination.mkdir(parents=True, exist_ok=True)
    for item in snapshot["occupations"]:
        text = f"# {item['title']}\n\n职业代码：{item['code']}\n\n官方分类：{' / '.join(item['official_classification'])}\n\n来源：{item['source_url']}\n\n以下说明与关键词由本项目整理，不属于官方职业标准。\n\n{item['description']}\n\n常见岗位称呼：{'、'.join(item['typical_jobs'])}\n\n关键词：{'、'.join(item['keywords'])}\n"
        (destination / (item["code"] + ".md")).write_text(text)
    (destination / "README.md").write_text("# 职业知识文件\n\n55 个经来源核对的职业条目；可选导入 Dify 知识库。当前运行版本采用本地规则召回10条，再交 DeepSeek 重排，没有开启知识库检索或嵌入调用。\n\n数据使用边界见 ../../docs/CHINA_CAREER_SOURCES.md；勿将这些文件标记成开放许可的官方职业标准全文。\n")
    print(f"Exported {len(snapshot['occupations'])} source-attributed career records")


if __name__ == "__main__":
    main()
