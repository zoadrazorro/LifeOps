from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from lifeops.core.life_state import LifeState


@dataclass
class NeuronSuggestion:
    """
    Generic suggestion object that all neurons can emit.
    The arbiter will combine/compare these.
    """
    neuron: str
    priority: str                 # "HIGH" | "MEDIUM" | "LOW"
    suggestion_type: str          # "focus_block" | "micro_task" | ...
    text: str                     # human-facing description
    expected_duration_min: int
    project: Optional[str] = None
    confidence: float = 0.7       # 0.0–1.0 for arbiter sorting


class FocusNeuron:
    """
    Responsible for suggesting 'what to work on' in focused work modes.

    v1 rules:
    - Only operates in mode == "work_deep"
    - Requires a primary_project
    - Uses recent focus sessions + energy_hint to pick block length
    """

    def __init__(
        self,
        default_block_min: int = 25,
        short_block_min: int = 15,
        micro_block_min: int = 5,
        min_gap_between_focus_min: int = 15,
    ) -> None:
        self.default_block_min = default_block_min
        self.short_block_min = short_block_min
        self.micro_block_min = micro_block_min
        self.min_gap_between_focus_min = min_gap_between_focus_min

    def suggest(self, state: LifeState) -> Optional[NeuronSuggestion]:
        # Only suggest in deep work mode with a primary project.
        if state.mode != "work_deep":
            return None
        if not state.primary_project:
            return None

        # Avoid spamming if we *just* finished a focus session.
        minutes_since = state.minutes_since_last_session("focus")
        if minutes_since is not None and minutes_since < self.min_gap_between_focus_min:
            return None

        project = state.primary_project

        # Determine block length based on energy_hint.
        energy = (state.energy_hint or "unknown").lower()
        if energy == "low":
            block_min = self.micro_block_min
            priority = "MEDIUM"
            confidence = 0.7
            task_verb = "Take a small bite out of"
        elif energy == "medium":
            block_min = self.short_block_min
            priority = "HIGH"
            confidence = 0.8
            task_verb = "Make solid progress on"
        else:  # high or unknown
            block_min = self.default_block_min
            priority = "HIGH"
            confidence = 0.85
            task_verb = "Push forward on"

        # Super simple task description for v1; later this can call an LLM.
        text = (
            f"{task_verb} {project}: "
            f"pick one small concrete subtask and work on it for {block_min} minutes."
        )

        return NeuronSuggestion(
            neuron="FocusNeuron",
            priority=priority,
            suggestion_type="focus_block",
            text=text,
            expected_duration_min=block_min,
            project=project,
            confidence=confidence,
        )
