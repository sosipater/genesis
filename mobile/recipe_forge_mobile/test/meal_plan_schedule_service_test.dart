import "package:flutter_test/flutter_test.dart";
import "package:recipe_forge_mobile/data/models/recipe_models.dart";
import "package:recipe_forge_mobile/data/repositories/recipe_repository.dart";
import "package:recipe_forge_mobile/features/meal_plan/meal_plan_service.dart";

class _FakeMealPlanRepository extends Fake implements RecipeRepository {
  final List<MealPlanItem> items;
  final Map<String, RecipeDetail> recipesById;
  String? lastListName;

  _FakeMealPlanRepository({required this.items, required this.recipesById});

  @override
  Future<List<MealPlanItem>> listMealPlanItems(String mealPlanId) async => items;

  @override
  Future<RecipeDetail?> getRecipeById(String recipeId) async => recipesById[recipeId];

  @override
  Future<String> createGroceryList({
    required String id,
    String? mealPlanId,
    required String name,
    required String generatedAtUtc,
  }) async {
    lastListName = name;
    return "grocery-1";
  }

  @override
  Future<void> replaceGroceryListItems(String groceryListId, List<GroceryListItem> items, String updatedAtUtc) async {}
}

void main() {
  test("range grocery includes only scheduled date slice", () async {
    const RecipeDetail recipe = RecipeDetail(
      id: "r1",
      title: "R",
      scope: "local",
      status: "draft",
      equipment: <RecipeEquipmentItem>[],
      ingredients: <RecipeIngredientItem>[
        RecipeIngredientItem(
          id: "i1",
          recipeId: "r1",
          rawText: "salt",
          ingredientName: "salt",
          quantityValue: 1,
          unit: "tsp",
          isOptional: false,
          displayOrder: 0,
        ),
      ],
      steps: <RecipeStep>[],
    );
    final _FakeMealPlanRepository repo = _FakeMealPlanRepository(
      items: const <MealPlanItem>[
        MealPlanItem(id: "a", mealPlanId: "m", recipeId: "r1", plannedDate: "2026-04-21", mealSlot: "dinner"),
        MealPlanItem(id: "b", mealPlanId: "m", recipeId: "r1", plannedDate: "2026-04-29", mealSlot: "dinner"),
      ],
      recipesById: const <String, RecipeDetail>{"r1": recipe},
    );
    final MealPlanService service = MealPlanService(repo);
    await service.generateGroceryListFromMealPlan("m", startDate: "2026-04-20", endDate: "2026-04-22");
    expect(repo.lastListName, "Grocery 2026-04-20..2026-04-22");
  });
}
