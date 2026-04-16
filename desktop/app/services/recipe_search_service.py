"""Deterministic search and filtering across recipe graph."""

from __future__ import annotations

from dataclasses import dataclass

from desktop.app.domain.models import Recipe


def _normalize_match_text(text: str) -> str:
    return " ".join(text.strip().lower().split())


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
    # When True and query is non-empty, recipe must match via ingredient raw_text, structured name, or linked catalog name.
    ingredient_focus: bool = False


@dataclass(slots=True)
class RecipeSearchResult:
    recipe: Recipe
    score: int
    match_hints: tuple[str, ...] = ()


class RecipeSearchService:
    def search(
        self,
        recipes: list[Recipe],
        query: str,
        filters: RecipeSearchFilters | None = None,
        *,
        catalog_names_by_id: dict[str, str] | None = None,
    ) -> list[RecipeSearchResult]:
        normalized_query = query.strip().lower()
        norm_query_folded = _normalize_match_text(query) if query.strip() else ""
        filters = filters or RecipeSearchFilters()
        catalog_names_by_id = catalog_names_by_id or {}
        results: list[RecipeSearchResult] = []
        for recipe in recipes:
            if not self._matches_filters(recipe, filters):
                continue
            score, ing_score, hints = self._score_recipe(recipe, normalized_query, norm_query_folded, catalog_names_by_id)
            if filters.ingredient_focus and normalized_query and ing_score == 0:
                continue
            if normalized_query and score == 0:
                continue
            results.append(RecipeSearchResult(recipe=recipe, score=score, match_hints=hints))
        results.sort(key=lambda item: (-item.score, item.recipe.title.lower(), item.recipe.id))
        return results

    def _score_recipe(
        self,
        recipe: Recipe,
        query: str,
        norm_query_folded: str,
        catalog_names_by_id: dict[str, str],
    ) -> tuple[int, int, tuple[str, ...]]:
        """Returns (total_score, ingredient_match_score, sorted hint labels for subtle UI)."""
        if not query:
            return 1, 0, ()
        score = 0
        ing_score = 0
        hints: set[str] = set()
        if query in recipe.title.lower():
            score += 50
        if recipe.subtitle and query in recipe.subtitle.lower():
            score += 25
            hints.add("subtitle")
        if recipe.author and query in recipe.author.lower():
            score += 15
            hints.add("author")
        for tag in recipe.tags:
            t = tag.strip().lower()
            if query in t or (norm_query_folded and norm_query_folded in _normalize_match_text(tag)):
                score += 24
                hints.add("tag")
        for ingredient in recipe.ingredients:
            raw_l = ingredient.raw_text.lower()
            if query in raw_l or (norm_query_folded and norm_query_folded in _normalize_match_text(ingredient.raw_text)):
                score += 20
                ing_score += 20
                hints.add("ingredient")
            if ingredient.ingredient_name:
                iname = ingredient.ingredient_name.lower()
                if query in iname or (
                    norm_query_folded and norm_query_folded in _normalize_match_text(ingredient.ingredient_name)
                ):
                    score += 15
                    ing_score += 15
                    hints.add("ingredient")
            cid = ingredient.catalog_ingredient_id
            if cid:
                cname = catalog_names_by_id.get(cid)
                if cname:
                    cn_l = cname.lower()
                    if query in cn_l or (norm_query_folded and norm_query_folded in _normalize_match_text(cname)):
                        score += 22
                        ing_score += 22
                        hints.add("catalog")
        for equipment in recipe.equipment:
            if query in equipment.name.lower():
                score += 15
                hints.add("equipment")
        for step in recipe.steps:
            if query in step.body_text.lower():
                score += 10
                hints.add("step")
        return score, ing_score, tuple(sorted(hints))

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

