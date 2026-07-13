"""PDF export smoke tests."""
from app.services.report_export_service import render_markdown_pdf


def test_render_markdown_pdf_produces_pdf_bytes() -> None:
    markdown = """# YOLO Detection Report

## 1. Task Summary
- detection_id: 42
- status: completed

## 2. Detected Objects
| # | class | confidence | bbox (x1, y1, x2, y2) |
|---|-------|------------|------------------------|
| 1 | merchant | 0.9123 | (1.0, 2.0, 30.0, 40.0) |

## 3. Limitations
- Results are model predictions, not human annotations.
"""

    pdf = render_markdown_pdf(markdown, detection_id=42)

    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 2000
