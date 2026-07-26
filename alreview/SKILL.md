---
name: alreview
description: agenticLearning 今日复习命令，列出 FSRS 到期错题，逐题重新考用户、批改并更新调度。仅在用户显式要求“今日复习”“刷到期错题”或调用 alreview 时使用，不要自动触发。
compatibility: Requires Python, uv/uvx, and the al skill installed as a sibling directory.
metadata:
  type: flow
---

# /alreview — 今日到期错题重做

`<AL>` 指 al skill 目录的绝对路径（本 skill 的同级目录），解析规则见 `<AL>/reference/PROTOCOL.md` 开头「脚本路径约定」。本 skill 依赖 al 内置脚本，需与 al 一同安装。

1. 运行 `uvx --with fsrs python <AL>/scripts/fsrs_cli.py due`，得到到期错题列表（含 qid、模块、上次错误备注）。没有到期题就直说，结束。
2. 逐题处理（一次一题，不要整页甩给用户）：
   - 按 qid 的模块号从 `.al/<course>/index.json` 找到模块素材文件，呈现题目（PDF 渲染对应页，md 直接引用；图题必须连图一起给）
   - 可以提示"上次错因类型"，但不要直接给答案
   - 用户作答后，对照该模块素材的答案部分批改
3. 每题批改后立即记录（命令前缀同上）：做对 → `grade <qid> good|easy`；又错 → `grade <qid> again --note "<本次错误类型>"`。
4. 全部完成后汇报：今日清了几题、还剩几题、哪些题反复错（lapses 高的要提醒用户重视对应知识点，可建议回炉 `/al` 重学该模块）。
