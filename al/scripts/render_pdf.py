"""render_pdf.py — 把模块 PDF 渲染成 PNG，供讲解/呈现题目用。

用法:
  uvx --with pypdfium2 --with pillow python render_pdf.py <pdf> <outdir> [--pages 1-3,5] [--scale 2]

输出 <outdir>/<pdf文件名去扩展名>_p<页码>.png，打印生成的文件列表 JSON。
"""

import argparse
import json
import os
import sys

# Windows GBK 控制台输出中文会乱码，强制 UTF-8
if sys.stdout.encoding and sys.stdout.encoding.upper() != "UTF-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import pypdfium2 as pdfium


def parse_pages(spec, total):
    """'1-3,5' -> [0,1,2,4]（转为 0 基索引）。"""
    pages = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            pages.update(range(int(a), int(b) + 1))
        elif part:
            pages.add(int(part))
    return sorted(p - 1 for p in pages if 1 <= p <= total)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("pdf")
    p.add_argument("outdir")
    p.add_argument("--pages", default=None, help="页码，如 1-3,5；缺省全部")
    p.add_argument("--scale", type=float, default=2.0)
    args = p.parse_args()

    pdf = pdfium.PdfDocument(args.pdf)
    total = len(pdf)
    idxs = parse_pages(args.pages, total) if args.pages else list(range(total))
    os.makedirs(args.outdir, exist_ok=True)

    stem = os.path.splitext(os.path.basename(args.pdf))[0]
    out = []
    for i in idxs:
        img = pdf[i].render(scale=args.scale).to_pil()
        path = os.path.join(args.outdir, f"{stem}_p{i+1}.png")
        img.save(path)
        out.append(path)
    print(json.dumps({"total": total, "rendered": out}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
