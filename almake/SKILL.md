---
name: almake
description: agenticLearning 材料化命令，把扫描 PDF、文字 PDF、Markdown 讲义等原始学习材料加工成 modules 素材与 index.json 标准课程结构。仅在用户明确要求把新材料制成 agenticLearning 课程或调用 almake 时使用。
compatibility: Requires Python, uv/uvx, and the al skill installed as a sibling directory; PDF workflows may require pypdf, pypdfium2, and Pillow.
metadata:
  type: flow
---

# /almake — 材料 agenticLearning 化

本 skill 规定产物的格式契约与验收标准。每份材料的情况不同，怎么找目录、页码如何对齐、在哪里切分、用 PDF 还是 md，由你读过材料之后判断。

先读 `<AL>/reference/PROTOCOL.md`（`<AL>` 的解析规则见该文件开头），index.json 的完整 schema 在那里。

## 一、产物契约

新课程目录 `.al/<course>/`：

```
<course>/
├── index.json      # 【必须】模块清单，由你按 PROTOCOL 的 schema 编写
├── modules/        # 【必须】每模块一个素材文件
└── toc.json        # 【可选】材料目录结构；PDF 类材料建议留下，记录页码映射便于回查
```

两条硬性要求，其余全部自由：

1. **组织方式**：一个模块 = 一个可独立学习的小节，模块文件内含**知识点、题目、答案**三部分（无题的节除外，此时 `has_exercises: false`）。题目与答案必须和知识点在同一个文件里：批改时 Agent 只打开这一个文件。
2. **模块号即题目 ID 前缀**：`index.json` 里的 `id` 决定了此后所有错题 ID 形如 `<模块号>.<题号>`，一旦定下不要再改，否则 `cards.json` 里的历史记录会对不上。

文件格式**不受约束**：`.pdf`、`.md`、同一课程里混用都合法，只要 `file` 字段指对。选"保真前提下 Agent 可读、制作最省事"的那个。

## 二、按材料类型选路线

| 材料 | 建议做法 | 理由 |
|---|---|---|
| 扫描版书（无文字层） | 按页切片成模块 PDF | 保真优先，OCR/转录会引入错误答案，代价比排版丑陋大得多 |
| 文字版 PDF | 抽文字转 md，公式图表多则仍切 PDF | md 体积小、Agent 读取快 |
| 网络教程 / 讲义 / 已有 md | 直接整理成 md 模块 | 本来就是文本 |
| 有题无答案的材料 | 先补答案再入库，或标 `has_exercises: false` | 无答案无法批改，FSRS 链条断在这里 |

扫描书这条路线最麻烦，通常绕不开：渲染页面图 → 视觉读目录页得到章节与书页码 → 建立"书页码 → 源 PDF 页"的偏移映射（一本书可能被拆成多个 PDF，偏移逐段不同，章扉页常落在前一个 PDF 末尾）→ 按边界切片。切片时**边界页共享**（相邻两片都包含交界页），宁可重复一页也不能漏内容。

`examples/` 存了一套跑通过的实现（一本 400+ 页扫描辅导书，六个源 PDF 切出 32 个模块），适合拿来改写。其中的页码映射与章节标题关键词都是那本书专有的。

## 三、验收

1. **抽查内容边界**：随机挑几个模块打开看首尾。切片查起止页（首页是否为该节标题，末页有没有截断答案），md 查小节是否完整、答案是否配齐。这一步不能省，边界错了后面每次讲解都错。
2. **写 index.json**：按 PROTOCOL 的 schema 编写，`status` 全部 `pending`，`next_module` 指向第一个模块。
3. **校验**：

```bash
uvx --with fsrs python <AL>/scripts/fsrs_cli.py check --fix --course .al/<course>
```

`check` 校验字段、status 取值、`file` 指向的素材是否存在、`next_module` 是否有效；`--fix` 补齐可省略的字段。退出码非 0 表示课程尚未就绪，照报错改到 `ok: true` 为止。

4. **登记课程**：按 PROTOCOL 的固定 schema 把新课程写进 `.al/courses.json`（`courses` 对象里以课程目录名为键增加 `{"title": "展示名"}`，需要时把 `active` 指过去）。

完成后向用户汇报：课程名、模块数、格式选型与理由、抽查了哪几个模块及结果、`check` 是否通过。
