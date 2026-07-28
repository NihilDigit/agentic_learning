---
name: alreview
description: agenticLearning 今日复习命令，列出 FSRS 到期错题，逐题重新考用户、批改并更新调度。仅在用户显式要求“今日复习”“刷到期错题”或调用 alreview 时使用，不要自动触发。
compatibility: Requires Python, uv/uvx, and the al skill installed as a sibling directory.
metadata:
  type: flow
---

# /alreview — 今日到期错题重做（复盘）

`<AL>` 指 al skill 目录的绝对路径（本 skill 的同级目录），解析规则见 `<AL>/reference/PROTOCOL.md` 开头「脚本路径约定」。本 skill 依赖 al 内置脚本，需与 al 一同安装。

这里进行的才是真正的「复盘」：错题到期后用户**独立重写**。注意与 /al 批改后的「更正」区分——更正是刚批改完趁热讲思路、用户当场改错，不更新 FSRS；复盘是本 skill 的到期重测，结果驱动 FSRS 调度与删卡。

1. 运行 `uvx --with fsrs python <AL>/scripts/fsrs_cli.py due`，得到到期错题列表（含 qid、模块、上次错误备注、`wrong_count` 历史错误次数）。没有到期题就直说，结束。
2. 逐题处理（一次一题，不要整页甩给用户）：
   - 按 qid 的模块号从 `.al/<course>/index.json` 找到模块素材文件，呈现题目（PDF 用 `<AL>/scripts/render_pdf.py` 渲染对应页，md 直接引用；图题必须连图一起给）
   - 可以提示"上次错因类型"，但不要直接给答案
   - 用户作答后，对照该模块素材的答案部分批改
3. 每题批改后立即记录（命令前缀同上）：
   - **做对** → 看 `wrong_count`：
     - `< 2`（只错过一次）→ 询问用户是否 `ungrade <qid>` 直接删卡（用户的默认偏好：复盘效果好就删）；用户想继续跟踪才 `grade <qid> good|easy`
     - `≥ 2`（错过两次及以上）→ **不删卡**，只能 `grade <qid> good|easy` 降级调度，让它以后再来
   - **又错** → `grade <qid> again --note "<本次错误类型>"`，卡留下继续调度
4. 全部完成后汇报：今日清了几题、删了几张卡、还剩几题、哪些题反复错（wrong_count / lapses 高的要提醒用户重视对应知识点，可建议回炉 `/al` 重学该模块）。
