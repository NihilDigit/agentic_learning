# agenticLearning 协议

agenticLearning 是一个强 HITL 的 Agent 学习系统：AI 讲解 → 用户做题 → AI 批改 → 错题 FSRS 重做 + 记忆卡入 Anki。
**一切进度状态以磁盘文件为唯一事实来源，Agent 不得凭会话上下文记忆进度。** 任何操作前先读状态文件。

## 脚本路径约定

各 SKILL.md 里的 `<AL>` 指 **al skill 目录的绝对路径**（本文件的上级目录）。按顺序解析，一次会话内解析一次即可复用：

1. Agent 提供了 skill 目录变量就直接用（Kimi Code 是 `${KIMI_SKILL_DIR}`，其他 Agent 各不相同）；
2. 否则由当前 SKILL.md 文件所在目录推断（`alreview`/`almake`/`alfsrs` 与 `al` 同级，即 `<本 skill 目录>/../al`）；
3. 都拿不到就定位一次：`fd -g fsrs_cli.py ~/.agents/skills ~/.claude/skills`（无 fd 用 `find ~ -name fsrs_cli.py -path '*al/scripts*'`）。

## 项目侧目录结构（每门课一份）

```
.al/
├── courses.json           # 课程清单与当前活跃课程（active 字段）
└── <course>/
    ├── index.json         # 【必须】进度大脑：模块清单 + status/next_module/错题清单
    ├── modules/           # 【必须】素材：每模块一个文件，含知识点→题目→答案三段
    ├── toc.json           # 【可选】材料目录结构，almake 的中间产物；PDF 类材料建议保留页码映射
    ├── cards.json         # 错题 FSRS 卡状态（首次 grade 时自动创建）
    ├── reviews.jsonl      # 批改日志（append-only）
    └── anki_cards/        # 记忆卡 md 源文件（Anki 内容的事实来源）
```

`courses.json` 的固定结构如下；键是课程目录名，`title` 是展示名和默认 Anki 牌组名：

```json
{
  "active": "data-structures",
  "courses": {
    "data-structures": {
      "title": "数据结构"
    }
  }
}
```

`active` 为 `null` 或省略时，若 `.al/` 下只有一个课程目录，脚本会自动选择它。

## index.json schema

index.json 由 Agent 编写，写完用 `check` 校验。模块怎么切分、切成什么格式，取决于对具体材料的判断。

```json
{
  "course": "<课程目录名>",
  "next_module": "1.1",
  "modules": [
    {
      "id": "1.1",
      "title": "线性表的定义和基本操作",
      "file": "modules/1.1_线性表的定义和基本操作.pdf",
      "status": "pending",
      "has_exercises": true,
      "chapter": "1",
      "taught_at": null, "done_at": null, "graded_at": null,
      "wrong": []
    }
  ]
}
```

| 字段 | 约束 |
|---|---|
| `id` | 模块号，全局唯一，题目 ID 以它为前缀（`<模块号>.<题号>`，如 `2.2.04`） |
| `file` | 相对课程目录的素材路径，**扩展名随材料自由**（`.pdf` / `.md` / 同课程内混用都可以） |
| `status` | `pending` / `studying` / `done` |
| `has_exercises` | 该模块有无题目；无题模块不进入批改与 FSRS |
| `next_module` | 下一个要学的模块 id，全部完成时为 `null` |
| `chapter` | 可选，仅用于汇报时分组 |
| `taught_at`/`done_at`/`graded_at`/`wrong` | 由脚本维护，Agent 初始写 `null` / `[]`，或省略后用 `check --fix` 补齐 |

模块的唯一硬性组织要求：**一个模块 = 一个可独立学习的小节，含知识点、题目、答案三部分**（无题的节除外）。

## 脚本（bundle 在 al skill 内）

`<AL>/scripts/fsrs_cli.py` 是进度与错题 FSRS 调度的唯一入口。运行：`uvx --with fsrs python <AL>/scripts/fsrs_cli.py <子命令>`。

| 子命令 | 作用 |
|---|---|
| `check [--fix]` | 校验 index.json 与 cards.json：必填字段、类型、status、素材路径、题目/模块归属、`next_module` 进度不变量。`--fix` 补齐缺失的可选字段并写回。退出码非 0 表示有错误 |
| `status` | 输出课程进度 JSON（各模块状态、错题数、卡数） |
| `due` | 输出今日到期错题 JSON |
| `grade <qid> <rating> [--note] [--allow-new]` | 记录批改，更新 FSRS 调度与模块错题清单；首次 `good/easy` 默认拒绝，只有用户明确要求跟踪时才加 `--allow-new` |
| `module <id> <pending\|studying\|done>` | 设置模块状态 |

所有子命令接受 `--course DIR`（**必须写在子命令之后**）；缺省解析 `.al/courses.json` 的 active 课程，或 `.al/` 下唯一的课程目录。

制卡同步脚本 `anki_sync.py` bundle 在 `alfsrs` skill 内。

## 批改评级映射（grade 的四个档位）

- `again`：不会、思路错、概念错 —— 根因是理解或记忆缺失
- `hard`：方向对但关键步骤出错、粗心造成实质错误
- `good`：复习重做时做对
- `easy`：复习重做时秒对且过程完整

只对错题（again/hard）建卡进入 FSRS；做对的题不建卡。若用户明确要求跟踪一开始就做对的题，使用 `--allow-new`。

## 行为纪律

1. 续学（al）：先跑 `status` 读 index.json，从 `next_module` / studying 断点继续。**不自动触发复习，不主动播报到期数**。
2. 复习只在 alreview 时进行；制卡只在 alfsrs 时进行；讲解/批改中不主动提议制卡。
3. 讲解与批改都基于模块素材（index.json 的 `file` 字段）：PDF 用 pypdfium2 渲染页面，md 直接读。试题与答案在同一模块文件内。
4. 题目 ID = `模块号.题号`（如 `2.2.04`）。
5. 模块状态流转：开始讲 → `module <id> studying`；该节习题全部批改完成 → `module <id> done`。
6. 不要手改 `cards.json` / `reviews.jsonl`，FSRS 状态只经 `grade` 更新。
