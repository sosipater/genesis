import "package:flutter_test/flutter_test.dart";
import "package:recipe_forge_mobile/data/models/recipe_models.dart";
import "package:recipe_forge_mobile/features/recipe_editor/recipe_editor_service.dart";

void main() {
  test("duplicate bundled recipe produces local editable clone with remapped ids", () {
    final RecipeEditorService service = RecipeEditorService();
    const RecipeDetail bundled = RecipeDetail(
      id: "recipe-b",
      title: "Bundled",
      scope: "bundled",
      status: "published",
      equipment: <RecipeEquipmentItem>[
        RecipeEquipmentItem(
          id: "eq-1",
          recipeId: "recipe-b",
          name: "Pan",
          isRequired: true,
          displayOrder: 0,
        ),
      ],
      ingredients: <RecipeIngredientItem>[
        RecipeIngredientItem(
          id: "ing-1",
          recipeId: "recipe-b",
          rawText: "2 eggs",
          ingredientName: "Eggs",
          isOptional: false,
          displayOrder: 0,
        ),
      ],
      steps: <RecipeStep>[
        RecipeStep(
          id: "step-1",
          recipeId: "recipe-b",
          bodyText: "Crack [[ingredient:eggs]] in [[equipment:pan]].",
          stepType: "instruction",
          displayOrder: 0,
          timers: <StepTimer>[
            StepTimer(
              id: "timer-1",
              stepId: "step-1",
              label: "Cook",
              durationSeconds: 60,
              autoStart: false,
              alertSoundKey: "ding",
            ),
          ],
        ),
      ],
      stepLinks: <StepLink>[
        StepLink(
          id: "link-1",
          stepId: "step-1",
          targetType: "ingredient",
          targetId: "ing-1",
          tokenKey: "eggs",
          labelSnapshot: "Eggs",
        ),
      ],
    );

    final RecipeDetail clone = service.duplicateBundledAsLocal(bundled);
    expect(clone.scope, "local");
    expect(clone.id, isNot(bundled.id));
    expect(clone.ingredients.first.id, isNot("ing-1"));
    expect(clone.steps.first.id, isNot("step-1"));
    expect(clone.stepLinks.first.targetId, clone.ingredients.first.id);
    expect(clone.steps.first.timers.first.alertSoundKey, "ding");
  });

  test("link token sync updates and removes step body markers", () {
    final RecipeEditorService service = RecipeEditorService();
    const String body = "Use [[ingredient:salt]] now";
    final String renamed = service.syncBodyForLinkToken(
      bodyText: body,
      oldTokenKey: "salt",
      tokenKey: "kosher_salt",
      targetType: "ingredient",
    );
    expect(renamed.contains("[[ingredient:kosher_salt]]"), isTrue);

    final String removed = service.removeLinkTokenFromBody(
      bodyText: renamed,
      targetType: "ingredient",
      tokenKey: "kosher_salt",
    );
    expect(removed.contains("[[ingredient:kosher_salt]]"), isFalse);
  });
}
