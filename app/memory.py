

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.rubric import describe_checkpoint
from app.schemas import LessonAttempt

SCHEMA_VERSION = 1
_MAX_RECENT_REASONS_PER_CHECKPOINT = 3


@dataclass
class CheckpointStats:
    fail_count: int = 0
    pass_count: int = 0
    recent_fail_reasons: list[str] = field(default_factory=list)

    def record(self, *, passed: bool, reason: str) -> None:
        if passed:
            self.pass_count += 1
            return
        self.fail_count += 1
        if reason and reason not in self.recent_fail_reasons:
            self.recent_fail_reasons.append(reason)
            self.recent_fail_reasons = self.recent_fail_reasons[-_MAX_RECENT_REASONS_PER_CHECKPOINT:]

    def to_dict(self) -> dict:
        return {
            "fail_count": self.fail_count,
            "pass_count": self.pass_count,
            "recent_fail_reasons": self.recent_fail_reasons,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CheckpointStats":
        return cls(
            fail_count=data.get("fail_count", 0),
            pass_count=data.get("pass_count", 0),
            recent_fail_reasons=list(data.get("recent_fail_reasons", [])),
        )


class MemoryStore:
    

    def __init__(self, path: Path):
        self.path = path

    def _load_raw(self) -> dict:
        if not self.path.exists():
            return {"version": SCHEMA_VERSION, "checkpoint_stats": {}, "runs": []}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            # Corrupt memory file should never crash a run -- start fresh
            # rather than blocking lesson generation.
            return {"version": SCHEMA_VERSION, "checkpoint_stats": {}, "runs": []}

    def _save_raw(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def get_pitfalls_for_generation(self, *, threshold: int, max_pitfalls: int) -> list[str]:
        """Standing guidance strings for checkpoints that have failed often
        enough, historically, to be worth proactively warning the generator
        about. Ranked by fail_count, most-failed first."""
        data = self._load_raw()
        stats_raw: dict = data.get("checkpoint_stats", {})
        entries = []
        for checkpoint_id, raw in stats_raw.items():
            stats = CheckpointStats.from_dict(raw)
            if stats.fail_count >= threshold:
                entries.append((stats.fail_count, checkpoint_id, stats))
        entries.sort(key=lambda e: e[0], reverse=True)

        pitfalls = []
        for fail_count, checkpoint_id, stats in entries[:max_pitfalls]:
            reason_hint = stats.recent_fail_reasons[-1] if stats.recent_fail_reasons else ""
            line = f"{describe_checkpoint(checkpoint_id)} (has failed {fail_count}x historically)"
            if reason_hint:
                line += f" -- common issue: {reason_hint}"
            pitfalls.append(line)
        return pitfalls

    def record_run(
        self,
        *,
        topic: str,
        attempts: list[LessonAttempt],
        final_passed: bool,
    ) -> None:
        data = self._load_raw()
        stats_raw: dict = data.setdefault("checkpoint_stats", {})

        stats_by_id: dict[str, CheckpointStats] = {
            cid: CheckpointStats.from_dict(raw) for cid, raw in stats_raw.items()
        }

        for attempt in attempts:
            for verdict in attempt.evaluation.verdicts:
                stats = stats_by_id.setdefault(verdict.checkpoint_id, CheckpointStats())
                stats.record(passed=verdict.passed, reason=verdict.reason)

        data["checkpoint_stats"] = {cid: s.to_dict() for cid, s in stats_by_id.items()}
        data.setdefault("runs", []).append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "topic": topic,
                "attempts": len(attempts),
                "final_passed": final_passed,
                "final_attempt_failed_checkpoints": (
                    attempts[-1].failed_checkpoint_ids if attempts else []
                ),
            }
        )
        data["version"] = SCHEMA_VERSION
        self._save_raw(data)
