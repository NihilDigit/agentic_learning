"""agenticLearning 错题FSRS调度 + 课程进度 CLI。
所有状态落盘于课程目录，Agent 通过本脚本读写，不凭上下文记忆。

index.json 由 Agent 按 PROTOCOL.md 的 schema 编写，本脚本负责校验它以及此后的状态读写。

用法:
  fsrs_cli.py check   [--course DIR] [--fix]        校验 index.json 是否符合 schema
  fsrs_cli.py status  [--course DIR]                输出课程进度 JSON
  fsrs_cli.py due     [--course DIR]                输出今日到期错题 JSON
  fsrs_cli.py grade QID RATING [--note 备注]        批改记录: RATING ∈ again|hard|good|easy
  fsrs_cli.py module MID STATUS                     设置模块状态: pending|studying|done

--course 缺省时解析 .al/courses.json 的 active 课程。
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from fsrs import Card, Rating, Scheduler


def default_course():
    """从 cwd 解析默认课程：.al/courses.json 的 active，或 .al/ 下唯一的课程目录。"""
    base = os.path.join(os.getcwd(), ".al")
    courses_file = os.path.join(base, "courses.json")
    if os.path.exists(courses_file):
        with open(courses_file, encoding="utf-8") as f:
            info = json.load(f)
        if info.get("active"):
            return os.path.join(base, info["active"])
    if os.path.isdir(base):
        subs = [d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))]
        if len(subs) == 1:
            return os.path.join(base, subs[0])
    return base


RATINGS = {
    "again": Rating.Again,
    "hard": Rating.Hard,
    "good": Rating.Good,
    "easy": Rating.Easy,
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, obj):
    """在同一目录原子替换 JSON，避免进程中断留下半个文件。"""
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


STATUSES = ("pending", "studying", "done")
# 模块必填字段；其余字段（状态时间戳、wrong、has_exercises）缺省时由 check --fix 补齐
MODULE_REQUIRED = ("id", "title", "file", "status")
MODULE_OPTIONAL = {
    "has_exercises": True,
    "taught_at": None,
    "done_at": None,
    "graded_at": None,
    "wrong": [],
}


def qid_module(qid):
    """返回合法题目 ID 的模块前缀；格式不合法时返回 None。"""
    if not isinstance(qid, str) or "." not in qid:
        return None
    module, question = qid.rsplit(".", 1)
    return module if module and question else None


def cmd_check(course, fix):
    """校验 Agent 手写的 index.json：字段、取值、file 指向、qid 归属。"""
    idx = load_json(os.path.join(course, "index.json"), None)
    if idx is None:
        print(
            json.dumps(
                {"ok": False, "errors": [f"{course}/index.json 不存在"]},
                ensure_ascii=False,
            )
        )
        sys.exit(1)
    if not isinstance(idx, dict):
        print(
            json.dumps(
                {"ok": False, "errors": ["index.json 顶层必须是对象"]},
                ensure_ascii=False,
                indent=2,
            )
        )
        sys.exit(1)

    errors, warnings, fixed = [], [], []
    if not isinstance(idx.get("modules"), list) or not idx["modules"]:
        errors.append("modules 必须是非空数组")
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        sys.exit(1)

    seen = set()
    for i, m in enumerate(idx["modules"]):
        if not isinstance(m, dict):
            errors.append(f"modules[{i}]: 必须是对象")
            continue
        where = f"modules[{i}]" + (
            f" ({m['id']})" if isinstance(m.get("id"), str) else ""
        )
        for k in MODULE_REQUIRED:
            if not m.get(k):
                errors.append(f"{where}: 缺少必填字段 {k}")
        mid = m.get("id")
        if isinstance(mid, str):
            if mid in seen:
                errors.append(f"{where}: 模块 id 重复")
            seen.add(mid)
        if m.get("status") not in STATUSES:
            errors.append(f"{where}: status={m.get('status')!r} 不在 {STATUSES}")
        file = m.get("file")
        if file and not isinstance(file, str):
            errors.append(f"{where}: file 必须是字符串")
        elif file and not os.path.exists(os.path.join(course, file)):
            errors.append(f"{where}: file 指向的素材不存在 -> {file}")
        has_exercises = m.get("has_exercises", True)
        if not isinstance(has_exercises, bool):
            errors.append(f"{where}: has_exercises 必须是布尔值")
        wrong = m.get("wrong", [])
        if not isinstance(wrong, list):
            errors.append(f"{where}: wrong 必须是数组")
            wrong = []
        for qid in wrong:
            if not isinstance(qid, str):
                errors.append(f"{where}: wrong 里的题目 ID 必须是字符串")
            elif qid_module(qid) is None:
                errors.append(f"{where}: wrong 里的 {qid!r} 不是合法题目 ID")
            elif qid_module(qid) != mid:
                errors.append(f"{where}: wrong 里的 {qid} 不属于本模块")
        missing = [k for k in MODULE_OPTIONAL if k not in m]
        if missing:
            if fix:
                for k in missing:
                    v = MODULE_OPTIONAL[k]
                    m[k] = list(v) if isinstance(v, list) else v
                fixed.append(where)
            else:
                warnings.append(
                    f"{where}: 缺少可选字段 {', '.join(missing)}（check --fix 可补齐）"
                )

    nxt = idx.get("next_module")
    if nxt is not None and nxt not in seen:
        errors.append(f"next_module={nxt!r} 不是任何模块的 id")
    valid_modules = [m for m in idx["modules"] if isinstance(m, dict)]
    pending = [
        m.get("id")
        for m in valid_modules
        if m.get("status") != "done" and m.get("id") in seen
    ]
    expected_next = pending[0] if pending else None
    if nxt != expected_next:
        errors.append(
            f"next_module 应为第一个未完成模块 {expected_next!r}，实际为 {nxt!r}"
        )
    if not idx.get("course"):
        if fix:
            idx["course"] = os.path.basename(course.rstrip("/\\"))
            fixed.append("course")
        else:
            warnings.append("缺少 course 字段（check --fix 可补齐）")
    elif not isinstance(idx["course"], str):
        errors.append("course 必须是字符串")

    cards = load_json(os.path.join(course, "cards.json"), {})
    if not isinstance(cards, dict):
        errors.append("cards.json 顶层必须是对象")
    else:
        for key, card in cards.items():
            if not isinstance(card, dict):
                errors.append(f"cards.json[{key!r}] 必须是对象")
                continue
            qid = card.get("qid")
            module = card.get("module")
            if qid != key:
                errors.append(f"cards.json[{key!r}] 的 qid 与键不一致")
            if module not in seen:
                errors.append(f"cards.json[{key!r}] 引用了不存在的模块 {module!r}")
            if qid_module(qid) is None:
                errors.append(f"cards.json[{key!r}] 的 qid 格式不合法")
            elif qid_module(qid) != module:
                errors.append(f"cards.json[{key!r}] 的 qid 与 module 不一致")

    if fix and fixed and not errors:
        save_json(os.path.join(course, "index.json"), idx)

    print(
        json.dumps(
            {
                "ok": not errors,
                "modules": len(idx["modules"]),
                "errors": errors,
                "warnings": warnings,
                "fixed": fixed,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    sys.exit(0 if not errors else 1)


def get_index(course):
    idx = load_json(os.path.join(course, "index.json"), None)
    if idx is None:
        sys.exit("index.json 不存在，先用 almake 创建课程")
    if not isinstance(idx, dict) or not isinstance(idx.get("modules"), list):
        sys.exit("index.json 格式错误，先运行 check")
    return idx


def cmd_status(course):
    idx = get_index(course)
    cards = load_json(os.path.join(course, "cards.json"), {})
    out = {
        "course": idx["course"],
        "next_module": idx["next_module"],
        "modules": [],
    }
    for m in idx["modules"]:
        mcards = [c for c in cards.values() if c.get("module") == m["id"]]
        out["modules"].append(
            {
                "id": m["id"],
                "title": m["title"],
                "status": m["status"],
                "has_exercises": m.get("has_exercises", True),
                "file": m["file"],
                "wrong_total": len(m.get("wrong", [])),
                "cards": len(mcards),
            }
        )
    print(json.dumps(out, ensure_ascii=False, indent=2))


def cmd_due(course):
    cards = load_json(os.path.join(course, "cards.json"), {})
    now = datetime.now(timezone.utc)
    due = []
    for c in cards.values():
        due_dt = datetime.fromisoformat(c["fsrs"]["due"])
        if due_dt.tzinfo is None:
            due_dt = due_dt.replace(tzinfo=timezone.utc)
        if due_dt <= now:
            due.append(
                {
                    "qid": c["qid"],
                    "module": c["module"],
                    "due": c["fsrs"]["due"],
                    "lapses": c["fsrs"].get("lapses", 0),
                    "last_note": c.get("last_note"),
                }
            )
    due.sort(key=lambda x: x["due"])
    print(json.dumps({"count": len(due), "due": due}, ensure_ascii=False, indent=2))


def cmd_grade(course, qid, rating, note, allow_new):
    # 在任何写盘前验证课程、模块和建卡语义，避免无效输入污染唯一事实来源。
    idx = get_index(course)
    module = qid_module(qid)
    if module is None:
        sys.exit(f"题目 ID {qid!r} 格式错误，应为 <模块号>.<题号>")
    target = next(
        (m for m in idx["modules"] if isinstance(m, dict) and m.get("id") == module),
        None,
    )
    if target is None:
        sys.exit(f"题目 {qid} 所属模块 {module!r} 不存在")
    if not target.get("has_exercises", True):
        sys.exit(f"模块 {module} 标记为无题，不能记录题目 {qid}")

    cards_path = os.path.join(course, "cards.json")
    cards = load_json(cards_path, {})
    if not isinstance(cards, dict):
        sys.exit("cards.json 格式错误，先运行 check")
    if qid not in cards and rating in ("good", "easy") and not allow_new:
        sys.exit(
            "good/easy 只能用于已有错题；若用户明确要求跟踪首次做对的题，请加 --allow-new"
        )
    if qid in cards and cards[qid].get("module") != module:
        sys.exit(f"cards.json 中 {qid} 的模块归属不一致，先运行 check")

    scheduler = Scheduler()
    if qid in cards:
        card = Card.from_dict(cards[qid]["fsrs"])
    else:
        card = Card()
    reviewed_at = datetime.now(timezone.utc)
    card, _log = scheduler.review_card(
        card, RATINGS[rating], review_datetime=reviewed_at
    )
    reviewed_at_iso = reviewed_at.isoformat()

    cards[qid] = {
        "qid": qid,
        "module": module,
        "fsrs": card.to_dict(),
        "last_note": note,
        "last_rating": rating,
        "history": cards.get(qid, {}).get("history", [])
        + [{"rating": rating, "at": reviewed_at_iso, "note": note}],
    }

    wrong = target.setdefault("wrong", [])
    if rating in ("again", "hard") and qid not in wrong:
        wrong.append(qid)
    if rating in ("good", "easy") and qid in wrong:
        wrong.remove(qid)
    target["graded_at"] = reviewed_at_iso

    # 单个 JSON 文件均原子替换；所有校验已完成后才开始写入。
    save_json(cards_path, cards)
    save_json(os.path.join(course, "index.json"), idx)
    with open(os.path.join(course, "reviews.jsonl"), "a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {"qid": qid, "rating": rating, "note": note, "at": reviewed_at_iso},
                ensure_ascii=False,
            )
            + "\n"
        )

    print(
        json.dumps(
            {
                "qid": qid,
                "rating": rating,
                "due": cards[qid]["fsrs"]["due"],
                "state": cards[qid]["fsrs"]["state"],
            },
            ensure_ascii=False,
        )
    )


def cmd_module(course, mid, status):
    idx = get_index(course)
    ids = [m["id"] for m in idx["modules"]]
    if mid not in ids:
        sys.exit(f"未知模块 {mid}")
    for m in idx["modules"]:
        if m["id"] == mid:
            m["status"] = status
            if status == "studying" and not m.get("taught_at"):
                m["taught_at"] = now_iso()
            if status == "done":
                m["done_at"] = now_iso()
    # next_module 恒等于模块表里第一个未完成的模块：回炉重学旧模块并做完后，
    # 指针会自动回到原来的进度前沿，不会停在被重学的那一节。
    pend = [m for m in idx["modules"] if m["status"] != "done"]
    idx["next_module"] = pend[0]["id"] if pend else None
    save_json(os.path.join(course, "index.json"), idx)
    print(
        json.dumps(
            {"ok": True, "module": mid, "status": status, "next": idx["next_module"]},
            ensure_ascii=False,
        )
    )


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name):
        # --course 只挂在子命令上：同时挂主 parser 时，子 parser 的默认值会静默覆盖
        # 用户在子命令前给的值（argparse 行为），导致写错课程目录。
        sp = sub.add_parser(name)
        sp.add_argument("--course", default=None)
        return sp

    add("status")
    add("due")
    add("check").add_argument(
        "--fix", action="store_true", help="补齐缺失的可选字段并写回"
    )
    g = add("grade")
    g.add_argument("qid")
    g.add_argument("rating", choices=list(RATINGS))
    g.add_argument("--note", default=None)
    g.add_argument(
        "--allow-new",
        action="store_true",
        help="允许用 good/easy 显式创建一张此前不存在的 FSRS 卡",
    )
    m = add("module")
    m.add_argument("mid")
    m.add_argument("status", choices=list(STATUSES))
    args = p.parse_args()

    course = args.course or default_course()
    if args.cmd == "check":
        cmd_check(course, args.fix)
    elif args.cmd == "status":
        cmd_status(course)
    elif args.cmd == "due":
        cmd_due(course)
    elif args.cmd == "grade":
        cmd_grade(course, args.qid, args.rating, args.note, args.allow_new)
    elif args.cmd == "module":
        cmd_module(course, args.mid, args.status)


if __name__ == "__main__":
    main()
