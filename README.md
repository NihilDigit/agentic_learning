# agenticLearning

一个强 HITL 的 Agent 学习系统 Skill 包：AI 讲解 → 用户做题 → AI 批改 → 错题进 FSRS 自动排期重做，记忆点制成 Anki 卡。面向任何可按"模块 = 知识点 + 题目 + 答案"组织的学习材料（教材、讲义、教程、规范文档），学科与材料格式无关。

符合 [Agent Skills](https://agentskills.io) 标准：每个 Skill 目录自包含（SKILL.md + 内置脚本 + 参考文档），可被支持 Skills 的 Agent CLI（Kimi Code、Claude Code 等）直接加载。

## 四个 Skill

| Skill | 类型 | 作用 |
|---|---|---|
| `al` | prompt | 续学主入口：读 index.json 从断点继续。不自动复习、不播报到期数 |
| `alreview` | flow（仅手动） | 今日到期错题逐题重考、批改、更新调度 |
| `alfsrs` | flow（仅手动） | 从当前会话上下文提取记忆点制卡（能推导的不制卡），同步 Anki |
| `almake` | flow（仅手动） | 材料 agenticLearning 化：原始材料（扫描PDF/文字PDF/md）→ 标准课程结构 |

`alreview` / `almake` 复用 `al` 内置的 `fsrs_cli.py`（通过同级目录引用），四个需一起安装。

## 安装

把四个目录拷进 Agent 的 Skills 扫描路径即可，例如 Kimi Code 用户级（全项目生效）：

```bash
cp -r al alreview alfsrs almake ~/.agents/skills/
```

之后 `/al`、`/alreview`、`/alfsrs`、`/almake` 即可用（Kimi Code 需新开会话加载）。

## 运行依赖

无虚拟环境：脚本经 [uv](https://docs.astral.sh/uv/) 的 `uvx --with <依赖> python` 运行（fsrs_cli 需 `fsrs`；材料化脚本需 `pypdf pypdfium2 pillow`；anki_sync 纯标准库）。Anki 同步需桌面 Anki 安装 AnkiConnect 插件（代码 2055492159）。

## 工作目录结构（每门课一份状态）

课程与进度落在工作目录的 `.al/` 下，脚本留在 Skill 目录，项目根目录不多出可见文件。

```
.al/
├── courses.json        # 课程清单 + active 指针
└── <course>/
    ├── index.json      # 进度大脑：模块 status/next/错题清单
    ├── modules/        # 素材：每节一个文件（知识点→题目→答案）
    ├── toc.json        # 材料目录，可选；PDF 类材料用来记页码映射
    ├── cards.json      # 错题 FSRS 状态
    ├── reviews.jsonl   # 批改日志
    └── anki_cards/     # 记忆卡 md（Anki 内容的事实来源）
```

`courses.json` 使用固定映射结构：

```json
{
  "active": "data-structures",
  "courses": {
    "data-structures": {"title": "数据结构"}
  }
}
```

核心纪律：**一切进度以磁盘文件为唯一事实来源，Agent 不凭会话上下文记忆进度**（防 compact）。FSRS 计算全部在 `al/scripts/fsrs_cli.py`（基于 py-fsrs），Agent 只做判断与记录。完整协议与 index.json 的 schema 见 `al/reference/PROTOCOL.md`。

## 材料加工

`index.json` 由 Agent 编写，写完跑 `fsrs_cli.py check` 校验字段、素材路径与模块引用。模块怎么切、用什么格式，取决于材料本身：扫描书按页切片 PDF 保真，文字版 PDF 与网络讲义转 md 更省事，同一课程里混用也可以。`almake/SKILL.md` 给的是格式契约与验收标准；`almake/examples/` 存了一个跑通过的实现（400+ 页扫描辅导书 → 32 个模块 PDF，pypdfium2 渲染 + pypdf 切片，边界页共享防漏内容）。

## 开发检查

```bash
uv run --with fsrs --with pypdf python -m unittest discover -s tests -v
uvx ruff check .
uvx --from skills-ref agentskills validate al
```

最后一条对其余三个 Skill 目录同样运行。
