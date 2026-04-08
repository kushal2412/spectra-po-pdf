"""
Spectra Constructions — PO Review PDF Generation API
Receives structured review data from Make.com, generates branded PDF, returns base64.
"""
import os
import io
import base64
import json
from datetime import datetime
from flask import Flask, request, jsonify

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, Image
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

app = Flask(__name__)

# ── Brand colours ──────────────────────────────────────────────────────────
RED         = colors.HexColor("#C0392B")
RED_LIGHT   = colors.HexColor("#FAEAEA")
RED_MID     = colors.HexColor("#E8A09A")
DARK        = colors.HexColor("#1A1A1A")
MID         = colors.HexColor("#444441")
MUTED       = colors.HexColor("#888780")
FAINT       = colors.HexColor("#C8C6BE")
SURFACE     = colors.HexColor("#F7F6F2")
WHITE       = colors.white
FLAG_BG     = colors.HexColor("#FAEEDA")
FLAG_TXT    = colors.HexColor("#633806")
FLAG_BDR    = colors.HexColor("#EF9F27")
RISK_BG     = colors.HexColor("#FCEBEB")
RISK_TXT    = colors.HexColor("#791F1F")
RISK_BDR    = colors.HexColor("#E24B4A")
PASS_BG     = colors.HexColor("#EAF3DE")
PASS_TXT    = colors.HexColor("#27500A")
PASS_BDR    = colors.HexColor("#639922")
INFO_BG     = colors.HexColor("#E6F1FB")
INFO_TXT    = colors.HexColor("#0C447C")
INFO_BDR    = colors.HexColor("#378ADD")

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm
W = PAGE_W - 2 * MARGIN

def s(name, **kw):
    base = dict(fontName="Helvetica", fontSize=8.5, leading=13,
                textColor=MID, spaceAfter=0, spaceBefore=0)
    base.update(kw)
    return ParagraphStyle(name, **base)

ST = {
    "sec":      s("sec",  fontName="Helvetica-Bold", fontSize=9.5, textColor=RED, leading=13),
    "h3":       s("h3",   fontName="Helvetica-Bold", fontSize=8.5, textColor=DARK, leading=12),
    "body":     s("body", fontSize=8.5, leading=13, textColor=MID),
    "small":    s("small",fontSize=7.5, leading=11, textColor=MUTED),
    "bold":     s("bold", fontName="Helvetica-Bold", fontSize=8.5, textColor=DARK, leading=12),
    "flag":     s("flag", fontName="Helvetica-Bold", fontSize=8,   textColor=FLAG_TXT, leading=11),
    "risk":     s("risk", fontName="Helvetica-Bold", fontSize=8,   textColor=RISK_TXT, leading=11),
    "pass":     s("pass", fontName="Helvetica-Bold", fontSize=8,   textColor=PASS_TXT, leading=11),
    "info":     s("info", fontName="Helvetica-Bold", fontSize=8,   textColor=INFO_TXT, leading=11),
    "red_bold": s("rb",   fontName="Helvetica-Bold", fontSize=8,   textColor=RED, leading=11),
    "ml":       s("ml",   fontSize=7,  textColor=MUTED,  leading=10),
    "mv":       s("mv",   fontName="Helvetica-Bold", fontSize=8.5, textColor=DARK, leading=12),
    "right":    s("right",fontSize=7.5, textColor=MUTED, leading=11, alignment=TA_RIGHT),
    "center":   s("center",fontSize=8, textColor=MID, leading=12, alignment=TA_CENTER),
    "tagline":  s("tagline", fontSize=7.5, textColor=MUTED, leading=10, alignment=TA_RIGHT),
    "verdict_flag": s("vf", fontName="Helvetica-Bold", fontSize=9, textColor=FLAG_TXT, leading=13),
    "verdict_risk": s("vr", fontName="Helvetica-Bold", fontSize=9, textColor=RISK_TXT, leading=13),
    "verdict_pass": s("vp", fontName="Helvetica-Bold", fontSize=9, textColor=PASS_TXT, leading=13),
}

def P(text, style="body"):
    # Escape any HTML-like content except our known tags
    text = str(text)
    return Paragraph(text, ST[style])

def SP(h): return Spacer(1, h * mm)

def HR():
    return HRFlowable(width=W, thickness=0.5, color=colors.HexColor("#D3D1C7"),
                      spaceAfter=0, spaceBefore=0)

def badge(text, kind="pass"):
    lut = {
        "pass":  (PASS_BG,  PASS_TXT,  PASS_BDR),
        "flag":  (FLAG_BG,  FLAG_TXT,  FLAG_BDR),
        "risk":  (RISK_BG,  RISK_TXT,  RISK_BDR),
        "info":  (INFO_BG,  INFO_TXT,  INFO_BDR),
        "red":   (RED_LIGHT, RED,      RED_MID),
        "clear": (PASS_BG,  PASS_TXT,  PASS_BDR),
        "flagged":(FLAG_BG, FLAG_TXT,  FLAG_BDR),
    }
    bg, fg, bdr = lut.get(kind.lower(), lut["info"])
    ps = ParagraphStyle(f"bdg_{kind}", fontName="Helvetica-Bold",
                        fontSize=7, textColor=fg, leading=9)
    t = Table([[Paragraph(str(text), ps)]])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), bg),
        ("BOX",           (0,0), (-1,-1), 0.5, bdr),
        ("TOPPADDING",    (0,0), (-1,-1), 2),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("RIGHTPADDING",  (0,0), (-1,-1), 6),
    ]))
    return t

def section_header(number, title, badge_text, badge_kind):
    bdg = badge(badge_text, badge_kind)
    combined_ps = ParagraphStyle("shdr", fontName="Helvetica-Bold", fontSize=9,
                                  textColor=DARK, leading=12)
    num_tag   = f'<font color="#C0392B">{number}</font>'
    title_tag = f'<font color="#1A1A1A">  {title.upper()}</font>'
    combined  = Paragraph(num_tag + title_tag, combined_ps)
    inner = Table(
        [[combined, bdg]],
        colWidths=[W - 34*mm, 34*mm]
    )
    inner.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor("#ECEAE2")),
        ("LINEABOVE",     (0,0), (-1,0),  0.5, colors.HexColor("#B0AEA6")),
        ("LINEBELOW",     (0,0), (-1,-1), 0.5, colors.HexColor("#B0AEA6")),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("RIGHTPADDING",  (0,0), (-1,-1), 8),
        ("ALIGN",         (1,0), (1,0),   "RIGHT"),
    ]))
    return inner

def note(text, kind="info"):
    lut = {
        "info": (INFO_BG,  INFO_TXT,  INFO_BDR),
        "flag": (FLAG_BG,  FLAG_TXT,  FLAG_BDR),
        "risk": (RISK_BG,  RISK_TXT,  RISK_BDR),
        "pass": (PASS_BG,  PASS_TXT,  PASS_BDR),
    }
    bg, fg, bdr = lut.get(kind.lower(), lut["info"])
    ps = ParagraphStyle(f"nt_{kind}", fontName="Helvetica",
                        fontSize=8, textColor=fg, leading=12)
    t = Table([[Paragraph(str(text), ps)]], colWidths=[W])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), bg),
        ("LINEBEFORE",    (0,0), (0,-1),  2, bdr),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ("RIGHTPADDING",  (0,0), (-1,-1), 10),
    ]))
    return t

def dtable(headers, rows, col_widths):
    hrow = [P(h, "bold") for h in headers]
    data = [hrow] + rows
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("LINEBELOW",     (0,0), (-1,0),  0.8, DARK),
        ("LINEBELOW",     (0,1), (-1,-1), 0.3, FAINT),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 4),
        ("RIGHTPADDING",  (0,0), (-1,-1), 4),
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, SURFACE]),
    ]))
    return t

def kv_block(pairs):
    rows = []
    for i in range(0, len(pairs), 2):
        row = []
        for label, val in pairs[i:i+2]:
            row += [P(label, "ml"), P(val, "mv")]
        while len(row) < 4:
            row += [P("", "ml"), P("", "mv")]
        rows.append(row)
    cw = [W/2 * 0.35, W/2 * 0.65, W/2 * 0.35, W/2 * 0.65]
    t = Table(rows, colWidths=cw)
    t.setStyle(TableStyle([
        ("LINEBELOW",     (0,0), (-1,-1), 0.3, FAINT),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (-1,-1), 4),
        ("RIGHTPADDING",  (0,0), (-1,-1), 4),
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
    ]))
    return t


def build_pdf(data):
    """Build the branded PDF from structured review data. Returns bytes."""
    buf = io.BytesIO()

    po_number    = data.get("poNumber", "—")
    supplier     = data.get("supplierName", "—")
    po_type      = data.get("poType", "—")
    po_date      = data.get("poDate", datetime.now().strftime("%d %B %Y"))
    project      = data.get("project", "Spectra Project")
    verdict      = data.get("verdict", "FLAGGED").upper()
    flag_count   = data.get("flagCount", 0)
    sections     = data.get("sections", [])  # list of {number, title, badgeText, badgeKind, content}
    flags_summary = data.get("flagsSummary", [])  # list of {ref, kind, title, finding, severity, action}

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title=f"PO Review — {po_number}",
        author="Spectra Constructions Private Limited"
    )
    story = []

    # ── HEADER ────────────────────────────────────────────────────────────
    logo_path = os.path.join(os.path.dirname(__file__), "spectra_logo.jpg")
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=38*mm, height=12*mm)
        logo.hAlign = "LEFT"
        logo_cell = logo
    else:
        logo_cell = P("SPECTRA", "bold")

    hdr = Table([
        [logo_cell,
         [P("PURCHASE ORDER REVIEW REPORT", "bold"),
          SP(0.5),
          P("Automated procurement analysis  ·  Confidential  ·  Internal use only", "small")],
         [P("Living, Built by Design", "tagline"),
          SP(0.5),
          P(po_date, "right")]]
    ], colWidths=[42*mm, W - 42*mm - 44*mm, 44*mm])
    hdr.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
        ("LEFTPADDING",   (0,0), (-1,-1), 0),
        ("RIGHTPADDING",  (0,0), (-1,-1), 0),
        ("ALIGN",         (2,0), (2,0),   "RIGHT"),
    ]))
    story.append(hdr)
    story.append(SP(2))
    story.append(HRFlowable(width=W, thickness=1.5, color=RED, spaceAfter=0, spaceBefore=0))
    story.append(SP(4))

    # ── PO DETAILS ────────────────────────────────────────────────────────
    story.append(kv_block([
        ("PO number",   po_number),
        ("PO type",     po_type),
        ("PO date",     po_date),
        ("Vendor",      supplier),
        ("Project",     project),
        ("Review date", datetime.now().strftime("%d %B %Y")),
    ]))
    story.append(SP(4))

    # ── VERDICT ───────────────────────────────────────────────────────────
    if verdict == "CLEAR":
        v_style = "verdict_pass"
        v_bg = PASS_BG
        v_bdr = PASS_BDR
        v_text = "CLEAR — NO CRITICAL FLAGS RAISED"
        v_sub = "Review complete  ·  Proceed to approval"
    else:
        v_style = "verdict_flag"
        v_bg = FLAG_BG
        v_bdr = FLAG_BDR
        v_text = f"FLAGGED — REVIEW REQUIRED BEFORE APPROVAL"
        v_sub = f"{flag_count} flag{'s' if flag_count != 1 else ''} raised  ·  see Summary section for required actions"

    v = Table([
        [P(v_text, v_style),
         P(v_sub, "right")]
    ], colWidths=[W * 0.60, W * 0.40])
    v.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), v_bg),
        ("LINEBEFORE",    (0,0), (0,-1),  3, v_bdr),
        ("TOPPADDING",    (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ("RIGHTPADDING",  (0,0), (-1,-1), 10),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(v)
    story.append(SP(7))

    # ── SECTIONS ──────────────────────────────────────────────────────────
    for sec in sections:
        num        = sec.get("number", "01")
        title      = sec.get("title", "Section")
        badge_text = sec.get("badgeText", "Review")
        badge_kind = sec.get("badgeKind", "info")
        content    = sec.get("content", "")  # plain text paragraphs

        story.append(KeepTogether([
            section_header(num, title, badge_text, badge_kind),
            SP(3),
        ]))

        # Render each paragraph of the section content
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    item_type = item.get("type", "body")
                    item_text = item.get("text", "")
                    item_kind = item.get("kind", "info")
                    if item_type == "note":
                        story.append(note(item_text, item_kind))
                    elif item_type == "table":
                        headers = item.get("headers", [])
                        rows_data = item.get("rows", [])
                        col_pcts = item.get("colWidths", [])
                        col_widths = [W * p for p in col_pcts] if col_pcts else [W / max(len(headers), 1)] * len(headers)
                        tbl_rows = []
                        for row in rows_data:
                            tbl_rows.append([P(str(cell), "body") for cell in row])
                        if headers and tbl_rows:
                            story.append(dtable(headers, tbl_rows, col_widths))
                    else:
                        story.append(P(item_text, item_type if item_type in ST else "body"))
                else:
                    story.append(P(str(item), "body"))
                story.append(SP(1))
        else:
            # Plain text — split by newline into paragraphs
            for line in str(content).split("\n"):
                line = line.strip()
                if line:
                    story.append(P(line, "body"))
                    story.append(SP(1))

        story.append(SP(6))

    # ── FLAGS SUMMARY ─────────────────────────────────────────────────────
    if flags_summary:
        story.append(section_header(
            f"0{len(sections)+1}" if len(sections) < 9 else str(len(sections)+1),
            "Summary of flags & required actions",
            f"{len(flags_summary)} item{'s' if len(flags_summary) != 1 else ''} · action required",
            "risk"
        ))
        story.append(SP(3))

        flag_rows = []
        for f in flags_summary:
            ref      = f.get("ref", "F1")
            kind     = f.get("kind", "flag")
            title    = f.get("title", "")
            finding  = f.get("finding", "")
            severity = f.get("severity", "")
            action   = f.get("action", "")
            flag_rows.append([
                P(ref, "bold"),
                badge(kind.upper(), kind),
                [P(title, "bold"), SP(0.5), P(finding, "body")],
                P(severity, "body"),
                P(action, "body"),
            ])

        t_flags = Table(flag_rows, colWidths=[8*mm, 12*mm, W*0.30, W*0.22, W*0.33])
        t_flags.setStyle(TableStyle([
            ("LINEBELOW",     (0,0), (-1,-1), 0.3, FAINT),
            ("TOPPADDING",    (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("LEFTPADDING",   (0,0), (-1,-1), 4),
            ("RIGHTPADDING",  (0,0), (-1,-1), 4),
            ("VALIGN",        (0,0), (-1,-1), "TOP"),
            ("ALIGN",         (1,0), (1,-1),  "CENTER"),
            ("ROWBACKGROUNDS",(0,0), (-1,-1), [WHITE, SURFACE]),
        ]))
        story.append(t_flags)
        story.append(SP(7))

    # ── FOOTER ────────────────────────────────────────────────────────────
    story.append(HRFlowable(width=W, thickness=1.5, color=RED, spaceAfter=0, spaceBefore=0))
    story.append(SP(2))
    ft = Table([[
        P("This report is auto-generated by Spectra Constructions' procurement review system. "
          "For internal review only. Approval or rejection rests with the authorised signatory. "
          "Market rates are indicative and sourced from publicly available data.", "small"),
        P("Spectra Constructions Private Limited\nGSTIN: 29AAFCS8564H1ZS\naccounts@spectra.co.in", "small"),
    ]], colWidths=[W*0.65, W*0.35])
    ft.setStyle(TableStyle([
        ("ALIGN",         (1,0), (1,0),  "RIGHT"),
        ("VALIGN",        (0,0), (-1,-1),"TOP"),
        ("TOPPADDING",    (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
        ("LEFTPADDING",   (0,0), (-1,-1), 0),
        ("RIGHTPADDING",  (0,0), (-1,-1), 0),
    ]))
    story.append(ft)

    doc.build(story)
    buf.seek(0)
    return buf.read()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "Spectra PO PDF Generator"})


@app.route("/generate-pdf", methods=["POST"])
def generate_pdf():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON body received"}), 400

        pdf_bytes = build_pdf(data)
        pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

        po_number = data.get("poNumber", "PO-Review")
        filename = f"Spectra_PO_Review_{po_number.replace('/', '-')}.pdf"

        return jsonify({
            "success": True,
            "filename": filename,
            "pdf_base64": pdf_b64,
            "size_bytes": len(pdf_bytes)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
