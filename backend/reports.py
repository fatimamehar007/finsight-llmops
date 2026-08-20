"""Compliance status logic and PDF audit report generation.

Extracted from the Streamlit Reports page so the REST API can generate
reports directly — the frontend no longer needs to know how a report
is built, only how to request one.
"""

import io
from datetime import datetime

import pandas as pd


def compliance_status(safe_pct: float, high_pct: float) -> tuple[str, str]:
    """Return (verdict, description) given safe-response % and HIGH-risk %."""
    if safe_pct > 90 and high_pct < 5:
        return "COMPLIANT", "All key metrics within acceptable thresholds."
    elif safe_pct >= 70 and high_pct <= 20:
        return "REVIEW", "One or more metrics are outside recommended ranges."
    else:
        return "FAIL", "Critical thresholds breached. Immediate review required."


def sanitize_pdf_text(text: str) -> str:
    """Strip characters Helvetica (latin-1 only) can't render."""
    replacements = {
        "…": "...", "‘": "'", "’": "'", "“": '"', "”": '"',
        "–": "-", "—": "--", "é": "e", "à": "a", "•": "-", "°": "deg",
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def generate_compliance_pdf(
    report_title: str,
    analyst_name: str,
    org_name: str,
    date_from: datetime,
    date_to: datetime,
    df: pd.DataFrame,
) -> bytes:
    """Build the compliance audit PDF and return its raw bytes."""
    from fpdf import FPDF, XPos, YPos

    total       = len(df)
    safe_count  = int(df["is_safe"].sum())
    unsafe_ct   = total - safe_count
    safe_pct    = safe_count / total * 100 if total else 0
    avg_lat     = df["latency_ms"].mean() if total else 0
    avg_risk    = df["overall_risk_score"].mean() if total else 0
    risk_dist   = df["hallucination_risk"].value_counts().to_dict()
    high_ct     = risk_dist.get("HIGH", 0)
    high_pct    = high_ct / total * 100 if total else 0
    cat_dist    = df["query_category"].value_counts().to_dict()
    top_flagged = df.nlargest(5, "overall_risk_score")

    status_label, _ = compliance_status(safe_pct, high_pct)

    recs = []
    if high_pct > 20:
        recs.append(
            f"HIGH hallucination rate ({high_pct:.1f}%) exceeds 20% threshold. "
            "Mandatory model review and knowledge-base refresh required."
        )
    if safe_pct < 90:
        recs.append(
            f"Safe response rate ({safe_pct:.1f}%) is below the 90% target. "
            "Review prompt guardrails and escalate to the AI Risk Committee."
        )
    if avg_risk > 40:
        recs.append(
            f"Average risk score ({avg_risk:.1f}/100) above moderate threshold. "
            "Increase human-in-the-loop review frequency."
        )
    if avg_lat > 5000:
        recs.append(
            f"Average latency ({avg_lat:.0f} ms) exceeds the 5,000 ms SLA. "
            "Review model serving infrastructure."
        )
    if not recs:
        recs.append(
            "All metrics within acceptable thresholds. Maintain current monitoring cadence. "
            "Next scheduled review: 30 days."
        )

    report_title = sanitize_pdf_text(report_title)
    analyst_name = sanitize_pdf_text(analyst_name)
    org_name     = sanitize_pdf_text(org_name)
    recs         = [sanitize_pdf_text(r) for r in recs]

    class RPdf(FPDF):
        def header(self):
            self.set_font("Helvetica", "B", 9)
            self.set_fill_color(26, 26, 46)
            self.rect(0, 0, 210, 16, "F")
            self.set_text_color(200, 200, 200)
            self.cell(0, 6, "  FinSight LLMOps  |  AI Compliance Report  |  CONFIDENTIAL",
                      new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.set_text_color(0, 0, 0)
            self.ln(6)

        def footer(self):
            self.set_y(-14)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(120, 120, 120)
            self.cell(
                0, 8,
                f"FinSight LLMOps Compliance Report  |  Page {self.page_no()} of {{nb}}  "
                f"|  {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
                align="C",
            )

        def section(self, title):
            title = sanitize_pdf_text(str(title))
            self.set_font("Helvetica", "B", 11)
            self.set_fill_color(26, 26, 46)
            self.set_text_color(250, 250, 250)
            self.cell(0, 8, f"  {title}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
            self.set_text_color(0, 0, 0)
            self.ln(3)

        def stat(self, label, value, warn=False):
            label = sanitize_pdf_text(str(label))
            value = sanitize_pdf_text(str(value))
            self.set_font("Helvetica", "B", 10)
            self.cell(90, 7, label, border="B")
            self.set_font("Helvetica", "B" if warn else "", 10)
            if warn:
                self.set_text_color(192, 57, 43)
            self.cell(0, 7, value, border="B", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.set_text_color(0, 0, 0)

        def body(self, text):
            text = sanitize_pdf_text(str(text))
            self.set_font("Helvetica", "", 10)
            self.multi_cell(0, 6, text)
            self.ln(2)

    pdf = RPdf()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=18)

    pdf.add_page()
    pdf.ln(12)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(26, 26, 46)
    pdf.cell(0, 12, "AI Compliance Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 8, report_title, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, f"Organization: {org_name}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.cell(
        0, 7,
        f"Period: {date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')}",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C",
    )
    pdf.cell(0, 7, f"Prepared by: {analyst_name}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.cell(
        0, 7, f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C",
    )
    pdf.ln(8)
    pdf.set_draw_color(26, 26, 46)
    pdf.set_line_width(0.8)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(8)

    pdf.set_font("Helvetica", "B", 13)
    if status_label == "COMPLIANT":
        pdf.set_fill_color(30, 126, 74)
    elif status_label == "REVIEW":
        pdf.set_fill_color(212, 134, 10)
    else:
        pdf.set_fill_color(192, 57, 43)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 12, f"  Compliance Status: {status_label}",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(6)

    pdf.section("1. Executive Summary")
    pdf.body(
        f"This report covers {total} LLM queries processed by FinSight LLMOps during the period "
        f"{date_from.strftime('%B %d, %Y')} through {date_to.strftime('%B %d, %Y')}. "
        "Every query was evaluated for toxicity, hallucination risk, query category, and latency. "
        "All results are logged to a persistent audit database."
    )
    pdf.stat("Total Queries Processed", str(total))
    pdf.stat("Safe Responses", f"{safe_count} ({safe_pct:.1f}%)")
    pdf.stat("Unsafe Responses", f"{unsafe_ct} ({100 - safe_pct:.1f}%)", warn=unsafe_ct > 0)
    pdf.stat("Average Response Latency", f"{avg_lat:.0f} ms", warn=avg_lat > 5000)
    pdf.stat("Average Overall Risk Score", f"{avg_risk:.1f} / 100", warn=avg_risk > 40)
    pdf.stat("Compliance Status", status_label, warn=status_label != "COMPLIANT")
    pdf.ln(6)

    pdf.section("2. Hallucination Risk Breakdown")
    pdf.body("Classified into LOW / MEDIUM / HIGH using context-grounding analysis and refusal detection.")
    for level in ["LOW", "MEDIUM", "HIGH"]:
        ct  = risk_dist.get(level, 0)
        pct = ct / total * 100 if total else 0
        pdf.stat(f"{level} Risk", f"{ct} queries ({pct:.1f}%)", warn=(level == "HIGH" and ct > 0))
    pdf.ln(6)

    pdf.section("3. Query Category Distribution")
    pdf.body("Queries automatically classified into financial domain categories.")
    for cat, cnt in sorted(cat_dist.items(), key=lambda x: -x[1]):
        pct = cnt / total * 100
        pdf.stat(cat.title(), f"{cnt} queries ({pct:.1f}%)")
    pdf.ln(6)

    pdf.add_page()
    pdf.section("4. Top Flagged Queries")
    pdf.body("Queries with the highest overall risk scores during this period:")
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 8)
    for col, w in [("#", 10), ("Query (truncated)", 96), ("Risk", 22), ("Score", 20), ("Tox", 22)]:
        pdf.cell(w, 7, col, border=1, align="C")
    pdf.ln()
    pdf.set_font("Helvetica", "", 8)
    for rank, (_, row) in enumerate(top_flagged.iterrows(), 1):
        q_raw = str(row["query"])
        q = sanitize_pdf_text(q_raw[:62] + ("..." if len(q_raw) > 62 else ""))
        pdf.cell(10, 6, str(rank), border=1, align="C")
        pdf.cell(96, 6, q, border=1)
        pdf.cell(22, 6, sanitize_pdf_text(str(row["hallucination_risk"])), border=1, align="C")
        pdf.cell(20, 6, f"{row['overall_risk_score']:.1f}", border=1, align="C")
        pdf.cell(22, 6, f"{row['toxicity_score']:.4f}", border=1, align="C")
        pdf.ln()
    pdf.ln(8)

    pdf.section("5. Recommendations")
    for i, rec in enumerate(recs, 1):
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(8, 7, f"{i}.")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 7, rec)
        pdf.ln(1)
    pdf.ln(6)

    pdf.section("6. Attestation")
    pdf.body(
        f"This report was generated automatically by FinSight LLMOps v1.0 "
        f"and reviewed by {analyst_name} on behalf of {org_name}. "
        "All data reflects queries logged during the specified period."
    )
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(80, 8, "Analyst Signature: ________________________")
    pdf.cell(
        0, 8, f"Date: {datetime.utcnow().strftime('%Y-%m-%d')}",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()
