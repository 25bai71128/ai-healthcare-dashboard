"""PDF report generation for integrated AI healthcare analytics."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"
PAGE_WIDTH, PAGE_HEIGHT = letter


def _wrap_text(pdf: Any, text: str, max_width: int) -> list[str]:
    """Simple width-aware text wrapping for report sections."""
    words = str(text or "").split()
    if not words:
        return [""]

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if pdf.stringWidth(candidate, pdf._fontname, pdf._fontsize) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _risk_color(level: str):
    """Return report color by risk level."""
    mapping = {
        "High": colors.HexColor("#d32f2f"),
        "Medium": colors.HexColor("#f9a825"),
        "Low": colors.HexColor("#2e7d32"),
    }
    return mapping.get(level, colors.HexColor("#0f3359"))


def _severity_color(severity: str) -> Any:
    """Map alert severity to color."""
    mapping = {
        "danger": colors.HexColor("#d32f2f"),
        "warning": colors.HexColor("#ed8f00"),
        "info": colors.HexColor("#1565c0"),
        "success": colors.HexColor("#2e7d32"),
    }
    return mapping.get(str(severity).lower(), colors.HexColor("#335e8f"))


def _draw_header(pdf: Any, title: str, subtitle: str, risk_level: str, score: Any) -> None:
    """Draw premium report header banner."""
    pdf.setFillColor(colors.HexColor("#0f3359"))
    pdf.rect(0, PAGE_HEIGHT - 86, PAGE_WIDTH, 86, stroke=0, fill=1)

    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 17)
    pdf.drawString(40, PAGE_HEIGHT - 42, title)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(40, PAGE_HEIGHT - 58, subtitle)

    pill_w = 200
    pill_x = PAGE_WIDTH - pill_w - 36
    pill_y = PAGE_HEIGHT - 63
    pdf.setFillColor(_risk_color(risk_level))
    pdf.roundRect(pill_x, pill_y, pill_w, 30, 10, stroke=0, fill=1)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(pill_x + 12, pill_y + 11, f"Score: {score}% ({risk_level})")


def _draw_footer(pdf: Any, report_id: str, page_number: int) -> None:
    """Draw footer with page number and report id."""
    pdf.setStrokeColor(colors.HexColor("#dbe7f7"))
    pdf.line(36, 40, PAGE_WIDTH - 36, 40)
    pdf.setFillColor(colors.HexColor("#6f8398"))
    pdf.setFont("Helvetica", 8)
    pdf.drawString(40, 27, f"Report ID: {report_id}")
    pdf.drawRightString(PAGE_WIDTH - 40, 27, f"Page {page_number}")


def _section_header(pdf: Any, title: str, x: int, y: int, width: int = 520) -> int:
    """Draw section header with subtle divider."""
    pdf.setFont("Helvetica-Bold", 12)
    pdf.setFillColor(colors.HexColor("#0f3359"))
    pdf.drawString(x, y, title)
    pdf.setStrokeColor(colors.HexColor("#d6e4f8"))
    pdf.line(x, y - 4, x + width, y - 4)
    pdf.setFillColor(colors.black)
    return y - 16


def _draw_wrapped_paragraph(
    pdf: Any,
    text: str,
    x: int,
    y: int,
    width: int,
    font_name: str = "Helvetica",
    font_size: int = 10,
    gap: int = 13,
    color: Any = colors.black,
) -> int:
    """Render wrapped paragraph and return next y-coordinate."""
    pdf.setFont(font_name, font_size)
    pdf.setFillColor(color)
    for line in _wrap_text(pdf, text, width):
        pdf.drawString(x, y, line)
        y -= gap
    pdf.setFillColor(colors.black)
    return y


def _draw_metric_card(pdf: Any, title: str, value: str, x: int, y: int, w: int = 160, h: int = 62) -> None:
    """Draw compact metric card."""
    pdf.setFillColor(colors.HexColor("#f3f8ff"))
    pdf.setStrokeColor(colors.HexColor("#d4e3f7"))
    pdf.roundRect(x, y, w, h, 8, stroke=1, fill=1)

    pdf.setFillColor(colors.HexColor("#637f98"))
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(x + 10, y + h - 18, title.upper())

    pdf.setFillColor(colors.HexColor("#0d3357"))
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(x + 10, y + 18, value)
    pdf.setFillColor(colors.black)


def _draw_risk_meter(pdf: Any, score: float, x: int, y: int, w: int, h: int) -> None:
    """Draw segmented risk meter with score pointer."""
    zones = [
        (0.0, 0.35, colors.HexColor("#2e7d32"), "Low"),
        (0.35, 0.65, colors.HexColor("#f9a825"), "Medium"),
        (0.65, 1.0, colors.HexColor("#d32f2f"), "High"),
    ]

    for start, end, color, label in zones:
        zone_x = x + int(w * start)
        zone_w = int(w * (end - start))
        pdf.setFillColor(color)
        pdf.rect(zone_x, y, zone_w, h, stroke=0, fill=1)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawCentredString(zone_x + zone_w / 2, y + h / 2 - 3, label)

    pdf.setStrokeColor(colors.HexColor("#a5bbd8"))
    pdf.rect(x, y, w, h, stroke=1, fill=0)

    marker_x = x + (max(0.0, min(100.0, score)) / 100.0) * w
    pdf.setStrokeColor(colors.HexColor("#08315a"))
    pdf.setLineWidth(1.2)
    pdf.line(marker_x, y - 8, marker_x, y + h + 8)

    pdf.setFillColor(colors.HexColor("#08315a"))
    pdf.circle(marker_x, y - 10, 3, stroke=0, fill=1)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawCentredString(marker_x, y - 20, f"{round(score, 1)}%")
    pdf.setFillColor(colors.black)


def _draw_two_column_bullets(
    pdf: Any,
    left_title: str,
    left_items: list[str],
    right_title: str,
    right_items: list[str],
    x: int,
    y: int,
    width: int,
    column_gap: int = 20,
    max_items: int = 6,
) -> int:
    """Draw two-column bullet lists."""
    col_w = int((width - column_gap) / 2)
    left_x = x
    right_x = x + col_w + column_gap

    pdf.setFillColor(colors.HexColor("#eff6ff"))
    pdf.setStrokeColor(colors.HexColor("#d5e5fa"))
    panel_h = 190
    pdf.roundRect(left_x, y - panel_h, col_w, panel_h, 8, stroke=1, fill=1)
    pdf.roundRect(right_x, y - panel_h, col_w, panel_h, 8, stroke=1, fill=1)

    left_y = y - 16
    right_y = y - 16

    left_y = _section_header(pdf, left_title, left_x + 10, left_y, width=col_w - 20)
    right_y = _section_header(pdf, right_title, right_x + 10, right_y, width=col_w - 20)

    pdf.setFont("Helvetica", 9)
    for item in left_items[:max_items]:
        wrapped = _wrap_text(pdf, f"- {item}", col_w - 24)
        for line in wrapped:
            pdf.drawString(left_x + 12, left_y, line)
            left_y -= 11
            if left_y < y - panel_h + 12:
                break
        if left_y < y - panel_h + 12:
            break

    for item in right_items[:max_items]:
        wrapped = _wrap_text(pdf, f"- {item}", col_w - 24)
        for line in wrapped:
            pdf.drawString(right_x + 12, right_y, line)
            right_y -= 11
            if right_y < y - panel_h + 12:
                break
        if right_y < y - panel_h + 12:
            break

    return y - panel_h - 8


def _draw_feature_impact_bars(pdf: Any, feature_impacts: list[dict[str, Any]], x: int, y: int, w: int) -> int:
    """Draw feature contribution bars."""
    items = feature_impacts[:5]
    if not items:
        return _draw_wrapped_paragraph(
            pdf,
            "No feature contribution data available for this prediction.",
            x,
            y,
            width=w,
            font_size=9,
            color=colors.HexColor("#5b7187"),
        )

    row_h = 20
    for item in items:
        label = str(item.get("label") or item.get("feature") or "Unknown")
        impact = float(item.get("impact_percent") or 0.0)
        impact = max(0.0, min(100.0, impact))

        pdf.setFont("Helvetica", 9)
        pdf.setFillColor(colors.HexColor("#2e4b66"))
        pdf.drawString(x, y, label)

        bar_x = x + 135
        bar_w = w - 190
        bar_y = y - 7

        pdf.setFillColor(colors.HexColor("#e4eefc"))
        pdf.roundRect(bar_x, bar_y, bar_w, 10, 4, stroke=0, fill=1)

        fill_w = bar_w * (impact / 100.0)
        pdf.setFillColor(colors.HexColor("#2563eb"))
        pdf.roundRect(bar_x, bar_y, fill_w, 10, 4, stroke=0, fill=1)

        pdf.setFont("Helvetica-Bold", 9)
        pdf.setFillColor(colors.HexColor("#0f3359"))
        pdf.drawRightString(x + w, y, f"{round(impact, 1)}%")
        y -= row_h

    pdf.setFillColor(colors.black)
    return y


def _draw_model_cards(pdf: Any, model_predictions: dict[str, dict[str, Any]], x: int, y: int, w: int) -> int:
    """Render model output cards in a two-column grid."""
    entries = list(model_predictions.items())[:6]
    if not entries:
        return _draw_wrapped_paragraph(pdf, "No model predictions available.", x, y, width=w)

    col_w = int((w - 16) / 2)
    card_h = 78
    current_y = y

    for idx, (_family, item) in enumerate(entries):
        col = idx % 2
        if idx > 0 and col == 0:
            current_y -= card_h + 10

        card_x = x + (col * (col_w + 16))
        card_y = current_y - card_h

        risk_level = str(item.get("risk_level", "Low"))
        risk_pct = item.get("risk_percent", "n/a")
        model_name = item.get("metadata", {}).get("model_name", "Model")
        version = item.get("version", "n/a")
        weight = item.get("weight", "n/a")
        metrics = item.get("metadata", {}).get("metrics", {})

        pdf.setFillColor(colors.HexColor("#f7fbff"))
        pdf.setStrokeColor(colors.HexColor("#d8e7fa"))
        pdf.roundRect(card_x, card_y, col_w, card_h, 8, stroke=1, fill=1)

        pdf.setFillColor(_risk_color(risk_level))
        pdf.roundRect(card_x + 8, card_y + card_h - 20, 72, 13, 6, stroke=0, fill=1)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 7)
        pdf.drawString(card_x + 14, card_y + card_h - 15, risk_level.upper())

        pdf.setFillColor(colors.HexColor("#0f3359"))
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(card_x + 88, card_y + card_h - 15, f"{risk_pct}%")

        pdf.setFillColor(colors.HexColor("#1f3f5f"))
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(card_x + 8, card_y + card_h - 32, str(model_name)[:34])

        pdf.setFillColor(colors.HexColor("#5f7388"))
        pdf.setFont("Helvetica", 8)
        pdf.drawString(card_x + 8, card_y + 30, f"Version: {version}")
        pdf.drawString(card_x + 8, card_y + 19, f"Weight: {weight}")
        pdf.drawString(card_x + 8, card_y + 8, f"AUC {metrics.get('auc', 'n/a')}  F1 {metrics.get('f1', 'n/a')}")

    rows = (len(entries) + 1) // 2
    return y - rows * (card_h + 10)


def _draw_chart_tile(pdf: Any, title: str, path: str | None, x: int, y: int, w: int, h: int) -> None:
    """Draw chart card with title and optional image."""
    pdf.setFillColor(colors.HexColor("#f8fbff"))
    pdf.setStrokeColor(colors.HexColor("#d8e7fa"))
    pdf.roundRect(x, y, w, h, 8, stroke=1, fill=1)

    pdf.setFillColor(colors.HexColor("#0f3359"))
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(x + 8, y + h - 14, title)

    if path and Path(path).exists():
        pdf.drawImage(
            ImageReader(path),
            x + 8,
            y + 8,
            width=w - 16,
            height=h - 28,
            preserveAspectRatio=True,
            mask="auto",
        )
    else:
        pdf.setFillColor(colors.HexColor("#8aa0b6"))
        pdf.setFont("Helvetica-Oblique", 9)
        pdf.drawCentredString(x + (w / 2), y + (h / 2), "Chart unavailable")
        pdf.setFillColor(colors.black)


def generate_report(
    patient_data: dict[str, Any],
    health_score: dict[str, Any],
    model_predictions: dict[str, dict[str, Any]],
    result_explanation: dict[str, Any],
    precautions: list[dict[str, str]],
    recommendations: list[str],
    monitoring: dict[str, Any],
    alerts: list[dict[str, str]],
    feature_impacts: list[dict[str, Any]],
    chart_paths: dict[str, str] | None = None,
) -> str:
    """Generate and save a rich multi-model healthcare report PDF."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = REPORTS_DIR / f"health_report_{timestamp}.pdf"
    chart_paths = chart_paths or {}

    pdf = canvas.Canvas(str(report_file), pagesize=letter)
    pdf.setTitle("AI Healthcare Decision Support Report")

    score = float(health_score.get("overall_health_score", 0))
    risk_level = str(health_score.get("risk_level", "Low"))
    report_id = f"HRS-{timestamp}"
    generated_at = datetime.now().strftime("%B %d, %Y %H:%M:%S")

    # PAGE 1: Executive clinical summary.
    _draw_header(
        pdf,
        "AI Healthcare Decision Support Report",
        f"Generated {generated_at} | Confidential Clinical Analytics",
        risk_level,
        round(score, 1),
    )

    y = 682
    y = _section_header(pdf, "Patient Snapshot", 40, y)

    _draw_metric_card(pdf, "Age", f"{patient_data.get('age', 'n/a')}", 40, y - 72)
    _draw_metric_card(pdf, "Blood Pressure", f"{patient_data.get('blood_pressure', 'n/a')} mmHg", 216, y - 72)
    _draw_metric_card(pdf, "Cholesterol", f"{patient_data.get('cholesterol', 'n/a')} mg/dL", 392, y - 72)

    y = y - 94
    y = _section_header(pdf, "Global Risk Position", 40, y)
    _draw_risk_meter(pdf, score, 40, y - 20, 515, 16)

    y = y - 44
    y = _section_header(pdf, "Result Explanation", 40, y)
    y = _draw_wrapped_paragraph(
        pdf,
        result_explanation.get("summary", "No summary available."),
        40,
        y,
        width=515,
        font_size=10,
        gap=13,
    )

    confidence = result_explanation.get("confidence_note", "No confidence note available.")
    pdf.setFillColor(colors.HexColor("#f2f8ff"))
    pdf.setStrokeColor(colors.HexColor("#d6e6fb"))
    pdf.roundRect(40, y - 34, 515, 30, 6, stroke=1, fill=1)
    pdf.setFillColor(colors.HexColor("#355a80"))
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(48, y - 16, "Confidence")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(110, y - 16, str(confidence)[:72])

    y = y - 54
    y = _section_header(pdf, "Monitoring and Alerts", 40, y)
    pdf.setFont("Helvetica", 9)
    monitor_line = (
        f"Drift: {monitoring.get('drift_detected')} | "
        f"High disagreement: {monitoring.get('high_model_disagreement')} | "
        f"Avg probability: {monitoring.get('avg_model_probability')}"
    )
    y = _draw_wrapped_paragraph(pdf, monitor_line, 40, y, width=515, font_size=9, gap=12)

    if alerts:
        for alert in alerts[:3]:
            severity = str(alert.get("severity", "info"))
            panel_color = _severity_color(severity)
            pdf.setFillColor(colors.whitesmoke)
            pdf.setStrokeColor(panel_color)
            pdf.roundRect(40, y - 25, 515, 20, 6, stroke=1, fill=1)
            pdf.setFillColor(panel_color)
            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawString(48, y - 13, str(alert.get("title", "Alert"))[:35])
            pdf.setFillColor(colors.HexColor("#355a80"))
            pdf.setFont("Helvetica", 8)
            pdf.drawString(170, y - 13, str(alert.get("message", ""))[:67])
            y -= 24
    else:
        y = _draw_wrapped_paragraph(
            pdf,
            "No active alert rules were triggered for this case.",
            40,
            y,
            width=515,
            font_size=9,
            color=colors.HexColor("#5d7389"),
        )

    _draw_footer(pdf, report_id, 1)
    pdf.showPage()

    # PAGE 2: Model evidence and action plan.
    _draw_header(
        pdf,
        "Model Evidence and Preventive Action Plan",
        "Model outputs, feature contributions, precautions, and recommendations",
        risk_level,
        round(score, 1),
    )

    y = 682
    y = _section_header(pdf, "Model Prediction Cards", 40, y)
    y = _draw_model_cards(pdf, model_predictions, 40, y, 515)

    y -= 4
    y = _section_header(pdf, "Top Feature Drivers", 40, y)
    y = _draw_feature_impact_bars(pdf, feature_impacts, 40, y, 515)

    y -= 8
    precaution_lines = [
        f"[{item.get('priority', 'Info')}] {item.get('title', 'Precaution')}: {item.get('action', '')}"
        for item in precautions
    ]
    y = _draw_two_column_bullets(
        pdf,
        "Precautions",
        precaution_lines,
        "Recommendations",
        recommendations,
        40,
        y,
        515,
    )

    _draw_footer(pdf, report_id, 2)
    pdf.showPage()

    # PAGE 3: Visual analytics dashboard export.
    _draw_header(
        pdf,
        "Visual Analytics Export",
        "Patient indicators, risk distribution, and model intelligence charts",
        risk_level,
        round(score, 1),
    )

    grid = [
        ("Patient Indicators", chart_paths.get("patient_chart"), 40, 470, 248, 176),
        ("Model Comparison", chart_paths.get("comparison_chart"), 304, 470, 248, 176),
        ("Risk Breakdown", chart_paths.get("risk_breakdown_chart"), 40, 270, 248, 176),
        ("Feature Impact", chart_paths.get("feature_impact_chart"), 304, 270, 248, 176),
        ("Weight vs Risk", chart_paths.get("model_weight_risk_chart"), 40, 70, 248, 176),
        ("Historical Trend", chart_paths.get("history_trend_chart"), 304, 70, 248, 176),
    ]

    for title, path, x, y, w, h in grid:
        _draw_chart_tile(pdf, title, path, x, y, w, h)

    _draw_footer(pdf, report_id, 3)
    pdf.save()
    return str(report_file)
