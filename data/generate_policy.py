"""Generate a synthetic FinCorp AI Governance & Compliance Policy PDF."""

import sys
from pathlib import Path

from fpdf import FPDF, XPos, YPos


class PolicyPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_fill_color(15, 17, 39)
        self.rect(0, 0, 210, 18, "F")
        self.set_text_color(255, 255, 255)
        self.cell(
            0, 8, "  FINCORP FINANCIAL TECHNOLOGIES  |  CONFIDENTIAL",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L",
        )
        self.set_text_color(0, 0, 0)
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(
            0, 10,
            f"AI Governance & Compliance Policy v2.4  |  Page {self.page_no()} of {{nb}}  |  Classification: Internal",
            align="C",
        )

    def chapter_title(self, number: str, title: str):
        self.set_font("Helvetica", "B", 13)
        self.set_fill_color(245, 245, 245)
        self.set_text_color(20, 20, 80)
        self.cell(
            0, 10, f"Section {number}  -  {title}",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True,
        )
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def clause(self, number: str, text: str):
        self.set_font("Helvetica", "B", 10)
        self.cell(18, 7, number)
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 7, text)
        self.ln(1)

    def body_text(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 6, text)
        self.ln(2)

    def kv_row(self, key: str, value: str):
        self.set_font("Helvetica", "B", 10)
        self.cell(70, 7, key, border="B")
        self.set_font("Helvetica", "", 10)
        self.cell(0, 7, value, border="B", new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def generate(output_path: str = "data/fincorp_ai_policy.pdf"):
    pdf = PolicyPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # -----------------------------------------------------------------------
    # Cover Page
    # -----------------------------------------------------------------------
    pdf.add_page()
    pdf.ln(20)
    pdf.set_font("Helvetica", "B", 26)
    pdf.set_text_color(20, 20, 80)
    pdf.cell(
        0, 14, "FinCorp Financial Technologies",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C",
    )
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(239, 68, 68)
    pdf.cell(
        0, 10, "AI Governance & Compliance Policy",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C",
    )
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(
        0, 8, "Version 2.4  |  Effective Date: January 1, 2025",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C",
    )
    pdf.cell(
        0, 8, "Owner: Global AI Risk & Ethics Committee",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C",
    )
    pdf.ln(10)

    pdf.set_draw_color(239, 68, 68)
    pdf.set_line_width(0.8)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(10)

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 8, "Document Control", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    pdf.kv_row("Classification:", "Internal - Restricted Distribution")
    pdf.kv_row("Review Cycle:", "Annual (or upon material AI system changes)")
    pdf.kv_row("Regulatory Framework:", "PCI DSS v4.0, GDPR, CCPA, EU AI Act")
    pdf.kv_row("Supersedes:", "AI Ethics Guidelines v1.9 (March 2023)")
    pdf.ln(10)

    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(
        0, 6,
        "This document establishes binding requirements for the design, deployment, monitoring, "
        "and retirement of artificial intelligence systems operated by or on behalf of the organization. "
        "Violations may result in disciplinary action, project suspension, or regulatory reporting.",
    )

    # -----------------------------------------------------------------------
    # Page 2 - Sections 1 & 2
    # -----------------------------------------------------------------------
    pdf.add_page()

    pdf.chapter_title("1", "Purpose & Scope")
    pdf.body_text(
        "This Policy governs all AI and machine learning systems used in the organization's payment "
        "networks, fraud prevention infrastructure, customer analytics platforms, and partner-facing "
        "APIs. It applies to all employees, contractors, and third-party vendors who "
        "develop, operate, or procure AI systems on behalf of the organization."
    )
    pdf.clause("1.1", "This Policy applies to Large Language Models (LLMs), generative AI tools, predictive ML models, and agentic AI systems deployed in production or used for internal decision support.")
    pdf.clause("1.2", "Third-party AI providers must contractually agree to these standards before integration. Non-compliant vendors will be subject to immediate contract review.")
    pdf.clause("1.3", "Experimental and research-phase AI systems are exempt from Sections 4-7 but must comply with Sections 2 and 3 at all times.")

    pdf.ln(4)
    pdf.chapter_title("2", "AI Model Deployment Standards")
    pdf.body_text(
        "All AI models must complete a formal Model Risk Assessment (MRA) before production deployment. "
        "The MRA must be reviewed by the AI Risk & Ethics Committee and signed off by the CISO and "
        "relevant business owner. Deployment without MRA approval is a Tier-1 policy violation."
    )
    pdf.clause("2.1", "Models must be validated on representative, bias-tested datasets before production approval. Validation reports are retained for a minimum of 5 years.")
    pdf.clause("2.2", "All models generating customer-facing outputs must include confidence thresholds. Outputs below the approved threshold must be flagged for human review.")
    pdf.clause("2.3", "LLMs deployed for financial advisory, compliance, or fraud detection must be RAG-augmented with verified, versioned knowledge bases. Ungrounded LLM responses in these domains are prohibited.")
    pdf.clause("2.4", "Model versioning and rollback capabilities are mandatory. Each production model must have a tested rollback procedure with an RTO of less than 4 hours.")
    pdf.clause("2.5", "Shadow deployment (parallel running of new vs. existing model) is required for 30 days before full production cutover for any model replacing a Tier-1 system.")

    # -----------------------------------------------------------------------
    # Page 3 - Sections 3 & 4
    # -----------------------------------------------------------------------
    pdf.add_page()

    pdf.chapter_title("3", "Data Privacy Requirements")
    pdf.body_text(
        "AI systems handling organizational or cardholder data must comply with PCI DSS v4.0, "
        "GDPR Article 22 (automated decision-making), and applicable regional privacy laws. "
        "Data used for AI training or inference must be classified and handled according to "
        "the Global Data Classification Standard."
    )
    pdf.clause("3.1", "Personally Identifiable Information (PII) including names, card numbers, SSNs, biometrics, and transaction history must never be included in LLM training datasets or prompts without explicit written authorization from the Data Governance team.")
    pdf.clause("3.2", "Biometric data (fingerprints, facial recognition, voice) may only be used for identity verification if processed in a certified Trusted Execution Environment (TEE) with zero data retention after the session.")
    pdf.clause("3.3", "Synthetic data used for model training must be validated to ensure it does not encode real cardholder information through re-identification attacks.")
    pdf.clause("3.4", "AI inference logs containing query text must be masked, tokenized, or aggregated before storage. Raw query logs are subject to a 90-day retention limit unless subject to legal hold.")

    pdf.ln(4)
    pdf.chapter_title("4", "Prohibited Use Cases for AI")
    pdf.body_text(
        "The following use cases are explicitly prohibited and may not be pursued without "
        "a formal exception approved by the Board-level AI Ethics Committee. Exceptions are "
        "granted only for legitimate law-enforcement cooperation with appropriate legal authority."
    )
    pdf.clause("4.1", "AI systems must not be used to generate, infer, or reconstruct customer Social Security Numbers, full card numbers, or CVVs from partial data.")
    pdf.clause("4.2", "Discriminatory use of AI in credit decisioning based on protected characteristics (race, gender, religion, nationality, disability) is strictly prohibited and may constitute a violation of the Equal Credit Opportunity Act.")
    pdf.clause("4.3", "Generative AI must not be used to create synthetic fraudulent transaction records, counterfeit card templates, or phishing content under any circumstance.")
    pdf.clause("4.4", "AI must not make autonomous, unreviewed decisions to freeze or terminate customer accounts. A human-in-the-loop review is mandatory for all account-level adverse actions.")
    pdf.clause("4.5", "Mass surveillance of cardholder behaviour beyond fraud prevention scope, including political profiling or behavioural manipulation, is prohibited.")

    # -----------------------------------------------------------------------
    # Page 4 - Sections 5, 6, 7
    # -----------------------------------------------------------------------
    pdf.add_page()

    pdf.chapter_title("5", "Hallucination Risk Thresholds & Mitigation")
    pdf.body_text(
        "LLMs deployed in regulated or customer-facing contexts must be monitored continuously "
        "for hallucination risk. Hallucination is defined as any model output that is factually "
        "incorrect, unverifiable against the grounding context, or inconsistent with known facts."
    )
    pdf.clause("5.1", "LOW Risk (Confidence below 10%): Response is consistent with provided context. Automated processing permitted. Logged for audit.")
    pdf.clause("5.2", "MEDIUM Risk (Confidence 10-30%): Response contains unverifiable claims. Output must be flagged with a disclaimer. Human review recommended before external distribution.")
    pdf.clause("5.3", "HIGH Risk (Confidence above 30%): Response contradicts grounding context or verified facts. Output must be blocked or quarantined. Immediate human review mandatory. Incident ticket auto-created.")
    pdf.clause("5.4", "All LLMs must use Retrieval-Augmented Generation (RAG) with verified policy documents as the primary grounding mechanism. Ungrounded LLM outputs in regulated domains trigger automatic HIGH risk classification.")
    pdf.clause("5.5", "Hallucination metrics must be reported in monthly AI Risk Dashboards submitted to the AI Risk & Ethics Committee.")

    pdf.ln(4)
    pdf.chapter_title("6", "Bias Detection Requirements")
    pdf.body_text(
        "AI systems must be tested for demographic bias, representational bias, and proxy "
        "discrimination before deployment and on a quarterly basis thereafter."
    )
    pdf.clause("6.1", "Fraud detection models must be tested against demographic subgroups (gender, age, geography) to ensure false positive rates do not exceed 1.5x the population-level baseline for any protected group.")
    pdf.clause("6.2", "Credit scoring AI must comply with Fair Credit Reporting Act (FCRA) and Equal Credit Opportunity Act (ECOA). Adverse action notices must include model-interpretable explanations.")
    pdf.clause("6.3", "Query categorization and routing systems must be audited semi-annually to detect topic-based bias that could result in differential service quality.")

    pdf.ln(4)
    pdf.chapter_title("7", "Incident Reporting & Responsible AI Principles")
    pdf.body_text(
        "Any AI system producing HIGH-risk outputs, discriminatory decisions, or data breaches "
        "must be reported within 2 hours to the AI Incident Response Team via the AIRT portal."
    )
    pdf.clause("7.1", "Responsible AI principles: Fairness, Transparency, Accountability, Reliability, Privacy, and Inclusivity. All AI systems are evaluated against these six dimensions during MRA.")
    pdf.clause("7.2", "Explainability: Any AI decision affecting a customer must be explainable in plain English upon request. Black-box models in Tier-1 systems must be accompanied by a surrogate explainability layer (SHAP or LIME).")
    pdf.clause("7.3", "Penalties for non-compliance: Tier-1 violations (prohibited use cases, unreported HIGH-risk incidents) result in immediate project suspension and mandatory regulatory disclosure. Tier-2 violations result in remediation plan within 30 days.")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    pdf.output(output_path)
    print(f"Policy PDF generated: {output_path}")
    return output_path


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "data/fincorp_ai_policy.pdf"
    generate(out)
