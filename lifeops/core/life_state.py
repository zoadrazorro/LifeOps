from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any


# --------- Low-level submodels --------- #

@dataclass
class SceneState:
    """
    High-level description of what the glasses/phone see.
    This is the LifeOps equivalent of game perception.
    """
    scene_type: str = "unknown"        # e.g. home_office, kitchen, gym, outdoors
    objects: List[str] = field(default_factory=list)  # laptop, notebook, barbell, etc.
    people_present: str = "unknown"    # solo | small_group | crowd | unknown
    text_snippets: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)  # e.g. ["not_driving", "indoors"]


@dataclass
class OpenLoop:
    """
    An unresolved commitment or task that matters.
    """
    type: str                          # e.g. "email_reply", "outline_section"
    label: str                         # human label: "Reply to Client A"
    project: Optional[str] = None      # which project it's attached to, if any
    due_by: Optional[datetime] = None  # soft/hard deadline


@dataclass
class RecentSession:
    """
    A chunk of time where you did something structured (focus block, workout, etc.).
    Used to avoid over-scheduling and understand recent effort.
    """
    type: str                          # "focus", "workout", "walk"
    project: Optional[str] = None
    duration_min: int = 0
    completed: bool = False
    ended_at: Optional[datetime] = None


# --------- Core LifeState model --------- #

@dataclass
class LifeState:
    """
    The 'BeingState' for your real life.

    This lives in RAM on the LifeOps core and is updated every time a
    LifeOps event comes from the phone/glasses.
    """
    user_id: str
    timestamp: datetime

    # High-level mode & context
    mode: str                          # e.g. work_deep, walking, gym, home_evening
    time_block: str                    # morning | afternoon | evening | night
    location_hint: str                 # home_office | living_room | gym | etc.

    # Perception
    scene: SceneState = field(default_factory=SceneState)

    # Projects & work
    primary_project: Optional[str] = None
    secondary_projects: List[str] = field(default_factory=list)
    open_loops: List[OpenLoop] = field(default_factory=list)
    recent_sessions: List[RecentSession] = field(default_factory=list)

    # Internal signals
    energy_hint: str = "unknown"       # low | medium | high | unknown
    preference_profile: Dict[str, Any] = field(default_factory=dict)

    def describe_context(self) -> str:
        """
        Human/LLM-friendly summary of what is going on right now.
        Great for logs, prompts, and debugging.
        """
        scene_desc = f"{self.scene.scene_type or 'unknown'}"
        if self.scene.objects:
            scene_desc += f" with {', '.join(self.scene.objects[:3])}"
            if len(self.scene.objects) > 3:
                scene_desc += ", ..."
        return (
            f"[{self.timestamp.isoformat()}] mode={self.mode}, "
            f"location={self.location_hint}, scene={scene_desc}, "
            f"primary_project={self.primary_project}, time_block={self.time_block}, "
            f"energy={self.energy_hint}, open_loops={len(self.open_loops)}"
        )

    def last_session_of_type(self, session_type: str) -> Optional[RecentSession]:
        """
        Return the most recent session of a given type, if any.
        """
        candidates = [s for s in self.recent_sessions if s.type == session_type]
        if not candidates:
            return None
        return max(candidates, key=lambda s: s.ended_at or self.timestamp)

    def minutes_since_last_session(self, session_type: str) -> Optional[int]:
        """
        How long since we last did a given type of session (focus, workout, etc.).
        """
        last = self.last_session_of_type(session_type)
        if not last or not last.ended_at:
            return None
        delta: timedelta = self.timestamp - last.ended_at
        return int(delta.total_seconds() // 60)

    def with_updated_timestamp(self, ts: datetime) -> "LifeState":
        """
        Convenience for 'same state, new timestamp'.
        """
        new_state = LifeState(
            user_id=self.user_id,
            timestamp=ts,
            mode=self.mode,
            time_block=self.time_block,
            location_hint=self.location_hint,
            scene=self.scene,
            primary_project=self.primary_project,
            secondary_projects=list(self.secondary_projects),
            open_loops=list(self.open_loops),
            recent_sessions=list(self.recent_sessions),
            energy_hint=self.energy_hint,
            preference_profile=dict(self.preference_profile),
        )
        return new_state
