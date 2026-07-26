"""按 toc.json 把源 PDF 切成自包含模块 modules/<编号>_<节名>.pdf，
每片加"知识点 / 试题精选 / 答案与解析"三个书签。
边界页采用共享策略（两相邻切片都包含交界页），宁可重复不漏内容。

参考实现，PDF_MAP 与标题关键词都是案例材料专有的，按材料改：见同目录 README.md。
"""

import json
import os
import re

from pypdf import PdfReader, PdfWriter

PDF_MAP = [
    (1, 62, "01_第1-2章_绪论与线性表.pdf", 12),
    (63, 123, "02_第3-4章_栈队列数组与串.pdf", -62),
    (124, 194, "03_第5章_树与二叉树.pdf", -123),
    (195, 263, "04_第6章_图.pdf", -194),
    (264, 330, "05_第7章_查找.pdf", -263),
    (331, 392, "06_第8章_排序.pdf", -330),
]


def locate(book_page):
    for start, end, pdf, off in PDF_MAP:
        if start <= book_page <= end:
            return pdf, book_page + off
    raise ValueError(f"书页 {book_page} 不在任何PDF范围内")


def safe(name):
    return re.sub(r'[\\/:*?"<>|]', "_", name)


readers = {}


def get_reader(path):
    if path not in readers:
        readers[path] = PdfReader(path)
    return readers[path]


def append_pages(writer, start_bp, end_bp):
    for bp in range(start_bp, end_bp + 1):
        pdf_path, pdf_page = locate(bp)
        writer.add_page(get_reader(pdf_path).pages[pdf_page - 1])


def main():
    with open("toc.json", encoding="utf-8") as f:
        toc = json.load(f)
    os.makedirs("modules", exist_ok=True)

    # 主条目流（章+节），用于确定无试题节的讲解结束页
    major = []  # (page, label)
    for ch in toc["chapters"]:
        major.append((ch["page"], f"第{ch['num']}章"))
        for sec in ch["sections"]:
            major.append((sec["page"], sec["num"]))
    major.sort()

    # 小节流，用于确定试题/答案的结束页（含章末条目）
    flat = []
    for ch in toc["chapters"]:
        flat.append((ch["page"], f"第{ch['num']}章"))
        for sec in ch["sections"]:
            flat.append((sec["page"], sec["num"]))
            for sub in sec["subsections"]:
                flat.append((sub["page"], sub["num"]))
        for em in ch.get("end_matter", []):
            flat.append((em["page"], f"第{ch['num']}章{em['title']}"))
    if toc.get("references_page"):
        flat.append((toc["references_page"], "参考文献"))
    flat.sort()

    for ch in toc["chapters"]:
        first_sec = True
        for sec in ch["sections"]:
            subs_ex = [s for s in sec["subsections"] if "试题精选" in s["title"]]
            subs_ans = [s for s in sec["subsections"] if "答案与解析" in s["title"]]

            # 知识点: 节首页(首节含章扉页) -> 试题页(共享) 或 下一主条目页(共享)
            kstart = min(sec["page"], ch["page"]) if first_sec else sec["page"]
            if subs_ex:
                kend = subs_ex[0]["page"]
            else:
                nxt = next((p for p, _ in major if p > sec["page"]), None)
                kend = nxt if nxt else toc.get("references_page", 392)

            writer = PdfWriter()
            append_pages(writer, kstart, kend)
            writer.add_outline_item("知识点", 0)
            n = kend - kstart + 1
            for sub, label in [(subs_ex, "试题精选"), (subs_ans, "答案与解析")]:
                if not sub:
                    continue
                start = sub[0]["page"]
                end = (
                    next(
                        (p for p, _ in flat if p > start),
                        toc.get("references_page", 392),
                    )
                    - 1
                )
                outline_page = n
                append_pages(writer, start, end)
                # pypdf 只能把已存在的页索引解析为有效目标；先追加再建书签。
                writer.add_outline_item(label, outline_page)
                n += end - start + 1

            out = os.path.join("modules", f"{sec['num']}_{safe(sec['title'])}.pdf")
            with open(out, "wb") as f:
                writer.write(f)
            print(f"{sec['num']:5s} {out} ({n}页)")
            first_sec = False


if __name__ == "__main__":
    main()
