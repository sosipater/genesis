"""Meal planning, scaling, and grocery list generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from desktop.app.domain.models import Recipe, RecipeIngredientItem
from desktop.app.persistence.recipe_repository import RecipeRepository

_MAX_SUB_RECIPE_DEPTH = 24


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

    def generate_grocery_items(self, recipes_with_factors: list[tuple[Recipe, float]]) -> tuple[list[GroceryItem], list[str]]:
        grouped: dict[tuple[str, str | None], GroceryItem] = {}
        warnings: list[str] = []
        for recipe, factor in recipes_with_factors:
            self._accumulate_recipe_ingredients(
                grouped,
                recipe,
                factor,
                stack=frozenset(),
                depth=0,
                top_source_recipe_id=recipe.id,
                warnings=warnings,
            )
        return (
            sorted(grouped.values(), key=lambda item: (item.name.lower(), item.unit or "")),
            warnings,
        )

    def _accumulate_recipe_ingredients(
        self,
        grouped: dict[tuple[str, str | None], GroceryItem],
        recipe: Recipe,
        factor: float,
        *,
        stack: frozenset[str],
        depth: int,
        top_source_recipe_id: str,
        warnings: list[str],
    ) -> None:
        if depth > _MAX_SUB_RECIPE_DEPTH:
            warnings.append(
                f"Grocery expansion: stopped at max sub-recipe depth ({_MAX_SUB_RECIPE_DEPTH}) "
                f"while expanding from meal-plan recipe {top_source_recipe_id} (encountered {recipe.title!r})."
            )
            return
        if recipe.id in stack:
            warnings.append(
                f"Grocery expansion: circular sub-recipe chain skipped at {recipe.title!r} ({recipe.id}); "
                "that recipe already appears on the expansion path."
            )
            return
        next_stack = stack | {recipe.id}
        for ingredient in sorted(recipe.ingredients, key=lambda row: row.display_order):
            if ingredient.sub_recipe_id:
                self._expand_sub_recipe(
                    grouped,
                    ingredient,
                    factor,
                    stack=next_stack,
                    depth=depth + 1,
                    top_source_recipe_id=top_source_recipe_id,
                    warnings=warnings,
                )
            else:
                self._merge_plain_ingredient(grouped, ingredient, factor, top_source_recipe_id)

    def _expand_sub_recipe(
        self,
        grouped: dict[tuple[str, str | None], GroceryItem],
        ingredient: RecipeIngredientItem,
        factor: float,
        *,
        stack: frozenset[str],
        depth: int,
        top_source_recipe_id: str,
        warnings: list[str],
    ) -> None:
        usage = ingredient.sub_recipe_usage_type or "full_batch"
        if usage not in ("full_batch", "fraction_of_batch"):
            warnings.append(
                f"Grocery expansion: unknown sub-recipe usage {usage!r} on {ingredient.raw_text!r}; treated as full_batch."
            )
            usage = "full_batch"
        sub_mult = 1.0 if usage == "full_batch" else float(ingredient.sub_recipe_multiplier or 0.0)
        if usage == "fraction_of_batch" and sub_mult <= 0:
            warnings.append(
                f"Grocery expansion: invalid sub-recipe multiplier on {ingredient.raw_text!r}; using 1.0."
            )
            sub_mult = 1.0
        combined = factor * sub_mult
        sub = self._repository.get_recipe_by_id(ingredient.sub_recipe_id or "")
        if sub is None:
            label = (ingredient.sub_recipe_display_name or ingredient.ingredient_name or ingredient.raw_text).strip()
            warnings.append(
                f"Grocery expansion: missing sub-recipe {label!r} (id {ingredient.sub_recipe_id}) "
                f"referenced from meal-plan recipe {top_source_recipe_id}."
            )
            self._merge_missing_placeholder(grouped, label, top_source_recipe_id, ingredient.id)
            return
        self._accumulate_recipe_ingredients(
            grouped,
            sub,
            combined,
            stack=stack,
            depth=depth,
            top_source_recipe_id=top_source_recipe_id,
            warnings=warnings,
        )

    def _merge_missing_placeholder(
        self,
        grouped: dict[tuple[str, str | None], GroceryItem],
        label: str,
        source_recipe_id: str,
        ingredient_line_id: str,
    ) -> None:
        display = f"[Missing recipe] {label}".strip() or "[Missing recipe]"
        name_key = display.lower()
        unit: str | None = None
        key = (name_key, unit)
        group_key = f"__missing_sub__::{ingredient_line_id}"
        if key not in grouped:
            grouped[key] = GroceryItem(
                name=display,
                quantity_value=None,
                unit=None,
                source_recipe_ids=[source_recipe_id],
                generated_group_key=group_key,
            )
        else:
            current = grouped[key]
            if source_recipe_id not in current.source_recipe_ids:
                current.source_recipe_ids.append(source_recipe_id)

    def _merge_plain_ingredient(
        self,
        grouped: dict[tuple[str, str | None], GroceryItem],
        ingredient: RecipeIngredientItem,
        factor: float,
        source_recipe_id: str,
    ) -> None:
        name = (ingredient.ingredient_name or ingredient.raw_text).strip().lower()
        display_name = ingredient.ingredient_name or ingredient.raw_text
        unit_norm = ingredient.unit.strip().lower() if ingredient.unit else None
        key = (name, unit_norm)
        group_key = f"{name}::{unit_norm or '_'}"
        scaled_qty = ingredient.quantity_value * factor if ingredient.quantity_value is not None else None
        if key not in grouped:
            grouped[key] = GroceryItem(
                name=display_name,
                quantity_value=scaled_qty,
                unit=ingredient.unit,
                source_recipe_ids=[source_recipe_id],
                generated_group_key=group_key,
            )
        else:
            current = grouped[key]
            if source_recipe_id not in current.source_recipe_ids:
                current.source_recipe_ids.append(source_recipe_id)
            if current.quantity_value is not None and scaled_qty is not None:
                current.quantity_value = round(current.quantity_value + scaled_qty, 3)
            else:
                current.quantity_value = None
