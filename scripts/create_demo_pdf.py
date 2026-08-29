"""Generate the synthetic PrivateDocs hackathon demonstration agreement."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUTPUT = Path(__file__).resolve().parents[1] / "output" / "pdf" / "private-docs-demo-agreement.pdf"

NAVY = colors.HexColor("#07101D")
INK = colors.HexColor("#132238")
MUTED = colors.HexColor("#586A80")
CYAN = colors.HexColor("#15A9B5")
VIOLET = colors.HexColor("#6459C7")
PALE = colors.HexColor("#EEF6F8")
LINE = colors.HexColor("#D5E0E8")


def page_decoration(canvas, document) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 18 * mm, width, 18 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(18 * mm, height - 11.5 * mm, "PRIVATEDOCS AI")
    canvas.setFillColor(colors.HexColor("#72E5EA"))
    canvas.setFont("Helvetica", 7.5)
    canvas.drawRightString(width - 18 * mm, height - 11.5 * mm, "SYNTHETIC DEMO - NOT A REAL AGREEMENT")
    canvas.setStrokeColor(LINE)
    canvas.line(18 * mm, 13 * mm, width - 18 * mm, 13 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(18 * mm, 8.5 * mm, "Generated for the Integrate Midnight Hackathon")
    canvas.drawRightString(width - 18 * mm, 8.5 * mm, f"Page {document.page}")
    canvas.restoreState()


def build() -> Path:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=27 * mm,
        bottomMargin=20 * mm,
        title="Synthetic Confidential Services Agreement",
        author="PrivateDocs AI",
        subject="Non-sensitive demonstration document",
        invariant=1,
    )

    base = getSampleStyleSheet()
    styles = {
        "eyebrow": ParagraphStyle(
            "Eyebrow",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=CYAN,
            spaceAfter=5,
            tracking=1.3,
        ),
        "title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=28,
            leading=31,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=8,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["Normal"],
            fontSize=11,
            leading=16,
            textColor=MUTED,
            spaceAfter=14,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=19,
            textColor=INK,
            spaceBefore=10,
            spaceAfter=7,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=VIOLET,
            spaceBefore=8,
            spaceAfter=10,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.3,
            leading=13.5,
            textColor=INK,
            spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontSize=8,
            leading=11,
            textColor=MUTED,
        ),
        "callout": ParagraphStyle(
            "Callout",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=14,
            textColor=INK,
            backColor=PALE,
            borderColor=CYAN,
            borderWidth=0.8,
            borderPadding=9,
            spaceBefore=10,
            spaceAfter=10,
        ),
        "center": ParagraphStyle(
            "Center",
            parent=base["BodyText"],
            fontSize=8,
            leading=11,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
    }

    story = [
        Spacer(1, 8 * mm),
        Paragraph("CONFIDENTIAL - SYNTHETIC DEMO", styles["eyebrow"]),
        Paragraph("Data Services Agreement", styles["title"]),
        Paragraph(
            "A fictional agreement between Northstar Analytics GmbH and Aurora Field Labs Ltd. "
            "Created solely to demonstrate privacy-preserving document question answering.",
            styles["subtitle"],
        ),
        HRFlowable(width="100%", thickness=1, color=LINE, spaceAfter=12),
        Table(
            [
                ["Effective date", "1 September 2026"],
                ["Initial term", "12 months"],
                ["Governing law", "Austria"],
                ["Data class", "Confidential - synthetic"],
            ],
            colWidths=[42 * mm, 110 * mm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), PALE),
                    ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
                    ("TEXTCOLOR", (1, 0), (1, -1), INK),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ]
            ),
        ),
        Spacer(1, 8 * mm),
        Paragraph(
            "Demo note: all names, obligations, amounts, addresses and signatures in this PDF are fictional. "
            "The document contains no personal or commercially sensitive data.",
            styles["callout"],
        ),
        Paragraph("1. Parties and purpose", styles["h1"]),
        Paragraph(
            "Northstar Analytics GmbH (the <b>Customer</b>) appoints Aurora Field Labs Ltd. "
            "(the <b>Provider</b>) to deliver a synthetic document-classification pilot. The parties "
            "will use generated test records only; neither party may supply real customer, employee, "
            "patient, payment, or authentication data.",
            styles["body"],
        ),
        Paragraph("2. Services", styles["h1"]),
        Paragraph(
            "The Provider will configure a sandbox, process up to 10,000 fictional records, deliver a "
            "model-evaluation report, and conduct one knowledge-transfer workshop. Production deployment, "
            "automated decision-making, and processing of real personal data are outside scope.",
            styles["body"],
        ),
        Paragraph("3. Fees and acceptance", styles["h1"]),
        Paragraph(
            "The fixed pilot fee is EUR 18,500 excluding tax. Deliverables are accepted unless the Customer "
            "identifies a material written non-conformity within ten business days. The Provider will correct "
            "confirmed non-conformities once without additional charge.",
            styles["body"],
        ),
        PageBreak(),
        Paragraph("OPERATING TERMS", styles["eyebrow"]),
        Paragraph("4. Confidentiality", styles["h1"]),
        Paragraph(
            "Each recipient must protect non-public technical, financial, security, and business information "
            "using at least reasonable care. Confidential information may be used only to perform this Agreement "
            "and disclosed only to personnel and advisers with a need to know and equivalent duties.",
            styles["body"],
        ),
        Paragraph("5. Data handling and security", styles["h1"]),
        Paragraph(
            "The Provider will keep project data in the isolated sandbox, encrypt it in transit and at rest, "
            "apply least-privilege access, maintain access logs, and notify the Customer within 48 hours of a "
            "confirmed security incident affecting project data. Synthetic project records will be deleted "
            "within 30 days after termination, except for immutable security logs retained for 90 days.",
            styles["body"],
        ),
        Paragraph("6. Term and termination", styles["h1"]),
        Paragraph(
            "The initial term is twelve months. Either party may terminate for material breach if the breach "
            "is not cured within 15 days after written notice. The Customer may terminate for convenience on "
            "30 days' written notice and will pay for accepted work completed through the termination date.",
            styles["body"],
        ),
        Paragraph("6.1 Effect of termination and survival", styles["h2"]),
        Paragraph(
            "On termination, each party will return or securely destroy the other party's confidential material, "
            "subject to the deletion periods in Section 5. <b>Sections 4 (Confidentiality), 5 (Data Handling and "
            "Security), 7 (Intellectual Property), 9 (Audit and Compliance), 10 (Liability), and 12 (Disputes) "
            "survive termination for five years.</b> Obligations protecting trade secrets survive for as long as "
            "the information remains a trade secret under applicable law. Accrued payment obligations also survive.",
            styles["callout"],
        ),
        Paragraph("7. Intellectual property", styles["h1"]),
        Paragraph(
            "Each party retains its pre-existing materials. After full payment, the Customer owns the bespoke "
            "evaluation report. The Provider retains its general tools, templates, methods, and know-how and grants "
            "the Customer a perpetual license to embedded Provider materials solely as required to use the report.",
            styles["body"],
        ),
        Paragraph("8. Subcontractors", styles["h1"]),
        Paragraph(
            "The Provider may use listed subprocessors for infrastructure and support, remains responsible for "
            "their performance, and will give 14 days' notice before adding a subprocessor with access to project data.",
            styles["body"],
        ),
        PageBreak(),
        Paragraph("GOVERNANCE", styles["eyebrow"]),
        Paragraph("9. Audit and compliance", styles["h1"]),
        Paragraph(
            "Once per contract year, the Customer may request current security policies, a summary of the most "
            "recent independent assessment, and evidence that project-data deletion controls operated. Any on-site "
            "review requires 20 business days' notice, must avoid access to other customers' data, and is limited "
            "to one business day unless a confirmed incident justifies more.",
            styles["body"],
        ),
        Paragraph("10. Liability", styles["h1"]),
        Paragraph(
            "Neither party is liable for indirect or consequential loss. Aggregate liability is capped at fees paid "
            "during the preceding twelve months, except that the cap does not apply to fraud, wilful misconduct, "
            "breach of confidentiality, or infringement of the other party's intellectual property rights.",
            styles["body"],
        ),
        Paragraph("11. Notices", styles["h1"]),
        Paragraph(
            "Formal notices must be delivered by tracked courier or email with receipt confirmation to the fictional "
            "addresses below. Operational chat messages are not formal notice.",
            styles["body"],
        ),
        Table(
            [
                ["Customer", "Northstar Analytics GmbH\n48 Example Quay, 1010 Vienna\nlegal@northstar.invalid"],
                ["Provider", "Aurora Field Labs Ltd.\n7 Fiction Lane, Dublin 2\ncontracts@aurora.invalid"],
            ],
            colWidths=[32 * mm, 120 * mm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), PALE),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("TEXTCOLOR", (0, 0), (-1, -1), INK),
                    ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ]
            ),
        ),
        Paragraph("12. Disputes and general terms", styles["h1"]),
        Paragraph(
            "Senior representatives will first attempt good-faith resolution for 20 business days. Unresolved "
            "disputes are subject to the exclusive courts of Vienna, Austria. This Agreement is the complete "
            "understanding for the pilot and may be amended only in a signed writing. Neither party may assign it "
            "without consent, except with a merger or sale of substantially all relevant assets.",
            styles["body"],
        ),
        Spacer(1, 5 * mm),
        KeepTogether(
            [
                HRFlowable(width="100%", thickness=1, color=LINE, spaceAfter=8),
                Table(
                    [
                        ["For Northstar Analytics GmbH", "For Aurora Field Labs Ltd."],
                        ["/s/ Elina Example", "/s/ Marco Sample"],
                        ["Elina Example, COO", "Marco Sample, Director"],
                        ["29 August 2026", "29 August 2026"],
                    ],
                    colWidths=[76 * mm, 76 * mm],
                    style=TableStyle(
                        [
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Oblique"),
                            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                            ("TEXTCOLOR", (0, 0), (-1, -1), INK),
                            ("LINEABOVE", (0, 1), (-1, 1), 0.5, LINE),
                            ("TOPPADDING", (0, 0), (-1, -1), 6),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                        ]
                    ),
                ),
            ]
        ),
        Spacer(1, 6 * mm),
        Paragraph(
            "END OF SYNTHETIC DEMONSTRATION DOCUMENT",
            styles["center"],
        ),
    ]

    document.build(story, onFirstPage=page_decoration, onLaterPages=page_decoration)
    return OUTPUT


if __name__ == "__main__":
    print(build())
