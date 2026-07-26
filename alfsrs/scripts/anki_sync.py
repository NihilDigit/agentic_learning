"""anki_cards/*.md -> Anki 增量同步（经 AnkiConnect, localhost:8765）。

卡片md格式:
    <!-- id: k2.2.01 | tags: 顺序表 概念 -->
    Q: 问题（可多行）
    A: 答案（可多行）

同步语义: md 是事实来源。按 CardID 匹配 Anki note，存在则更新，不存在则新建。
md 里删掉的卡不会自动从 Anki 删除（防误删），只报告孤立数量。

用法: anki_sync.py [--course DIR]
"""

import argparse
import glob
import json
import os
import re
import sys
import urllib.request

CONNECT = "http://localhost:8765"
MODEL = "agenticLearning"
CARD_START = re.compile(r"<!--\s*id:")
CARD_BLOCK = re.compile(
    r"<!--\s*id:\s*(\S+?)\s*(?:\|\s*tags:\s*(.*?))?\s*-->\s*\n"
    r"Q:\s*(.*?)\nA:\s*(.*)",
    re.DOTALL,
)


class CardParseError(ValueError):
    """anki_cards 源文件不符合可安全同步的格式。"""


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


def rpc(action, **params):
    body = json.dumps({"action": action, "version": 6, "params": params}).encode()
    req = urllib.request.Request(
        CONNECT, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        resp = json.load(r)
    if resp.get("error"):
        raise RuntimeError(f"{action}: {resp['error']}")
    return resp["result"]


def parse_cards(course):
    """解析 anki_cards/*.md -> [{id, q, a, tags, src}]"""
    cards = []
    seen = {}
    for path in sorted(glob.glob(os.path.join(course, "anki_cards", "*.md"))):
        with open(path, encoding="utf-8") as f:
            text = f.read()
        blocks = re.split(r"(?=<!--\s*id:)", text)
        for block_number, block in enumerate(blocks, start=1):
            if not CARD_START.match(block):
                continue
            m = CARD_BLOCK.fullmatch(block.strip())
            if not m:
                raise CardParseError(
                    f"{path}: 第 {block_number} 个卡片块格式错误，必须包含 id、Q 和 A"
                )
            cid, tags, q, a = m.groups()
            cid, q, a = cid.strip(), q.strip(), a.strip()
            if not q or not a:
                raise CardParseError(f"{path}: 卡片 {cid} 的 Q/A 不能为空")
            if cid in seen:
                raise CardParseError(f"CardID {cid} 重复：{seen[cid]} 与 {path}")
            seen[cid] = path
            cards.append(
                {
                    "id": cid,
                    "tags": tags.split() if tags else [],
                    "q": q.replace("\n", "<br>"),
                    "a": a.replace("\n", "<br>"),
                    "src": os.path.basename(path),
                }
            )
    return cards


def ensure_model():
    if MODEL not in rpc("modelNames"):
        rpc(
            "createModel",
            modelName=MODEL,
            inOrderFields=["CardID", "Q", "A"],
            cardTemplates=[{"Name": "卡片1", "Front": "{{Q}}", "Back": "{{A}}"}],
        )


def anki_query_value(value):
    """转义 Anki 搜索语法双引号中的值。"""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def sync_cards(deck, cards):
    """把已校验的卡片同步到 Anki，返回可序列化的结果。"""
    rpc("version")
    ensure_model()
    rpc("createDeck", deck=deck)

    # 先一次性取回本牌组下本模型的全部 note，避免逐卡往返查询。
    # note:MODEL 限定模型：牌组里可能混有用户自己的卡，它们没有 CardID 字段。
    existing = {}
    escaped_deck = anki_query_value(deck)
    note_ids = rpc("findNotes", query=f'deck:"{escaped_deck}" note:{MODEL}')
    if note_ids:
        for n in rpc("notesInfo", notes=note_ids):
            cid = n["fields"].get("CardID", {}).get("value")
            if cid:
                if cid in existing:
                    raise RuntimeError(f"Anki 中存在重复 CardID {cid}，请先人工合并")
                existing[cid] = n

    added, updated, unchanged = [], [], []
    for c in cards:
        note = existing.get(c["id"])
        if note:
            nid = note["noteId"]
            cur = note["fields"]
            if cur["Q"]["value"] != c["q"] or cur["A"]["value"] != c["a"]:
                rpc(
                    "updateNoteFields",
                    note={"id": nid, "fields": {"Q": c["q"], "A": c["a"]}},
                )
                updated.append(c["id"])
            else:
                unchanged.append(c["id"])
            new_tags = [t for t in c["tags"] if t not in note["tags"]]
            if new_tags:
                rpc("addTags", notes=[nid], tags=" ".join(new_tags))
            removed_tags = [t for t in note["tags"] if t not in c["tags"]]
            if removed_tags:
                rpc("removeTags", notes=[nid], tags=" ".join(removed_tags))
        else:
            nid = rpc(
                "addNote",
                note={
                    "deckName": deck,
                    "modelName": MODEL,
                    "fields": {"CardID": c["id"], "Q": c["q"], "A": c["a"]},
                    "tags": c["tags"],
                },
            )
            existing[c["id"]] = {"noteId": nid, "fields": {}, "tags": list(c["tags"])}
            added.append(c["id"])

    # 孤立 note（Anki 里有但 md 里没了），只报告不删除
    orphans = sorted(set(existing) - {c["id"] for c in cards})

    return {
        "ok": True,
        "deck": deck,
        "added": added,
        "updated": updated,
        "unchanged": len(unchanged),
        "orphans": orphans,
    }


def resolve_deck(course):
    """按 courses.json 的标准结构解析牌组名。"""
    course = os.fspath(course)
    course_id = os.path.basename(course.rstrip("/\\"))
    deck = course_id
    courses_file = os.path.join(os.path.dirname(course.rstrip("/\\")), "courses.json")
    if not os.path.exists(courses_file):
        return deck
    with open(courses_file, encoding="utf-8") as f:
        info = json.load(f)
    courses = info.get("courses", {})
    if not isinstance(courses, dict):
        raise TypeError("courses.json 的 courses 必须是对象")
    entry = courses.get(course_id)
    if entry is None:
        return deck
    if not isinstance(entry, dict):
        raise TypeError(f"courses.json 中 {course_id!r} 的课程信息必须是对象")
    title = entry.get("title")
    if title is not None and (not isinstance(title, str) or not title.strip()):
        raise ValueError(f"courses.json 中 {course_id!r} 的 title 必须是非空字符串")
    return title or deck


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--course", default=None)
    args = p.parse_args()
    try:
        course = args.course or default_course()
        deck = resolve_deck(course)
        cards = parse_cards(course)
        if not cards:
            result = {"ok": True, "cards": 0, "msg": "anki_cards/ 下没有卡片"}
        else:
            result = sync_cards(deck, cards)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (
        CardParseError,
        json.JSONDecodeError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        print(
            json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
