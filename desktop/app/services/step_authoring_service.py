"""Structured step link/timer authoring helpers."""

from __future__ import annotations

import re
from dataclasses import replace
from uuid import uuid4

from desktop.app.domain.models import Recipe, RecipeStep, StepLink, StepTimer

TOKEN_PATTERN = re.compile(r"\[\[(ingredient|equipment):([^\]]+)\]\]")


class StepAuthoringService:
    def add_link(
        self,
        recipe: Recipe,
        step_id: str,
        target_type: str,
        target_id: str,
        token_key: str,
        label_snapshot: str,
        label_override: str | None = None,
    ) -> StepLink:
        if target_type not in ("ingredient", "equipment"):
            raise ValueError("target_type must be ingredient/equipment")
        if not token_key.strip():
            raise ValueError("token_key cannot be empty")
        self._validate_target_exists(recipe, target_type, target_id)
        link = StepLink(
            id=str(uuid4()),
            step_id=step_id,
            target_type=target_type,  # type: ignore[arg-type]
            target_id=target_id,
            token_key=token_key.strip(),
            label_snapshot=label_snapshot.strip() or token_key.strip(),
            label_override=label_override.strip() if label_override and label_override.strip() else None,
        )
        recipe.step_links.append(link)
        self._ensure_token_present(recipe, step_id, link)
        return link

    def update_link(
        self,
        recipe: Recipe,
        link_id: str,
        *,
        token_key: str,
        label_override: str | None,
    ) -> None:
        link = next((lnk for lnk in recipe.step_links if lnk.id == link_id), None)
        if link is None:
            raise ValueError(f"link {link_id} not found")
        old_token = link.token_key
        link.token_key = token_key.strip()
        if not link.token_key:
            raise ValueError("token_key cannot be empty")
        link.label_override = label_override.strip() if label_override and label_override.strip() else None
        self._replace_token_in_body(recipe, link.step_id, link.target_type, old_token, link.token_key)

    def remove_link(self, recipe: Recipe, link_id: str) -> None:
        link = next((lnk for lnk in recipe.step_links if lnk.id == link_id), None)
        if link is None:
            return
        recipe.step_links = [lnk for lnk in recipe.step_links if lnk.id != link_id]
        self._remove_token_from_body(recipe, link.step_id, link.target_type, link.token_key)

    def add_timer(
        self,
        step: RecipeStep,
        label: str,
        duration_seconds: int,
        auto_start: bool,
        alert_sound_key: str | None,
        *,
        alert_vibrate: bool = False,
    ) -> StepTimer:
        if duration_seconds <= 0:
            raise ValueError("timer duration must be > 0")
        if not label.strip():
            raise ValueError("timer label cannot be empty")
        timer = StepTimer(
            id=str(uuid4()),
            label=label.strip(),
            duration_seconds=duration_seconds,
            auto_start=auto_start,
            alert_sound_key=alert_sound_key.strip() if alert_sound_key and alert_sound_key.strip() else None,
            alert_vibrate=alert_vibrate,
        )
        step.timers.append(timer)
        return timer

    def update_timer(
        self,
        step: RecipeStep,
        timer_id: str,
        *,
        label: str,
        duration_seconds: int,
        auto_start: bool,
        alert_sound_key: str | None,
        alert_vibrate: bool = False,
    ) -> None:
        if duration_seconds <= 0:
            raise ValueError("timer duration must be > 0")
        timer = next((t for t in step.timers if t.id == timer_id), None)
        if timer is None:
            raise ValueError(f"timer {timer_id} not found")
        timer.label = label.strip() or timer.label
        timer.duration_seconds = duration_seconds
        timer.auto_start = auto_start
        timer.alert_sound_key = alert_sound_key.strip() if alert_sound_key and alert_sound_key.strip() else None
        timer.alert_vibrate = alert_vibrate

    def remove_timer(self, step: RecipeStep, timer_id: str) -> None:
        step.timers = [timer for timer in step.timers if timer.id != timer_id]

    def render_preview_segments(self, recipe: Recipe, step: RecipeStep) -> list[tuple[str, StepLink | None]]:
        segments: list[tuple[str, StepLink | None]] = []
        cursor = 0
        for match in TOKEN_PATTERN.finditer(step.body_text):
            if match.start() > cursor:
                segments.append((step.body_text[cursor : match.start()], None))
            target_type = match.group(1)
            token_key = match.group(2)
            link = next(
                (
                    lnk
                    for lnk in recipe.step_links
                    if lnk.step_id == step.id and lnk.target_type == target_type and lnk.token_key == token_key
                ),
                None,
            )
            label = (link.label_override if link and link.label_override else None) or (link.label_snapshot if link else token_key)
            segments.append((label, link))
            cursor = match.end()
        if cursor < len(step.body_text):
            segments.append((step.body_text[cursor:], None))
        if not segments:
            segments.append((step.body_text, None))
        return segments

    def _validate_target_exists(self, recipe: Recipe, target_type: str, target_id: str) -> None:
        if target_type == "ingredient":
            exists = any(item.id == target_id for item in recipe.ingredients)
        else:
            exists = any(item.id == target_id for item in recipe.equipment)
        if not exists:
            raise ValueError(f"Target {target_type}:{target_id} does not exist in recipe")

    def _ensure_token_present(self, recipe: Recipe, step_id: str, link: StepLink) -> None:
        token = f"[[{link.target_type}:{link.token_key}]]"
        step = next((st for st in recipe.steps if st.id == step_id), None)
        if step is None:
            raise ValueError(f"step {step_id} not found")
        if token in step.body_text:
            return
        step.body_text = f"{step.body_text.strip()} {token}".strip()

    def _replace_token_in_body(self, recipe: Recipe, step_id: str, target_type: str, old_token_key: str, new_token_key: str) -> None:
        step = next((st for st in recipe.steps if st.id == step_id), None)
        if step is None:
            return
        old_token = f"[[{target_type}:{old_token_key}]]"
        new_token = f"[[{target_type}:{new_token_key}]]"
        step.body_text = step.body_text.replace(old_token, new_token)

    def _remove_token_from_body(self, recipe: Recipe, step_id: str, target_type: str, token_key: str) -> None:
        step = next((st for st in recipe.steps if st.id == step_id), None)
        if step is None:
            return
        token = f"[[{target_type}:{token_key}]]"
        step.body_text = step.body_text.replace(token, "").replace("  ", " ").strip()

