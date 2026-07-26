# 参考实现：扫描版辅导书 → 模块 PDF

这是一次加工任务留下的脚本存档：材料为一本 400+ 页扫描版考研辅导书，拆成 6 个源 PDF，切出 32 个模块。页码映射、文件命名、章节标题关键词都是那本书专有的，换材料需要改写后再运行。

处理这类材料的通用思路见 `../SKILL.md`，格式契约见 `../../al/reference/PROTOCOL.md`。

## render_pages.py

pypdfium2 把 cwd 下的 `*.pdf` 逐页渲染成 `pages/<pdf序号>/pNNN.png`，供 Agent 视觉读目录页、核对切片边界。`SCALE = 2` 约 1082×1508，够 AI 读清正文。已渲染的页会跳过，可断点续跑。

```bash
uvx --with pypdfium2 --with pillow python render_pages.py
```

改写要点：`tag = pdf_path[:2]` 假设源文件名以两位序号开头；材料只有单个 PDF 时，把输出目录写死即可。

## build_modules.py

按 `toc.json` 把源 PDF 切片合并成 `modules/<模块号>_<标题>.pdf`，每片加"知识点 / 试题精选 / 答案与解析"三个书签。边界页共享（相邻两片都含交界页），宁重复不漏。

```bash
uvx --with pypdf python build_modules.py     # cwd 需含 toc.json 与源 PDF
```

改写要点：

- `PDF_MAP`：`(书页起, 书页止, 源PDF文件名, 偏移)`。偏移需要逐段实测，章扉页常落在前一个 PDF 的末尾，目录页上标注的页码不足为凭。
- `"试题精选"` / `"答案与解析"`：靠小节标题关键词识别题目段与答案段，换材料需相应替换。
- 兜底页码 `392`：该书参考文献页，用于确定最后一个模块的结束位置。

## toc.json（该案例的形状）

也是自由格式，只要 `build_modules.py` 读得懂。此处用的是：

```json
{
  "chapters": [
    {"num": "1", "page": 1, "sections": [
      {"num": "1.1", "title": "...", "page": 3,
       "subsections": [{"num": "1.1.1", "title": "试题精选", "page": 8}]}
    ],
     "end_matter": [{"title": "本章总结", "page": 60}]}
  ],
  "references_page": 392
}
```

注意这里的 `page` 全是**书页码**（印在纸上的那个），转成 PDF 实际页由 `PDF_MAP` 的偏移完成。
