from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict

DATA_DIR = Path(__file__).parent / "data"
DATA_FILE = DATA_DIR / "workspace.json"


def empty_workspace() -> Dict[str, Any]:
    return {
        "students": [],
        "exams": [],
        "questions": [],
        "paper_templates": [],
        "practice_sets": [],
        "ai_reports": {},
        "settings": {
            "teacher_name": "旦旦老师",
            "subject": "高中物理",
            "school_year": "2026-2027",
        },
    }


def normalize_workspace(data: Dict[str, Any] | None) -> Dict[str, Any]:
    base = empty_workspace()
    if not isinstance(data, dict):
        return base
    for key, default in base.items():
        data.setdefault(key, default.copy() if isinstance(default, dict) else list(default) if isinstance(default, list) else default)
    if not isinstance(data.get("ai_reports"), dict):
        data["ai_reports"] = {}
    return data


def load_workspace() -> Dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        return empty_workspace()
    try:
        return normalize_workspace(json.loads(DATA_FILE.read_text(encoding="utf-8")))
    except Exception:
        return empty_workspace()


def save_workspace(data: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(normalize_workspace(data), ensure_ascii=False, indent=2), encoding="utf-8")


def workspace_bytes(data: Dict[str, Any]) -> bytes:
    return json.dumps(normalize_workspace(data), ensure_ascii=False, indent=2).encode("utf-8")


def restore_workspace(file_bytes: bytes) -> Dict[str, Any]:
    data = json.loads(file_bytes.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("备份文件格式不正确")
    return normalize_workspace(data)
