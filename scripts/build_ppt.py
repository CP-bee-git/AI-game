"""Build CareerPilot deck: >=19pt body text, geometric composition, embedded UI shots."""
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Emu, Pt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/ppt-assets/careerpilot-intro.pptx"
SHOTS = ROOT / "docs/ppt-assets/shots"

W, H = Emu(12192000), Emu(6858000)  # 16:9

NAVY = RGBColor(0x1B, 0x2A, 0x4A)
NAVY_DEEP = RGBColor(0x12, 0x1E, 0x38)
TEAL = RGBColor(0x12, 0x8C, 0x7E)
TEAL_SOFT = RGBColor(0xE2, 0xF2, 0xEF)
PAPER = RGBColor(0xFB, 0xFA, 0xF6)
INK = RGBColor(0x22, 0x27, 0x33)
MUTED = RGBColor(0x5D, 0x64, 0x72)
GOLD = RGBColor(0xE8, 0xA3, 0x3D)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LINE = RGBColor(0xD8, 0xDC, 0xE6)

FONT = "PingFang SC"


def slide_bg(slide, color):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = color


def add_rect(slide, x, y, w, h, fill, line=None, shape=MSO_SHAPE.RECTANGLE, shadow=False):
    box = slide.shapes.add_shape(shape, x, y, w, h)
    box.fill.solid()
    box.fill.fore_color.rgb = fill
    if line is None:
        box.line.fill.background()
    else:
        box.line.color.rgb = line
        box.line.width = Pt(1.2)
    box.shadow.inherit = False
    return box


def add_text(slide, x, y, w, h, text, size, color=INK, bold=False, align=PP_ALIGN.LEFT,
             font=FONT, anchor=MSO_ANCHOR.TOP, line_spacing=1.12):
    box = slide.shapes.add_textbox(x, y, w, h)
    frame = box.text_frame
    frame.word_wrap = True
    frame.vertical_anchor = anchor
    lines = text.split("\n")
    for i, line in enumerate(lines):
        para = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
        para.alignment = align
        para.line_spacing = line_spacing
        run = para.add_run()
        run.text = line
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color
        run.font.name = font
    return box


def add_picture_fit(slide, path, x, y, w, h):
    """Insert picture cropped to fill the target box."""
    img = Image.open(path)
    iw, ih = img.size
    target_ratio = w / h
    src_ratio = iw / ih
    pic = slide.shapes.add_picture(str(path), x, y, w, h)
    if src_ratio > target_ratio:
        crop = (1 - target_ratio / src_ratio) / 2
        pic.crop_left, pic.crop_right = crop, crop
    else:
        crop = (1 - src_ratio / target_ratio) / 2
        pic.crop_top, pic.crop_bottom = crop, crop
    pic.line.color.rgb = LINE
    pic.line.width = Pt(1)
    return pic


def add_chip(slide, x, y, text, fill=TEAL_SOFT, color=TEAL, size=19):
    w = Emu(int(220000 + len(text) * 210000))
    chip = add_rect(slide, x, y, w, Emu(400000), fill, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    chip.adjustments[0] = 0.5
    tf = chip.text_frame
    tf.word_wrap = False
    tf.margin_left = tf.margin_right = Emu(60000)
    tf.margin_top = tf.margin_bottom = Emu(10000)
    para = tf.paragraphs[0]
    para.alignment = PP_ALIGN.CENTER
    run = para.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = True
    run.font.color.rgb = color
    run.font.name = FONT
    return chip


def arrow(slide, x1, y1, x2, y2, color=TEAL, width=2.4):
    conn = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
    conn.line.color.rgb = color
    conn.line.width = Pt(width_pt := 2.4)
    line_elem = conn.line._get_or_add_ln()
    from pptx.oxml.ns import qn
    head = line_elem.makeelement(qn('a:tailEnd'), {'type': 'triangle', 'w': 'med', 'len': 'med'})
    line_elem.append(head)
    return conn


def cover(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide_bg(slide, NAVY_DEEP)
    add_rect(slide, Emu(9000000), Emu(-1400000), Emu(4600000), Emu(4600000), NAVY, shape=MSO_SHAPE.OVAL)
    add_rect(slide, Emu(-1200000), Emu(4600000), Emu(3800000), Emu(3800000), NAVY, shape=MSO_SHAPE.OVAL)
    # compass geometry
    cx, cy = Emu(10000000), Emu(3400000)
    add_rect(slide, cx - Emu(1500000), cy - Emu(1500000), Emu(3000000), Emu(3000000), NAVY_DEEP, line=TEAL, shape=MSO_SHAPE.OVAL)
    needle = add_rect(slide, cx - Emu(450000), cy - Emu(450000), Emu(900000), Emu(900000), GOLD, shape=MSO_SHAPE.DIAMOND)
    needle.rotation = 45
    add_rect(slide, cx - Emu(140000), cy - Emu(140000), Emu(280000), Emu(280000), WHITE, shape=MSO_SHAPE.OVAL)
    add_text(slide, Emu(900000), Emu(1500000), Emu(7000000), Emu(500000), "CAREERPILOT · AI 求职工作台", 20, TEAL, True)
    add_text(slide, Emu(880000), Emu(2000000), Emu(8000000), Emu(1400000), "就业罗盘", 60, WHITE, True)
    add_text(slide, Emu(900000), Emu(3300000), Emu(8200000), Emu(600000), "把简历写清楚，把面试练具体。", 30, RGBColor(0xD5, 0xDA, 0xEA))
    add_text(slide, Emu(900000), Emu(4000000), Emu(8600000), Emu(900000),
             "面向中国校招 / 社招与技术比赛场景\n真实经历 × 联网查证 × 事实锁定，全程可追溯", 21, RGBColor(0xAF, 0xB8, 0xD4))
    add_chip(slide, Emu(900000), Emu(5300000), "项目逻辑 · 创新点 · 开发者优势", fill=TEAL, color=WHITE, size=19)
    add_text(slide, Emu(900000), Emu(6000000), Emu(7000000), Emu(400000), "github.com/CP-bee-git/AI-game", 19, RGBColor(0x8E, 0x98, 0xB8))


def agenda(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide_bg(slide, PAPER)
    add_text(slide, Emu(800000), Emu(600000), Emu(5000000), Emu(500000), "今天讲什么", 34, INK, True)
    items = [
        ("01", "痛点", "求职材料失真、攻略来源不明、准备路径不具体"),
        ("02", "项目逻辑", "确认事实 → 查证要求 → 生成可执行攻略"),
        ("03", "系统架构", "Next.js / FastAPI / Dify 工作流 / 多模型分工"),
        ("04", "创新点", "事实锁定、引用可核对、版本失效、浏览器会话隔离"),
        ("05", "开发者优势", "精准场景攻略、比赛答辩训练、可导出来源报告"),
    ]
    y = Emu(1500000)
    for num, title, desc in items:
        add_text(slide, Emu(900000), y, Emu(900000), Emu(700000), num, 30, TEAL, True)
        add_text(slide, Emu(2000000), y, Emu(3600000), Emu(600000), title, 26, INK, True)
        add_text(slide, Emu(5600000), y + Emu(90000), Emu(6000000), Emu(600000), desc, 19, MUTED)
        y += Emu(1000000)
    add_rect(slide, Emu(820000), Emu(1430000), Emu(40000), Emu(4200000), TEAL)


def painpoints(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide_bg(slide, PAPER)
    add_text(slide, Emu(800000), Emu(550000), Emu(6000000), Emu(500000), "三个不信任", 32, INK, True)
    cards = [
        ("编造经历", "模型替用户“写”简历，\n团队成果写成个人成果", "我们只做事实锁定：\n每条句子映射已确认事实"),
        ("来源不明", "攻略像聊天回答，\n无法核对时间与出处", "我们给引用与链接：\n官方优先，标注抓取时间"),
        ("建议空泛", "“提升综合素质”\n无法执行也无法验收", "我们给任务清单：\n动作、产出物、自查标准"),
    ]
    x = Emu(800000)
    for title, problem, answer in cards:
        add_rect(slide, x, Emu(1500000), Emu(3500000), Emu(4200000), WHITE, line=LINE, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
        add_text(slide, x + Emu(260000), Emu(1760000), Emu(3000000), Emu(500000), title, 24, NAVY, True)
        add_text(slide, x + Emu(260000), Emu(2400000), Emu(3000000), Emu(1300000), problem, 19, MUTED)
        add_rect(slide, x + Emu(260000), Emu(3850000), Emu(2980000), Emu(1500000), TEAL_SOFT, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
        add_text(slide, x + Emu(430000), Emu(4010000), Emu(2680000), Emu(1300000), answer, 19, TEAL, True)
        x += Emu(3800000)


def logic_flow(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide_bg(slide, PAPER)
    add_text(slide, Emu(800000), Emu(520000), Emu(7000000), Emu(500000), "先精准，再联网，再给攻略", 32, INK, True)
    steps = [
        ("确认场景", "类型 / 届次 / 岗位\n信息不足先追问", NAVY),
        ("联网查证", "官方来源优先\nSSRF 防护读取", TEAL),
        ("证据整理", "逐字片段核对\n冲突如实呈现", NAVY),
        ("攻略生成", "动作 / 产出 / 自查\n预测题分开标注", TEAL),
        ("复核导出", "DeepSeek 复核\n带来源的报告", NAVY),
    ]
    x = Emu(700000)
    y = Emu(1700000)
    centers = []
    for i, (title, desc, color) in enumerate(steps):
        shape = MSO_SHAPE.OVAL if i % 2 else MSO_SHAPE.HEXAGON
        node = add_rect(slide, x, y, Emu(1750000), Emu(1750000), color, shape=shape)
        tf = node.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = title; r.font.size = Pt(21); r.font.bold = True; r.font.color.rgb = WHITE; r.font.name = FONT
        centers.append((x + Emu(1750000), y + Emu(875000)))
        add_text(slide, x - Emu(200000), y + Emu(1950000), Emu(2150000), Emu(900000), desc, 19, MUTED, align=PP_ALIGN.CENTER)
        x += Emu(2230000)
    for (x1, y1), (x2, y2) in zip(centers, centers[1:]):
        arrow(slide, x1 + Emu(60000), y1, x2 - Emu(60000), y2)
    add_rect(slide, Emu(700000), Emu(4900000), Emu(10700000), Emu(1400000), WHITE, line=LINE, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    add_text(slide, Emu(1000000), Emu(5080000), Emu(2400000), Emu(1000000), "不能确认\n就不生成", 24, GOLD, True)
    add_text(slide, Emu(3600000), Emu(5030000), Emu(7800000), Emu(1200000),
             "缺少年份、同名赛事、不同赛道 → 返回澄清问题，而不是编造一份“看似真实”的攻略。\n没有联网凭据 → 明确标注「未联网核验」，只给通用训练建议。", 19, INK)


def architecture(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide_bg(slide, PAPER)
    add_text(slide, Emu(800000), Emu(520000), Emu(7000000), Emu(500000), "系统架构：浏览器到模型的四层分工", 32, INK, True)
    layers = [
        ("Next.js 16 · React 19", "工作台 / 开发者页面 / 简历中心", "会话隔离"),
        ("FastAPI 业务接口", "校验 · 任务编排 · 引用检查", "SQLite 存储"),
        ("Dify 17 个工作流", "节点顺序与运行日志", "提示词版本化管理"),
        ("模型与检索", "千问写作 · DeepSeek 复核 · Tavily 检索", "凭据只在服务端"),
    ]
    y = Emu(1500000)
    colors = [NAVY, TEAL, NAVY, TEAL]
    for i, ((name, role, note), color) in enumerate(zip(layers, colors)):
        add_rect(slide, Emu(900000), y, Emu(7000000), Emu(980000), color, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
        add_text(slide, Emu(1250000), y + Emu(130000), Emu(4200000), Emu(450000), name, 23, WHITE, True)
        add_text(slide, Emu(1250000), y + Emu(520000), Emu(6400000), Emu(420000), f"{role} · {note}", 19, RGBColor(0xE6, 0xEA, 0xF5))
        if i < 3:
            arrow(slide, Emu(4400000), y + Emu(1010000), Emu(4400000), y + Emu(1240000), MUTED, 2)
        y += Emu(1280000)
    add_rect(slide, Emu(8400000), Emu(1500000), Emu(3300000), Emu(4720000), TEAL_SOFT, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    add_text(slide, Emu(8660000), Emu(1750000), Emu(2800000), Emu(400000), "安全边界", 23, TEAL, True)
    add_text(slide, Emu(8660000), Emu(2280000), Emu(2800000), Emu(3800000),
             "· 简历原文不进入搜索词\n\n· 网页内容视为不可信数据\n\n· 私网地址与重定向被拦截\n\n· 相同 request_id 不重复计费\n\n· 跨会话读取返回 404", 19, INK)


def innovation(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide_bg(slide, PAPER)
    add_text(slide, Emu(800000), Emu(520000), Emu(7000000), Emu(500000), "创新点：让 AI 输出可以被核对", 32, INK, True)
    rows = [
        ("事实锁定", "每条成稿句子映射 fact_id；画像一改，旧草稿标记失效", "个人 / 团队成果不混淆"),
        ("引用可核对", "「已查证」结论必须带来源 ID 与逐字片段", "后端校验，模型说了不算"),
        ("诚实降级", "断网 / 无凭据 / 查无资料 → 明确标注，不伪装成功", "通用建议与官方要求分开"),
        ("文档即产品", "简历按标准排版导出，攻略附来源列表与抓取时间", "HTML 打印即 PDF"),
    ]
    y = Emu(1480000)
    for i, (title, desc, tag) in enumerate(rows):
        add_rect(slide, Emu(800000), y, Emu(10600000), Emu(1120000), WHITE if i % 2 == 0 else TEAL_SOFT, line=LINE, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
        add_rect(slide, Emu(800000), y, Emu(140000), Emu(1120000), TEAL if i % 2 else NAVY)
        add_text(slide, Emu(1180000), y + Emu(120000), Emu(2600000), Emu(500000), title, 23, INK, True)
        add_text(slide, Emu(1180000), y + Emu(580000), Emu(6400000), Emu(500000), desc, 19, MUTED)
        add_text(slide, Emu(8100000), y + Emu(320000), Emu(3100000), Emu(500000), tag, 19, TEAL, True, align=PP_ALIGN.RIGHT)
        y += Emu(1280000)


def developer(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide_bg(slide, NAVY_DEEP)
    add_text(slide, Emu(800000), Emu(520000), Emu(8000000), Emu(500000), "面向开发者：/developer 工作台", 32, WHITE, True)
    add_picture_fit(slide, SHOTS / "live-developer.png", Emu(6400000), Emu(1400000), Emu(5300000), Emu(3300000))
    add_text(slide, Emu(6400000), Emu(4850000), Emu(5300000), Emu(400000), "实际运行界面：场景表单 + 攻略文档", 19, RGBColor(0x8E, 0x98, 0xB8), align=PP_ALIGN.CENTER)
    points = [
        ("精准场景", "求职 / 面试 / 比赛三类型\n届次、赛道、阶段先确认"),
        ("联网查证", "官方公告与规则优先\n每条结论可点开来源"),
        ("训练衔接", "攻略一键进入练习\n答辩预测题分开标注"),
        ("可交付", "导出带来源的报告\n任务去重不重复计费"),
    ]
    y = Emu(1500000)
    for title, desc in points:
        add_rect(slide, Emu(800000), y, Emu(120000), Emu(1050000), TEAL)
        add_text(slide, Emu(1080000), y + Emu(40000), Emu(4800000), Emu(450000), title, 23, WHITE, True)
        add_text(slide, Emu(1080000), y + Emu(480000), Emu(4800000), Emu(600000), desc, 19, RGBColor(0xC3, 0xCA, 0xE2))
        y += Emu(1230000)


def screens(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide_bg(slide, PAPER)
    add_text(slide, Emu(800000), Emu(520000), Emu(8000000), Emu(500000), "从工作台到可投递的简历", 32, INK, True)
    add_picture_fit(slide, SHOTS / "live-home.png", Emu(700000), Emu(1400000), Emu(6100000), Emu(3800000))
    add_picture_fit(slide, SHOTS / "resume-export.png", Emu(7300000), Emu(1400000), Emu(4200000), Emu(3800000))
    add_text(slide, Emu(700000), Emu(5350000), Emu(6100000), Emu(400000), "求职工作台：上传 → 核对 → 匹配 → 诊断 → 面试", 19, MUTED, align=PP_ALIGN.CENTER)
    add_text(slide, Emu(7300000), Emu(5350000), Emu(4200000), Emu(400000), "简历导出：标准排版，占位醒目", 19, MUTED, align=PP_ALIGN.CENTER)
    add_rect(slide, Emu(700000), Emu(5900000), Emu(10800000), Emu(600000), TEAL_SOFT, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    add_text(slide, Emu(950000), Emu(5980000), Emu(10400000), Emu(450000), "五种视口（1440 / 1280 / 768 / 390 / 360）截图验收通过，长中文无横向溢出", 19, TEAL, True)


def outlook(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide_bg(slide, PAPER)
    add_text(slide, Emu(800000), Emu(520000), Emu(7000000), Emu(500000), "验证结果与下一步", 32, INK, True)
    add_text(slide, Emu(900000), Emu(1400000), Emu(5200000), Emu(400000), "本轮验收", 24, TEAL, True)
    checks = ["17 个 Dify 工作流真实链路通过", "22 项浏览器回归全部通过", "模拟 + 真实云调用分层验证", "五视口截图无横向溢出"]
    y = Emu(1900000)
    for item in checks:
        add_rect(slide, Emu(900000), y + Emu(60000), Emu(220000), Emu(220000), TEAL, shape=MSO_SHAPE.OVAL)
        add_text(slide, Emu(1300000), y, Emu(5200000), Emu(400000), item, 20, INK)
        y += Emu(560000)
    add_text(slide, Emu(6900000), Emu(1400000), Emu(4800000), Emu(400000), "下一步", 24, NAVY, True)
    todos = ["DOCX 原生简历导出与 ATS 验证", "更多检索供应商与官方域名白名单", "比赛真题库（仅收录公开来源）", "多人协作与设备间同步"]
    y = Emu(1900000)
    for item in todos:
        add_rect(slide, Emu(6900000), y + Emu(60000), Emu(220000), Emu(220000), NAVY, shape=MSO_SHAPE.DIAMOND)
        add_text(slide, Emu(7300000), y, Emu(4400000), Emu(400000), item, 20, INK)
        y += Emu(560000)
    add_rect(slide, Emu(900000), Emu(4900000), Emu(10300000), Emu(1300000), NAVY, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    add_text(slide, Emu(1300000), Emu(5130000), Emu(9600000), Emu(900000),
             "就业罗盘不替用户做决定：它把每一份建议，变成可以核对、可以执行、可以交付的文档。", 24, WHITE, True)


def ending(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide_bg(slide, NAVY_DEEP)
    cx, cy = Emu(6100000), Emu(2400000)
    add_rect(slide, cx - Emu(900000), cy - Emu(900000), Emu(1800000), Emu(1800000), NAVY_DEEP, line=TEAL, shape=MSO_SHAPE.OVAL)
    needle = add_rect(slide, cx - Emu(270000), cy - Emu(270000), Emu(540000), Emu(540000), GOLD, shape=MSO_SHAPE.DIAMOND)
    needle.rotation = 45
    add_text(slide, Emu(2600000), Emu(3600000), Emu(7000000), Emu(900000), "真实，是最好的简历。", 40, WHITE, True, align=PP_ALIGN.CENTER)
    add_text(slide, Emu(2600000), Emu(4600000), Emu(7000000), Emu(600000), "就业罗盘 CareerPilot · 谢谢观看", 22, RGBColor(0xAF, 0xB8, 0xD4), align=PP_ALIGN.CENTER)
    add_text(slide, Emu(2600000), Emu(5600000), Emu(7000000), Emu(400000), "github.com/CP-bee-git/AI-game", 19, RGBColor(0x8E, 0x98, 0xB8), align=PP_ALIGN.CENTER)


def main():
    prs = Presentation()
    prs.slide_width = W
    prs.slide_height = H
    cover(prs)
    agenda(prs)
    painpoints(prs)
    logic_flow(prs)
    architecture(prs)
    innovation(prs)
    developer(prs)
    screens(prs)
    outlook(prs)
    ending(prs)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT)
    print(f"saved {OUT} with {len(prs.slides)} slides")


if __name__ == "__main__":
    main()
