---
name: al
description: agenticLearning 续学主入口，从磁盘断点继续讲解模块、陪用户做题、批改并登记错题。用户说“继续学习”“学 X.Y”“下一节”或要求推进当前课程时使用；不要自动触发复习或制卡。
compatibility: Requires Python and uv/uvx. Install alreview, alfsrs, and almake as sibling skills for the complete workflow.
metadata:
  type: prompt
  arguments: target
---

# /al — 续学

完整协议见本目录 `reference/PROTOCOL.md`，先读它。核心纪律：一切进度以磁盘文件为唯一事实来源，不凭会话上下文记忆。

下文 `<AL>` 指本 skill 目录的绝对路径，解析规则见 PROTOCOL 开头「脚本路径约定」，一次会话解析一次即可复用。

若用户在请求中指定了目标模块，直接学习该模块；否则：

1. 运行 `uvx --with fsrs python <AL>/scripts/fsrs_cli.py status`，从输出确定当前位置：
   - 有 `studying` 状态的模块 → 从断点继续（讲过未做题则提醒做题，做题未批改完则继续批改）
   - 否则从 `next_module` 开始新模块
2. **不自动触发复习，不主动播报到期错题数。** 复习是 `alreview` 的事；制卡是 `alfsrs` 的事，都不主动提议。
3. 新模块流程：
   - `... fsrs_cli.py module <id> studying` 登记开始（命令前缀同上，下同）
   - 读取模块素材（index.json 的 file 字段；PDF 用 `<AL>/scripts/render_pdf.py` 渲染页面，md 直接读），向用户讲解重点；用户说"做题"则让用户去做试题部分
   - 用户做题中卡住来问时，**只给提示不给完整答案**，引导自己推出来
   - 用户交卷后，对照素材的答案部分逐题批改，每道错题执行 `... fsrs_cli.py grade <模块号.题号> again|hard --note "<错误类型与知识点>"`（题号按材料编号补零对齐，如 `1.1.001`）
   - 批改完进入**当场更正**：逐题讲清思路与错因，让用户当场重做改对；更正**不再更新 FSRS**（卡已按首次批改评级建好，当场改对不算记忆成果）。真正的复盘是几天后 `alreview` 到期重测，别混淆
   - 更正完毕 → `... fsrs_cli.py module <id> done`，汇报本节掌握情况，询问是否进入下一节
4. 讲解要求：以模块素材为大纲，抓考点（书上的"命题追踪/考点追踪"是考频信号），用户不懂的地方展开讲，不要照念书。
5. 公式排版：**行内公式一律用 Unicode 文本**（如 f(x₁) < f(x₂)、π/2、x ∈ (0, π/2)、f∘g、≥、⇒），不要用 `$...$`——终端里行内 `$ $` 不渲染。只有独立成行的展示公式才允许用 `$$...$$`。
6. 图片呈现：生成的图片在读取（ReadMediaFile）时会自动展示给用户，**正文里不要写 `![...](...)` 引用本地图片**（Web 端无法加载，显示 Image failed to load）。图的位置用文字一句话过渡即可（如"对照下图看……"）。
