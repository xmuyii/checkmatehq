# timers.py
import time
from typing import Dict, Optional


class ActiveTimer:
    """Represents an individual countdown timer."""
    def __init__(self, key: str, label: str, duration_seconds: float, icon: str = "⏳"):
        self.key = key
        self.label = label
        self.icon = icon
        self.expires_at = time.time() + duration_seconds

    @property
    def remaining(self) -> float:
        """Returns remaining seconds (clamped to 0)."""
        return max(0.0, self.expires_at - time.time())

    @property
    def is_expired(self) -> bool:
        return self.remaining <= 0

    def extend(self, extra_seconds: float):
        """Extends an ongoing timer."""
        self.expires_at += extra_seconds

    def format_countdown(self) -> str:
        """Formats remaining time into MM:SS or human-readable string."""
        rem = int(self.remaining)
        mins, secs = divmod(rem, 60)
        if mins > 0:
            return f"{mins:02d}m {secs:02d}s"
        return f"{secs:02d}s"


class TimerManager:
    """Manages all active timers for a player session or active engine round."""
    def __init__(self):
        self.timers: Dict[str, ActiveTimer] = {}

    def set_timer(self, key: str, label: str, duration_seconds: float, icon: str = "⏳"):
        """Sets or overwrites a timer."""
        self.timers[key] = ActiveTimer(key, label, duration_seconds, icon)

    def get_timer(self, key: str) -> Optional[ActiveTimer]:
        return self.timers.get(key)

    def remove_timer(self, key: str):
        self.timers.pop(key, None)

    def cleanup_expired(self):
        """Purges expired timers from memory."""
        expired_keys = [k for k, t in self.timers.items() if t.is_expired]
        for k in expired_keys:
            del self.timers[k]

    def render_dashboard_block(self) -> str:
        """Generates a clean Markdown block of all active countdowns for the DM dashboard."""
        active = [t for t in self.timers.values() if not t.is_expired]
        if not active:
            return "⏱️ *No active cooldowns or effects.*"

        lines = ["<b>⏱️ ACTIVE TIMERS & BUFFS</b>", "━━━━━━━━━━━━━━━━━"]
        for t in sorted(active, key=lambda x: x.remaining):
            lines.append(f"{t.icon} <b>{t.label}:</b> <code>{t.format_countdown()}</code>")
        return "\n".join(lines)

    # ─── SERIALIZATION FOR DB PERSISTENCE ─────────────────────────
    def to_dict() -> dict:
        """Exports remaining times for database saving."""
        return {
            k: {
                "label": t.label,
                "expires_at": t.expires_at,
                "icon": t.icon
            }
            for k, t in self.timers.items() if not t.is_expired
        }

    def load_from_dict(self, data: dict):
        """Restores timers from database upon reload."""
        now = time.time()
        for k, v in data.items():
            if v["expires_at"] > now:
                t = ActiveTimer(k, v["label"], 0, v.get("icon", "⏳"))
                t.expires_at = v["expires_at"]
                self.timers[k] = t