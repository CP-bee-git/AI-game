from pathlib import Path
from zipfile import ZipFile

import pymupdf
from docx import Document


def initial_resume_blocks(path: Path, content_type: str) -> list[dict[str, str | int]]:
    """Extract text with source locations; scanned pages wait for the OCR adapter."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        blocks = []
        with pymupdf.open(path) as document:
            for page_number, page in enumerate(document[:100], start=1):
                for block_number, block in enumerate(page.get_text("blocks"), start=1):
                    text = block[4].strip()
                    if text:
                        blocks.append({
                            "block_id": f"page_{page_number}_block_{block_number}",
                            "text": text[:4000],
                            "page": page_number,
                        })
        return blocks or [{"block_id": "ocr_pending", "text": "未检测到可提取文本；扫描版 PDF 需要 OCR。", "page": 1}]

    if suffix == ".docx":
        document = Document(path)
        blocks = []
        for index, paragraph in enumerate(document.paragraphs, start=1):
            text = paragraph.text.strip()
            if text:
                blocks.append({"block_id": f"paragraph_{index}", "text": text[:4000], "page": 1})
        for table_index, table in enumerate(document.tables, start=1):
            for row_index, row in enumerate(table.rows, start=1):
                text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if text:
                    blocks.append({"block_id": f"table_{table_index}_row_{row_index}", "text": text[:4000], "page": 1})
        return blocks

    if content_type.startswith("text/"):
        text = path.read_text(encoding="utf-8", errors="replace")
        return [{"block_id": "text_1", "text": text[:20000], "page": 1}]

    return [
        {
            "block_id": "ocr_pending",
            "text": "图片已上传；OCR 引擎接入后将提取文本。",
            "page": 1,
        }
    ]

