import "package:flutter_test/flutter_test.dart";
import "package:genesis_mobile/data/models/recipe_models.dart";
import "package:genesis_mobile/data/repositories/recipe_editor_repository_port.dart";
import "package:genesis_mobile/features/recipe_editor/recipe_editor_controller.dart";

class _FakeEditorRepository implements RecipeEditorRepositoryPort {
  RecipeDetail? stored;
  int saveCount = 0;

  @override
  Future<RecipeDetail?> getRecipeById(String recipeId) async {
    if (stored?.id == recipeId) {
      return stored;
    }
    return null;
  }

  @override
  Future<void> upsertRecipeGraph(RecipeDetail recipe, {required String updatedAt}) async {
    stored = recipe;
    saveCount += 1;
  }
}

void main() {
  test("create edit and save persists equipment ingredient step link timer", () async {
    final _FakeEditorRepository repo = _FakeEditorRepository();
    final RecipeEditorController controller = RecipeEditorController(repo);

    await controller.createNew();
    controller.updateMetadata(title: "Pasta", status: "draft");
    controller.addEquipment(name: "Pot");
    controller.addIngredient(rawText: "1 lb pasta", ingredientName: "pasta");
    controller.addStep(title: "Boil", bodyText: "Boil [[ingredient:pasta]]", stepType: "instruction");

    final String stepId = controller.recipe!.steps.first.id;
    final String ingredientId = controller.recipe!.ingredients.first.id;
    controller.addOrUpdateStepLink(
      stepId: stepId,
      targetType: "ingredient",
      targetId: ingredientId,
      tokenKey: "pasta",
    );
    controller.addTimer(stepId: stepId, label: "Boil timer", durationSeconds: 600, autoStart: true);

    final bool saved = await controller.save();
    expect(saved, isTrue);
    expect(repo.saveCount, 1);
    expect(repo.stored!.title, "Pasta");
    expect(repo.stored!.equipment.length, 1);
    expect(repo.stored!.ingredients.length, 1);
    expect(repo.stored!.steps.length, 1);
    expect(repo.stored!.stepLinks.length, 1);
    expect(repo.stored!.steps.first.timers.length, 1);
  });

  test("ingredient quick line stores raw text without structured fields", () async {
    final _FakeEditorRepository repo = _FakeEditorRepository();
    final RecipeEditorController controller = RecipeEditorController(repo);
    await controller.createNew();
    controller.addIngredient(rawText: "2 cups flour");
    expect(controller.recipe!.ingredients.length, 1);
    expect(controller.recipe!.ingredients.first.rawText, "2 cups flour");
    expect(controller.recipe!.ingredients.first.quantityValue, isNull);
    expect(controller.recipe!.ingredients.first.unit, isNull);
    expect(controller.recipe!.ingredients.first.ingredientName, isNull);
  });

  test("bundled recipe requires duplicate before save", () async {
    final _FakeEditorRepository repo = _FakeEditorRepository()
      ..stored = const RecipeDetail(
        id: "bundled-1",
        title: "Bundled",
        scope: "bundled",
        status: "published",
        equipment: <RecipeEquipmentItem>[],
        ingredients: <RecipeIngredientItem>[],
        steps: <RecipeStep>[],
      );
    final RecipeEditorController controller = RecipeEditorController(repo);
    await controller.load("bundled-1");

    final bool blocked = await controller.save();
    expect(blocked, isFalse);

    await controller.duplicateAsLocal();
    controller.updateMetadata(title: "Forked bundled", status: "draft");
    final bool saved = await controller.save();
    expect(saved, isTrue);
    expect(repo.stored!.scope, "local");
  });
}
