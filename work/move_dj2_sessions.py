from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HERMES_AGENT = Path(r"C:/Users/Administrator/AppData/Local/hermes/hermes-agent")
DB_PATH = Path(r"C:/Users/Administrator/AppData/Local/hermes/state.db")
PLAN_PATH = Path(r"C:/huuhungn/huuhungn-PC/mc_server_pack/dj2-viethoa/work/session-full-move-plan.json")
DEST = r"C:\huuhungn\huuhungn-PC\mc_server_pack\dj2-viethoa"
CURRENT_SESSION = "20260823_231505_f01aae"

sys.path.insert(0, str(HERMES_AGENT))
from hermes_state import SessionDB  # noqa: E402


def norm(path: str | None) -> str:
    return (path or "").replace("/", "\\").rstrip("\\").lower()


def main() -> int:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    ids = list(dict.fromkeys(plan["ids_to_move"]))
    if not ids:
        print(json.dumps({"moved": 0, "already": 0, "failed": []}))
        return 0

    db = SessionDB(DB_PATH)
    moved = 0
    already = 0
    missing: list[str] = []
    failed: list[dict[str, str]] = []
    before = Counter()
    try:
        for index, session_id in enumerate(ids, 1):
            row = db.get_session(session_id)
            if not row:
                missing.append(session_id)
                continue
            old_cwd = row.get("cwd")
            before[old_cwd or "<NULL>"] += 1
            if norm(old_cwd) == norm(DEST):
                already += 1
                continue
            try:
                # Same durable SessionDB API used by session.workspace.move.
                # Destination is not a Git repo, so branch/root are intentionally cleared.
                db.update_session_cwd(
                    session_id,
                    DEST,
                    None,
                    None,
                    replace_git_meta=True,
                )
                moved += 1
            except Exception as exc:  # keep the batch auditable
                failed.append({"id": session_id, "error": str(exc)})
            if index % 100 == 0:
                print(f"progress={index}/{len(ids)} moved={moved} failed={len(failed)}", flush=True)
    finally:
        db.close()

    verify = SessionDB(DB_PATH, read_only=True)
    wrong: list[dict[str, str | None]] = []
    try:
        for session_id in ids:
            row = verify.get_session(session_id)
            if row and norm(row.get("cwd")) != norm(DEST):
                wrong.append({"id": session_id, "cwd": row.get("cwd")})
        current = verify.get_session(CURRENT_SESSION)
    finally:
        verify.close()

    result = {
        "planned": len(ids),
        "moved": moved,
        "already": already,
        "missing": missing,
        "failed": failed,
        "wrong_after_verify": wrong,
        "current_session_cwd": current.get("cwd") if current else None,
        "origins": dict(before),
        "destination": DEST,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if missing or failed or wrong else 0


if __name__ == "__main__":
    raise SystemExit(main())
