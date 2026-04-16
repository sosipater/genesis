"""Meal planning, scaling, and grocery list generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from desktop.app.domain.models import Recipe
from desktop.app.persistence.recipe_repository import RecipeRepository


@dataclass(slots=True)
class GroceryItem:
    name: str
    quantity_value: float | None
    unit: str | None
    source_recipe_ids: list[str]
    generated_group_key: str


class MealPlanService:
    def __init__(self, repository: RecipeRepository):
        self._repository = repository

    def scale_ingredient(self, ingredient: dict[str, Any], factor: float) -> dict[str, Any]:
        scaled = dict(ingredient)
        qty = scaled.get("quantity_value")
        if qty is not None:
            scaled["quantity_value"] = round(float(qty) * factor, 3)
        return scaled

    def generate_grocery_items(self, recipes_with_factors: list[tuple[Recipe, float]]) -> list[GroceryItem]:
        grouped: dict[tuple[str, str | None], GroceryItem] = {}
        for recipe, factor in recipes_with_factors:
            for ingredient in recipe.ingredients:
                name = (ingredient.ingredient_name or ingredient.raw_text).strip().lower()
                display_name = ingredient.ingredient_name or ingredient.raw_text
                unit = ingredient.unit.strip().lower() if ingredient.unit else None
                key = (name, unit)
                group_key = f"{name}::{unit or '_'}"
                scaled_qty = ingredient.quantity_value * factor if ingredient.quantity_value is not None else None
                if key not in grouped:
                    grouped[key] = GroceryItem(
                        name=display_name,
                        quantity_value=scaled_qty,
                        unit=ingredient.unit,
                        source_recipe_ids=[recipe.id],
                        generated_group_key=group_key,
                    )
                else:
                    current = grouped[key]
                    if recipe.id not in current.source_recipe_ids:
                        current.source_recipe_ids.append(recipe.id)
                    if current.quantity_value is not None and scaled_qty is not None:
                        current.quantity_value = round(current.quantity_value + scaled_qty, 3)
                    else:
                        current.quantity_value = None
        return sorted(grouped.values(), key=lambda item: (item.name.lower(), item.unit or ""))

