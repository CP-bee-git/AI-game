import re


def build_questions(job: dict) -> list[dict[str, object]]:
    skills = [skill for skill in job.get("required_skills", []) if skill]
    questions = [
        {"question": "请用一分钟介绍自己，并说明为什么适合这个岗位。", "keywords": []},
        {"question": "请介绍一个最能体现你解决问题能力的项目，说明你的具体职责和结果。", "keywords": []},
    ]
    questions.extend({"question": f"请结合具体项目说明你如何使用 {skill}。", "keywords": [skill]} for skill in skills[:4])
    return questions[:6]


def evaluate_answer(answer: str, question: dict[str, object]) -> tuple[float, str]:
    text = answer.strip()
    score = 2.0
    feedback = []
    keywords = [str(item).lower() for item in question.get("keywords", [])]
    if keywords and any(keyword in text.lower() for keyword in keywords):
        score += 1
    else:
        feedback.append("建议直接回应问题中的岗位技能要求")
    if len(text) >= 80:
        score += 1
    else:
        feedback.append("补充项目背景、个人职责和结果数据")
    if re.search(r"\d", text):
        score += 1
    else:
        feedback.append("尽量用数量、比例或时间说明结果")
    return min(score, 5), "；".join(feedback) or "回答包含岗位相关证据，可以继续练习表达的结构和重点。"

