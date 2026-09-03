from __future__ import annotations

import json
import re
import shutil
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

HERMES_AGENT = Path(r"C:/Users/Administrator/AppData/Local/hermes/hermes-agent")
DB_PATH = Path(r"C:/Users/Administrator/AppData/Local/hermes/state.db")
WORK = Path(r"C:/huuhungn/huuhungn-PC/mc_server_pack/dj2-viethoa/work")
DEST = r"C:\huuhungn\huuhungn-PC\mc_server_pack\dj2-viethoa"

sys.path.insert(0, str(HERMES_AGENT))
from hermes_state import SessionDB  # noqa: E402

# These are the translation-worker patterns created for the Divine Journey 2
# localization run. Generic Hermes/OmniRoute/Lark sessions are deliberately excluded.
DJ2_WORKER = re.compile(
    r"(translate|dịch|localization|localisation|việt).{0,90}"
    r"(minecraft|botania|atum|alchemistry|tooltip|quest|lang)|"
    r"(?:minecraft|botania|atum|alchemistry|tooltip|quest|lang).{0,90}"
    r"(translate|dịch|localization|localisation|việt)",
    re.IGNORECASE | re.DOTALL,
)


def norm(path: str | None) -> str:
    return (path or "").replace("/", "\\").rstrip("\\").lower()


def main() -> int:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    sessions = {
        row["id"]: dict(row)
        for row in conn.execute(
            "SELECT id,title,display_name,cwd,source,message_count,parent_session_id "
            "FROM sessions"
        )
    }
    remaining = [row for row in sessions.values() if not (row.get("cwd") or "").strip()]

    selected: dict[str, str] = {}
    for row in remaining:
        title = row.get("title") or row.get("display_name") or ""
        if DJ2_WORKER.search(title):
            selected[row["id"]] = "title"

    for row in remaining:
        if row["id"] in selected:
            continue
        messages = conn.execute(
            "SELECT role,content FROM messages WHERE session_id=? ORDER BY id LIMIT 6",
            (row["id"],),
        ).fetchall()
        text = " ".join(
            str(message["content"] or "")
            for message in messages
            if message["role"] in ("user", "system")
        )
        if DJ2_WORKER.search(text):
            selected[row["id"]] = "message"
    conn.close()

    ids = sorted(selected)
    if not ids:
        print(json.dumps({"selected": 0, "moved": 0}, ensure_ascii=False))
        return 0

    # Point-in-time safety copy before the durable metadata updates. The live
    # state.db itself remains in Hermes' managed location.
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = WORK / f"state.db.before-dj2-second-pass.{stamp}.bak"
    shutil.copy2(DB_PATH, backup)

    db = SessionDB(DB_PATH)
    moved = 0
    failed: list[dict[str, str]] = []
    try:
        for session_id in ids:
            try:
                db.update_session_cwd(
                    session_id,
                    DEST,
                    None,
                    None,
                    replace_git_meta=True,
                )
                moved += 1
            except Exception as exc:
                failed.append({"id": session_id, "error": str(exc)})
    finally:
        db.close()

    verify_conn = sqlite3.connect(str(DB_PATH))
    verify_conn.row_factory = sqlite3.Row
    verification = {
        row["id"]: row["cwd"]
        for row in verify_conn.execute(
            f"SELECT id,cwd FROM sessions WHERE id IN ({','.join('?' for _ in ids)})",
            ids,
        )
    }
    verify_conn.close()
    mismatched = [session_id for session_id in ids if norm(verification.get(session_id)) != norm(DEST)]

    manifest = {
        "destination": DEST,
        "selected": len(ids),
        "moved": moved,
        "failed": failed,
        "mismatched_after_verify": mismatched,
        "reason_counts": dict(Counter(selected.values())),
        "backup": str(backup),
        "ids": ids,
    }
    manifest_path = WORK / "session-second-pass-result.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in manifest.items() if k != "ids"}, ensure_ascii=False))
    return 1 if failed or mismatched else 0


if __name__ == "__main__":
    raise SystemExit(main())
