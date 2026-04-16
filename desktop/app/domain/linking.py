"""Utilities for step link resolution and fallback rendering."""

from __future__ import annotations

from desktop.app.domain.models import Recipe, StepLink


def resolve_step_link_label(recipe: Recipe, link: StepLink) -> str:
    if link.label_override:
        return link.label_override
    if link.target_type == "ingredient":
        for item in recipe.ingredients:
            if item.id == link.target_id:
                return item.ingredient_name or item.raw_text
    elif link.target_type == "equipment":
        for item in recipe.equipment:
            if item.id == link.target_id:
                return item.name
    return link.label_snapshot


def link_target_exists(recipe: Recipe, link: StepLink) -> bool:
    if link.target_type == "ingredient":
        return any(item.id == link.target_id for item in recipe.ingredients)
    if link.target_type == "equipment":
        return any(item.id == link.target_id for item in recipe.equipment)
    return False

