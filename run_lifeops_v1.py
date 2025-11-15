from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List

from lifeops.core.life_state import LifeState, SceneState, RecentSession
from lifeops.neurons.focus_neuron import FocusNeuron, NeuronSuggestion


# --------- Mock systems for test mode --------- #

class MockCalendar:
    def get_current_block(self) -> dict:
        # In real code, this would inspect your actual calendar.
        return {
            "title": "Deep Work - Project Horizon",
            "mode": "work_deep",
            "primary_project": "Project Horizon",
            "time_block": "afternoon",
            "location_hint": "home_office",
        }


class MockScene:
    def detect_scene(self) -> SceneState:
        # Stand-in for real vision. Hard-coded "home office".
        return SceneState(
            scene_type="home_office",
            objects=["laptop", "notebook", "coffee_mug"],
            people_present="solo",
            text_snippets=[],
            risk_flags=["indoors", "not_driving"],
        )


class MockHUD:
    def show_suggestion(self, text: str) -> None:
        print(f"[HUD] {text}")

    def ask_yes_no(self, prompt: str) -> bool:
        print(f"[HUD PROMPT] {prompt} [auto-YES in test mode]")
        # In real life, this comes from Neural Band or voice.
        return True

    def notify(self, text: str) -> None:
        print(f"[HUD NOTIFY] {text}")


# --------- Simple ActionArbiterLife --------- #

@dataclass
class SuggestedAction:
    binding_id: str
    suggestion: NeuronSuggestion


class ActionArbiterLife:
    """
    Minimal v1 arbiter:
    - takes suggestions from neurons
    - picks the highest-priority, highest-confidence one
    """

    PRIORITY_RANK = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

    def __init__(self) -> None:
        self._candidates: List[NeuronSuggestion] = []

    def request_action(self, suggestion: NeuronSuggestion) -> None:
        self._candidates.append(suggestion)

    def decide(self, state: LifeState) -> Optional[SuggestedAction]:
        if not self._candidates:
            return None

        # Sort by priority then confidence.
        sorted_candidates = sorted(
            self._candidates,
            key=lambda s: (self.PRIORITY_RANK.get(s.priority, 0), s.confidence),
            reverse=True,
        )
        best = sorted_candidates[0]
        binding_id = f"{state.timestamp.isoformat()}_{best.suggestion_type}"
        self._candidates.clear()
        return SuggestedAction(binding_id=binding_id, suggestion=best)


# --------- Test mode driver --------- #

def run_test_mode(duration_seconds: int = 60) -> None:
    print("=== LifeOps v1 Test Mode ===")
    print(f"Running for ~{duration_seconds} seconds...\n")

    calendar = MockCalendar()
    scene_detector = MockScene()
    hud = MockHUD()

    focus_neuron = FocusNeuron()
    arbiter = ActionArbiterLife()

    start = datetime.now()
    now = start
    end = start + timedelta(seconds=duration_seconds)

    # Seed initial LifeState
    cal_block = calendar.get_current_block()
    state = LifeState(
        user_id="tyler",
        timestamp=now,
        mode=cal_block["mode"],
        time_block=cal_block["time_block"],
        location_hint=cal_block["location_hint"],
        scene=scene_detector.detect_scene(),
        primary_project=cal_block["primary_project"],
        secondary_projects=[],
        open_loops=[],
        recent_sessions=[],
        energy_hint="medium",
        preference_profile={"nudges_per_hour_max": 4},
    )

    print("[INIT]", state.describe_context())

    # ---- Tick loop ---- #
    suggested_action: Optional[SuggestedAction] = None
    focus_block_started: Optional[datetime] = None
    focus_block_duration_min: Optional[int] = None

    tick = 0
    while datetime.now() < end:
        tick += 1
        now = datetime.now()
        state = state.with_updated_timestamp(now)

        print(f"\n[TICK {tick}] {state.timestamp.time()}")

        # If we don't have an active focus block, ask neuron for suggestions.
        if not focus_block_started:
            suggestion = focus_neuron.suggest(state)
            if suggestion:
                print(f"[FocusNeuron] Proposed: {suggestion.text} "
                      f"({suggestion.expected_duration_min} min, priority={suggestion.priority})")
                arbiter.request_action(suggestion)

        # Arbiter decides what to do.
        decision = arbiter.decide(state)
        if decision and not focus_block_started:
            suggested_action = decision
            hud.show_suggestion(decision.suggestion.text)
            accepted = hud.ask_yes_no("Accept this focus block?")
            if accepted:
                focus_block_started = now
                focus_block_duration_min = decision.suggestion.expected_duration_min
                print(f"[ARB] Accepted suggestion, starting focus block for "
                      f"{focus_block_duration_min} minutes")
            else:
                print("[ARB] Suggestion rejected")
                suggested_action = None

        # If we're in a focus block, check if it's done.
        if focus_block_started and focus_block_duration_min is not None:
            elapsed_min = (now - focus_block_started).total_seconds() / 60.0
            if elapsed_min >= focus_block_duration_min:
                hud.notify("Focus block complete!")
                # In real life you'd ask the user how it went; here we fake it.
                self_report = 8
                print(f"[OUTCOME] Focus completed, self_report={self_report}/10")

                # Add to recent_sessions
                state.recent_sessions.append(
                    RecentSession(
                        type="focus",
                        project=state.primary_project,
                        duration_min=focus_block_duration_min,
                        completed=True,
                        ended_at=now,
                    )
                )

                # Reset
                focus_block_started = None
                focus_block_duration_min = None
                suggested_action = None

        time.sleep(5)  # 5s per tick in test mode

    print("\n=== LifeOps v1 Test Mode Completed ===")
    # Quick summary
    focus_sessions = [s for s in state.recent_sessions if s.type == "focus"]
    print(f"Focus sessions completed: {len(focus_sessions)}")
    for i, s in enumerate(focus_sessions, 1):
        print(f"  #{i}: project={s.project}, duration={s.duration_min} min, "
              f"ended_at={s.ended_at}")


if __name__ == "__main__":
    run_test_mode(duration_seconds=60)
