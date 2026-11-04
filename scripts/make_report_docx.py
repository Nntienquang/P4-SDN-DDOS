#!/usr/bin/env python3
"""
make_report_docx.py — Chuyển docs/BAO_CAO_KET_QUA.md sang Word (.docx).

- Trang bìa (tên đề tài, chỗ điền nhóm/GVHD), mục lục tự động (Word cập nhật khi mở).
- Nội dung báo cáo; hình kết quả chèn vào cuối mục tương ứng, đánh số "Hình T.k"
  khớp với cách đánh số trong figures/README.md mà nội dung đang trích dẫn.
- Phụ lục A: bảng đầy đủ từ results/RESULTS.md.
- Định dạng: A4, lề trên/dưới 2 cm, trái 3 cm, phải 2 cm; Times New Roman 13pt.

Chỉ hiểu phần Markdown mà các file báo cáo này dùng: tiêu đề #..####, đoạn văn,
danh sách "- " (1 cấp, dòng tiếp thụt lề), bảng "| |", khối code ```, trích dẫn ">",
in đậm **x**, nghiêng *x*, `code`, liên kết [chữ](đích) (giữ chữ).

Chạy:  python3 scripts/make_report_docx.py            (cần: pip install python-docx)
"""
import argparse
import os
import re

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = "Times New Roman"
MONO = "Courier New"
DARK = RGBColor(0x14, 0x21, 0x3D)

# Mục (tiền tố tiêu đề) -> các hình chèn ở CUỐI mục đó
FIGS_BY_SECTION = {
    "## 3.": ["tuan04/counter_realtime_S3.png", "tuan04/poll_interval.png",
              "tuan05/four_traffic_types.png", "tuan05/probe_no_defense.png"],
    "## 4.": ["tuan06/feature_distribution.png", "tuan06/dataset_composition.png",
              "tuan06/baseline_flash_fpr.png"],
    "## 5.": ["tuan07/model_compare.png", "tuan07/feature_importance.png",
              "tuan07/confusion_rf.png"],
    "## 6.": ["tuan08/online_detection_S5.png", "tuan09/mitigation_timeline_S5.png",
              "tuan09/blocked_hosts.png"],
    "### 7.1": ["tuan10/lsr_attack.png", "tuan10/user_sr_attack.png"],
    "### 7.2": ["tuan10/fpr.png", "tuan10/flash_sr.png",
                "tuan11/timeline_S5_all.png", "tuan11/tradeoff_S5.png"],
}


def figure_index(readme):
    """{path: (số hình 'T.k', chú thích)} theo thứ tự trong figures/README.md."""
    out, week, k = {}, None, 0
    lines = open(readme, encoding="utf-8").read().splitlines()
    for i, ln in enumerate(lines):
        m = re.match(r"## Tuần (\d+)", ln)
        if m:
            week, k = int(m.group(1)), 0
            continue
        m = re.match(r"!\[[^\]]*\]\(([^)]+)\)", ln)
        if m and week is not None:
            k += 1
            cap = ""
            for nxt in lines[i + 1:i + 4]:
                if nxt.startswith("*") and nxt.endswith("*"):
                    cap = nxt.strip("*")
                    break
            out[m.group(1)] = ("%d.%d" % (week, k), cap)
    return out


# ---------------------------------------------------------------- định dạng
def set_cell_shading(cell, hex_fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tc_pr.append(shd)


def set_font(run, name=FONT, size=None, bold=None, italic=None, color=None):
    run.font.name = name
    run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), name)
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color is not None:
        run.font.color.rgb = color


INLINE = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\)|(?<![*\w])\*[^*\s][^*]*\*(?!\*))")


def add_inline(par, text, size=None, base_bold=False):
    """Thêm text có **đậm**, *nghiêng*, `code`, [link](x) vào paragraph."""
    pos = 0
    for m in INLINE.finditer(text):
        if m.start() > pos:
            set_font(par.add_run(text[pos:m.start()]), size=size, bold=base_bold or None)
        tok = m.group(0)
        if tok.startswith("**"):
            add_inline(par, tok[2:-2], size=size, base_bold=True)
        elif tok.startswith("`"):
            set_font(par.add_run(tok[1:-1]), name=MONO, size=(size or 13) - 1.5,
                     bold=base_bold or None)
        elif tok.startswith("["):
            label = re.match(r"\[([^\]]+)\]", tok).group(1)
            add_inline(par, label, size=size, base_bold=base_bold)
        else:
            set_font(par.add_run(tok[1:-1]), size=size, italic=True,
                     bold=base_bold or None)
        pos = m.end()
    if pos < len(text):
        set_font(par.add_run(text[pos:]), size=size, bold=base_bold or None)


def setup_styles(doc):
    st = doc.styles["Normal"]
    st.font.name = FONT
    st.font.size = Pt(13)
    st.element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), FONT)
    pf = st.paragraph_format
    pf.space_after = Pt(6)
    pf.line_spacing = 1.3
    sizes = {1: 16, 2: 14, 3: 13, 4: 13}
    for lvl, sz in sizes.items():
        h = doc.styles["Heading %d" % lvl]
        h.font.name = FONT
        h.font.size = Pt(sz)
        h.font.bold = True
        h.font.italic = (lvl == 4)
        h.font.color.rgb = DARK
        h.element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), FONT)
        h.paragraph_format.space_before = Pt(18 if lvl <= 2 else 12)
        h.paragraph_format.space_after = Pt(6)
        h.paragraph_format.keep_with_next = True
    for name in ("List Bullet",):
        ls = doc.styles[name]
        ls.font.name = FONT
        ls.font.size = Pt(13)


def setup_page(section):
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.top_margin = section.bottom_margin = Cm(2)
    section.left_margin, section.right_margin = Cm(3), Cm(2)


def add_page_number(section):
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
        else:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = text
        run._r.append(el)
    set_font(run, size=11)


def add_toc(doc):
    p = doc.add_paragraph()
    run = p.add_run()
    parts = [("begin", None), (None, 'TOC \\o "1-3" \\h \\z \\u'), ("separate", None)]
    for kind, text in parts:
        if kind:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
        else:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = text
        run._r.append(el)
    t = p.add_run("Nhấn chuột phải → Update Field (hoặc F9) để hiện mục lục.")
    set_font(t, italic=True, size=11, color=RGBColor(0x6A, 0x71, 0x79))
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    p.add_run()._r.append(end)
    # yêu cầu Word tự cập nhật trường (mục lục) khi mở file
    settings = doc.settings.element
    upd = OxmlElement("w:updateFields")
    upd.set(qn("w:val"), "true")
    settings.append(upd)


def cover(doc, title):
    def line(text, size, bold=False, italic=False, before=0, after=6, color=None):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(before)
        p.paragraph_format.space_after = Pt(after)
        set_font(p.add_run(text), size=size, bold=bold, italic=italic, color=color)
    line("[TÊN TRƯỜNG]", 13, bold=True)
    line("[TÊN KHOA]", 13, bold=True, after=60)
    line("BÁO CÁO", 14, bold=True)
    line("ĐỀ TÀI NGHIÊN CỨU KHOA HỌC SINH VIÊN", 14, bold=True, after=40)
    line(title.upper(), 18, bold=True, color=DARK, after=60)
    line("Nhóm thực hiện: [Tên thành viên]", 13)
    line("Giảng viên hướng dẫn: [Tên GVHD]", 13, after=120)
    line("[Thành phố], tháng 11/2026", 13, italic=True)
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


# ---------------------------------------------------------------- markdown
def parse_table(lines):
    rows = []
    for ln in lines:
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        rows.append(cells)
    return rows


def add_table(doc, rows, usable_cm=16.0):
    ncol = max(len(r) for r in rows)
    t = doc.add_table(rows=len(rows), cols=ncol)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    # độ rộng cột theo độ dài chữ dài nhất mỗi cột
    longest = [max(len(r[j]) if j < len(r) else 0 for r in rows) for j in range(ncol)]
    weights = [max(4, min(40, x)) for x in longest]
    total = sum(weights)
    widths = [Cm(usable_cm * w / total) for w in weights]
    size = 11 if ncol <= 5 else 10
    for i, r in enumerate(rows):
        for j in range(ncol):
            cell = t.cell(i, j)
            cell.width = widths[j]
            par = cell.paragraphs[0]
            par.paragraph_format.space_after = Pt(0)
            par.paragraph_format.line_spacing = 1.1
            add_inline(par, r[j] if j < len(r) else "", size=size, base_bold=(i == 0))
            if i == 0:
                set_cell_shading(cell, "DCE3EE")
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def add_code(doc, lines):
    for ln in lines:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.0
        p.paragraph_format.left_indent = Cm(0.5)
        set_font(p.add_run(ln if ln else " "), name=MONO, size=10)
        ppr = p._p.get_or_add_pPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), "F2F2F0")
        ppr.append(shd)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


INSERTED = []          # (số hình, chú thích) theo thứ tự xuất hiện


def add_figure(doc, path, num, cap):
    INSERTED.append((num, cap))
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(path, width=Cm(15.5))
    c = doc.add_paragraph()
    c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    c.paragraph_format.space_after = Pt(12)
    set_font(c.add_run("Hình %s. " % num), size=11, bold=True)
    add_inline(c, cap, size=11)


def render_markdown(doc, text, figs=None, fig_index=None, skip_title=True,
                    heading_shift=0):
    lines = text.splitlines()
    i = 0
    pending = []          # hình chờ chèn ở cuối mục hiện tại

    def flush():
        for rel in pending:
            path = os.path.join(ROOT, "figures", rel)
            if os.path.exists(path):
                num, cap = fig_index.get(rel, ("?", ""))
                add_figure(doc, path, num, cap)
        pending.clear()

    para_buf = []

    def flush_para():
        if para_buf:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            add_inline(p, " ".join(s.strip() for s in para_buf))
            para_buf.clear()

    while i < len(lines):
        ln = lines[i]
        m = re.match(r"^(#{1,4}) (.*)$", ln)
        if m:
            flush_para()
            level = len(m.group(1))
            if level == 1 and skip_title:
                i += 1
                continue
            if figs is not None and level <= 3:
                flush()
                for key, lst in figs.items():
                    if ln.startswith(key):
                        pending.extend(lst)
            h = doc.add_heading(level=min(4, max(1, level - 1 + heading_shift)))
            add_inline(h, m.group(2))
            i += 1
            continue
        if ln.startswith("```"):
            flush_para()
            j = i + 1
            block = []
            while j < len(lines) and not lines[j].startswith("```"):
                block.append(lines[j])
                j += 1
            add_code(doc, block)
            i = j + 1
            continue
        if ln.lstrip().startswith("|"):
            flush_para()
            j = i
            block = []
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                block.append(lines[j])
                j += 1
            add_table(doc, parse_table(block))
            i = j
            continue
        if ln.startswith(">"):
            flush_para()
            block = []
            while i < len(lines) and lines[i].startswith(">"):
                block.append(lines[i].lstrip(">").strip())
                i += 1
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.8)
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            for k, part in enumerate(" ".join(block).split("  ")):
                add_inline(p, part, size=12)
            for r in p.runs:
                r.italic = True
            continue
        if re.match(r"^\s*- ", ln):
            flush_para()
            item = [re.sub(r"^\s*- ", "", ln)]
            i += 1
            while i < len(lines) and lines[i].startswith("  ") and \
                    not re.match(r"^\s*- ", lines[i]) and lines[i].strip():
                item.append(lines[i].strip())
                i += 1
            p = doc.add_paragraph(style="List Bullet")
            p.paragraph_format.space_after = Pt(3)
            add_inline(p, " ".join(item))
            continue
        if not ln.strip() or ln.strip() == "---":
            flush_para()
            i += 1
            continue
        para_buf.append(ln)
        i += 1
    flush_para()
    if figs is not None:
        flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", default=os.path.join(ROOT, "docs", "BAO_CAO_KET_QUA.md"))
    ap.add_argument("--results", default=os.path.join(ROOT, "results", "RESULTS.md"))
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "BAO_CAO_KET_QUA.docx"))
    args = ap.parse_args()

    md = open(args.md, encoding="utf-8").read()
    title_m = re.search(r"^# (.+)$", md, re.M)
    title = title_m.group(1).split("—", 1)[-1].strip() if title_m else "Báo cáo"
    fig_index = figure_index(os.path.join(ROOT, "figures", "README.md"))

    doc = Document()
    setup_styles(doc)
    sec = doc.sections[0]
    setup_page(sec)
    cover(doc, title)

    h = doc.add_paragraph()
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(h.add_run("MỤC LỤC"), size=14, bold=True, color=DARK)
    add_toc(doc)
    body = doc.add_section(WD_SECTION.NEW_PAGE)
    setup_page(body)
    add_page_number(body)

    # mục "Danh mục hình" của bản Markdown trỏ tới file trong repo -> thay bằng
    # danh mục các hình thật sự có trong file Word
    md = re.sub(r"\n## \d+\. Danh mục hình.*?(?=\n## |\Z)", "\n", md, flags=re.S)
    render_markdown(doc, md, figs=FIGS_BY_SECTION, fig_index=fig_index)
    doc.add_heading("Danh mục hình", level=1)
    for num, cap in INSERTED:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        set_font(p.add_run("Hình %s. " % num), size=12, bold=True)
        add_inline(p, cap.split(". ")[0].rstrip(".") + ".", size=12)

    if os.path.exists(args.results):
        doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        doc.add_heading("Phụ lục A — Bảng kết quả đầy đủ", level=1)
        render_markdown(doc, open(args.results, encoding="utf-8").read(),
                        skip_title=True, heading_shift=0)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    doc.save(args.out)
    print("Đã ghi", args.out)


if __name__ == "__main__":
    main()
