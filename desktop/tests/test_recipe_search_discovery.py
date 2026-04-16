"""Deterministic library search: ingredients, catalog links, tags, filters, ordering."""

from __future__ import annotations

from uuid import uuid4

from desktop.app.domain.models import Recipe
from desktop.app.services.recipe_search_service import RecipeSearchFilters, RecipeSearchService


def _recipe(**kwargs) -> Recipe:
    defaults = dict(
        id=str(uuid4()),
        scope="local",
        title="Untitled",
        status="draft",
        created_at="2020-01-01T00:00:00Z",
        updated_at="2020-01-01T00:00:00Z",
        equipment=[],
        ingredients=[],
        steps=[],
        step_links=[],
        tags=[],
        schema_version=1,
        bundle_export_eligible=False,
        export_bundle_recipe_version=1,
        is_forked_from_bundled=False,
        display_settings={},
    )
    defaults.update(kwargs)
    return Recipe.from_dict(defaults)


def test_search_matches_raw_ingredient_text() -> None:
    r = _recipe(
        title="Plain Salad",
        ingredients=[
            {
                "id": str(uuid4()),
                "raw_text": "2 red peppers, diced",
                "is_optional": False,
                "display_order": 0,
            }
        ],
    )
    svc = RecipeSearchService()
    out = svc.search([r], "red pepper", RecipeSearchFilters(scope="local"))
    assert len(out) == 1
    assert "ingredient" in out[0].match_hints


def test_search_matches_linked_catalog_ingredient_name_not_in_raw_text() -> None:
    cid = str(uuid4())
    r = _recipe(
        title="Mystery Dish",
        ingredients=[
            {
                "id": str(uuid4()),
                "raw_text": "a pinch of spice mix",
                "is_optional": False,
                "display_order": 0,
                "catalog_ingredient_id": cid,
            }
        ],
    )
    catalog = {cid: "Red Pepper Flakes"}
    svc = RecipeSearchService()
    out = svc.search([r], "red pepper", RecipeSearchFilters(scope="local"), catalog_names_by_id=catalog)
    assert len(out) == 1
    assert "catalog" in out[0].match_hints


def test_search_matches_tag_text() -> None:
    r = _recipe(title="Soup", tags=["weeknight", "vegan"])
    svc = RecipeSearchService()
    out = svc.search([r], "vegan", RecipeSearchFilters(scope="local"))
    assert len(out) == 1
    assert "tag" in out[0].match_hints


def test_tag_filter_match_all_with_search() -> None:
    a = _recipe(title="A", tags=["quick", "vegan"], ingredients=[])
    b = _recipe(title="B", tags=["quick"], ingredients=[])
    svc = RecipeSearchService()
    out = svc.search([a, b], "quick", RecipeSearchFilters(scope="local", tags=["vegan"]))
    assert [x.recipe.id for x in out] == [a.id]


def test_ingredient_focus_excludes_title_only_match() -> None:
    r = _recipe(title="Red Pepper Story", ingredients=[])
    svc = RecipeSearchService()
    out = svc.search(
        [r],
        "red pepper",
        RecipeSearchFilters(scope="local", ingredient_focus=True),
    )
    assert out == []


def test_deterministic_ordering_same_score() -> None:
    r1 = _recipe(title="B Soup", id=str(uuid4()))
    r2 = _recipe(title="A Soup", id=str(uuid4()))
    svc = RecipeSearchService()
    out = svc.search([r1, r2], "soup", RecipeSearchFilters(scope="local"))
    titles = [x.recipe.title for x in out]
    assert titles == ["A Soup", "B Soup"]


def test_normalized_whitespace_query_matches_catalog_name() -> None:
    cid = str(uuid4())
    r = _recipe(
        title="X",
        ingredients=[
            {
                "id": str(uuid4()),
                "raw_text": "something",
                "is_optional": False,
                "display_order": 0,
                "catalog_ingredient_id": cid,
            }
        ],
    )
    catalog = {cid: "Red   Pepper"}
    svc = RecipeSearchService()
    out = svc.search([r], "red  pepper", RecipeSearchFilters(scope="local"), catalog_names_by_id=catalog)
    assert len(out) == 1
