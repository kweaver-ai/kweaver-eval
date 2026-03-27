"""Cross-run feedback tracking."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from lib.types import Finding, Severity


@dataclass
class FeedbackItem:
    """A tracked issue across runs."""

    id: str
    severity: str  # Stored as string for JSON serialization
    message: str
    test_case: str
    first_seen: str
    times_seen: int = 1
    last_seen: str = ""
    resolved: bool = False


class FeedbackTracker:
    """Tracks recurring issues across evaluation runs."""

    PERSISTENT_THRESHOLD = 3
    HUMAN_ATTENTION_THRESHOLD = 5
    RESOLVE_AFTER_ABSENT = 3

    def __init__(self, path: str = "test-result/feedback.json"):
        self._path = Path(path)
        self._items: dict[str, FeedbackItem] = {}
        self._seen_this_run: set[str] = set()
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            data = json.loads(self._path.read_text(encoding="utf-8"))
            for d in data.get("items", []):
                item = FeedbackItem(**d)
                self._items[item.id] = item

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {"items": [asdict(i) for i in self._items.values()]}
        self._path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def record_finding(self, test_case: str, finding: Finding) -> None:
        """Record a finding from the current run."""
        item_id = self._make_id(test_case, finding.message)
        now = datetime.now(timezone.utc).isoformat()
        self._seen_this_run.add(item_id)

        if item_id in self._items:
            item = self._items[item_id]
            item.times_seen += 1
            item.last_seen = now
            item.resolved = False
            if Severity(finding.severity.value) < Severity(item.severity):
                item.severity = finding.severity.value
        else:
            self._items[item_id] = FeedbackItem(
                id=item_id,
                severity=finding.severity.value,
                message=finding.message,
                test_case=test_case,
                first_seen=now,
                last_seen=now,
            )

    def get_persistent_items(self) -> list[FeedbackItem]:
        """Items seen >= PERSISTENT_THRESHOLD times."""
        return [
            i for i in self._items.values()
            if i.times_seen >= self.PERSISTENT_THRESHOLD and not i.resolved
        ]

    def get_human_attention_items(self) -> list[FeedbackItem]:
        """Items seen >= HUMAN_ATTENTION_THRESHOLD times."""
        return [
            i for i in self._items.values()
            if i.times_seen >= self.HUMAN_ATTENTION_THRESHOLD and not i.resolved
        ]

    def all_items(self) -> list[FeedbackItem]:
        return list(self._items.values())

    @staticmethod
    def _make_id(test_case: str, message: str) -> str:
        raw = f"{test_case}:{message}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]
