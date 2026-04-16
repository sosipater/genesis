"""Deterministic search and filtering across recipe graph."""

from __future__ import annotations

from dataclasses import dataclass

from desktop.app.domain.models import Recipe


@dataclass(slots=True)
class RecipeSearchFilters:
    scope: str | None = None  # local | bundled | forked
    difficulty: str | None = None
    servings_min: float | None = None
    servings_max: float | None = None
    total_minutes_max: int | None = None
    prep_minutes_max: int | None = None
    cook_minutes_max: int | None = None
    tags: list[str] | None = None


@dataclass(slots=True)
class RecipeSearchResult:
    recipe: Recipe
    score: int


class RecipeSearchService:
    def search(self, recipes: list[Recipe], query: str, filters: RecipeSearchFilters | None = None) -> list[RecipeSearchResult]:
        normalized_query = query.strip().lower()
        filters = filters or RecipeSearchFilters()
        results: list[RecipeSearchResult] = []
        for recipe in recipes:
            if not self._matches_filters(recipe, filters):
                continue
            score = self._score_recipe(recipe, normalized_query)
            if normalized_query and score == 0:
                continue
            results.append(RecipeSearchResult(recipe=recipe, score=score))
        results.sort(key=lambda item: (-item.score, item.recipe.title.lower(), item.recipe.id))
        return results

    def _score_recipe(self, recipe: Recipe, query: str) -> int:
        if not query:
            return 1
        score = 0
        if query in recipe.title.lower():
            score += 50
        if recipe.subtitle and query in recipe.subtitle.lower():
            score += 25
        if recipe.author and query in recipe.author.lower():
            score += 15
        for ingredient in recipe.ingredients:
            if query in ingredient.raw_text.lower():
                score += 20
            if ingredient.ingredient_name and query in ingredient.ingredient_name.lower():
                score += 15
        for equipment in recipe.equipment:
            if query in equipment.name.lower():
                score += 15
        for step in recipe.steps:
            if query in step.body_text.lower():
                score += 10
        return score

    def _matches_filters(self, recipe: Recipe, filters: RecipeSearchFilters) -> bool:
        if filters.scope == "local" and recipe.scope != "local":
            return False
        if filters.scope == "bundled" and recipe.scope != "bundled":
            return False
        if filters.scope == "forked" and not recipe.is_forked_from_bundled:
            return False
        if filters.difficulty and (recipe.difficulty or "").lower() != filters.difficulty.lower():
            return False
        if filters.servings_min is not None and (recipe.servings is None or recipe.servings < filters.servings_min):
            return False
        if filters.servings_max is not None and (recipe.servings is None or recipe.servings > filters.servings_max):
            return False
        if filters.total_minutes_max is not None and (recipe.total_minutes is None or recipe.total_minutes > filters.total_minutes_max):
            return False
        if filters.prep_minutes_max is not None and (recipe.prep_minutes is None or recipe.prep_minutes > filters.prep_minutes_max):
            return False
        if filters.cook_minutes_max is not None and (recipe.cook_minutes is None or recipe.cook_minutes > filters.cook_minutes_max):
            return False
        if filters.tags:
            recipe_tags = {tag.lower() for tag in recipe.tags}
            required = {tag.lower() for tag in filters.tags}
            if not required.issubset(recipe_tags):
                return False
        return True

