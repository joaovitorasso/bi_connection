import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from ..core.config import settings

logger = logging.getLogger("audit")


def _get_audit_logger():
    audit_logger = logging.getLogger("audit_trail")
    if not audit_logger.handlers:
        handler = logging.FileHandler(settings.AUDIT_LOG_PATH, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(message)s"))
        audit_logger.addHandler(handler)
        audit_logger.setLevel(logging.INFO)
    return audit_logger


def log_change(username: str, action: str, object_type: str, object_id: str, field: str, old_value: Any, new_value: Any, extra: Dict = None):
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "username": username,
        "action": action,
        "objectType": object_type,
        "objectId": object_id,
        "field": field,
        "oldValue": str(old_value) if old_value is not None else None,
        "newValue": str(new_value) if new_value is not None else None,
    }
    if extra:
        entry.update(extra)

    _get_audit_logger().info(json.dumps(entry, ensure_ascii=False))


def get_audit_log(limit: int = 100) -> list:
    try:
        path = Path(settings.AUDIT_LOG_PATH)
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        entries = []
        for line in reversed(lines[-limit:]):
            try:
                entries.append(json.loads(line))
            except Exception:
                pass
        return entries
    except Exception:
        return []
