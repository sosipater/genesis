import "package:flutter_test/flutter_test.dart";
import "package:genesis_mobile/data/models/recipe_models.dart";
import "package:genesis_mobile/features/recipe_view/link_resolution.dart";

void main() {
  test("resolves step links by stable ids via step_links metadata", () {
    const RecipeDetail recipe = RecipeDetail(
      id: "r1",
      title: "Recipe",
      scope: "local",
      status: "draft",
      equipment: <RecipeEquipmentItem>[],
      ingredients: <RecipeIngredientItem>[
        RecipeIngredientItem(
          id: "ing1",
          recipeId: "r1",
          rawText: "2 tsp salt",
          ingredientName: "salt",
          isOptional: false,
          displayOrder: 0,
        ),
      ],
      steps: <RecipeStep>[
        RecipeStep(
          id: "s1",
          recipeId: "r1",
          bodyText: "Add [[ingredient:salt]] now.",
          stepType: "instruction",
          displayOrder: 0,
        ),
      ],
      stepLinks: <StepLink>[
        StepLink(
          id: "l1",
          stepId: "s1",
          targetType: "ingredient",
          targetId: "ing1",
          tokenKey: "salt",
          labelSnapshot: "salt",
        ),
      ],
    );

    final result = resolveStepTextSegments(recipe, recipe.steps.first);
    expect(result.segments.any((s) => s.isLink), isTrue);
    expect(result.segments.where((s) => s.isLink).first.link!.targetId, "ing1");
  });

  test("missing link falls back safely", () {
    const RecipeDetail recipe = RecipeDetail(
      id: "r1",
      title: "Recipe",
      scope: "local",
      status: "draft",
      equipment: <RecipeEquipmentItem>[],
      ingredients: <RecipeIngredientItem>[],
      steps: <RecipeStep>[
        RecipeStep(
          id: "s1",
          recipeId: "r1",
          bodyText: "Use [[equipment:pan]].",
          stepType: "instruction",
          displayOrder: 0,
        ),
      ],
      stepLinks: <StepLink>[],
    );
    final result = resolveStepTextSegments(recipe, recipe.steps.first);
    final linkSegment = result.segments.where((s) => s.isLink).first;
    expect(linkSegment.text, "pan");
    expect(linkSegment.link, isNull);
  });
}

