"""把 cwd 下的 PDF 按页渲染成 PNG，存到 pages/<pdf序号>/p<页码>.png。
参考实现，按材料改：见同目录 README.md。
"""

import glob
import os

import pypdfium2 as pdfium

SCALE = 2  # 约 1082x1508，清晰度够 AI 视觉阅读

for pdf_path in sorted(glob.glob("*.pdf")):
    tag = pdf_path[:2]  # 01..06
    out_dir = os.path.join("pages", tag)
    os.makedirs(out_dir, exist_ok=True)
    with pdfium.PdfDocument(pdf_path) as pdf:
        n = len(pdf)
        done = 0
        for i in range(n):
            out = os.path.join(out_dir, f"p{i + 1:03d}.png")
            if os.path.exists(out):
                continue
            img = pdf[i].render(scale=SCALE).to_pil()
            img.save(out)
            done += 1
    print(f"{pdf_path}: {n} pages, rendered {done}", flush=True)
