import "package:flutter_test/flutter_test.dart";
import "package:recipe_forge_mobile/data/models/recipe_models.dart";
import "package:recipe_forge_mobile/data/repositories/recipe_repository.dart";
import "package:recipe_forge_mobile/features/home/home_service.dart";

class _FakeHomeRepository extends Fake implements RecipeRepository {
  List<RecipeSummary> recipes = const <RecipeSummary>[];
  List<MealPlanSummary> mealPlans = const <MealPlanSummary>[];
  Map<String, List<MealPlanItem>> itemsByPlan = <String, List<MealPlanItem>>{};
  List<GroceryListSummary> groceryLists = const <GroceryListSummary>[];
  List<RecipeSummary> workingSet = const <RecipeSummary>[];
  List<RecipeSummary> recentOpened = const <RecipeSummary>[];
  String? recentRecipeId;

  @override
  Future<List<RecipeSummary>> listRecipes() async => recipes;

  @override
  Future<List<MealPlanSummary>> listMealPlans() async => mealPlans;

  @override
  Future<List<MealPlanItem>> listMealPlanItems(String mealPlanId) async => itemsByPlan[mealPlanId] ?? const <MealPlanItem>[];

  @override
  Future<String?> getMostRecentRecipeId() async => recentRecipeId;

  @override
  Future<List<GroceryListSummary>> listGroceryLists() async => groceryLists;

  @override
  Future<List<RecipeSummary>> listWorkingSetRecipes() async => workingSet;

  @override
  Future<List<RecipeSummary>> listRecentOpenedRecipes({int limit = 12}) async => recentOpened.take(limit).toList();
}

void main() {
  test("home snapshot groups today and week deterministically", () async {
    final _FakeHomeRepository repo = _FakeHomeRepository()
      ..recipes = const <RecipeSummary>[
        RecipeSummary(id: "r1", title: "Soup", scope: "local", status: "draft", isFavorite: true),
        RecipeSummary(id: "r2", title: "Toast", scope: "local", status: "draft"),
      ]
      ..mealPlans = const <MealPlanSummary>[
        MealPlanSummary(id: "p1", name: "Week Plan"),
      ]
      ..itemsByPlan = <String, List<MealPlanItem>>{
        "p1": const <MealPlanItem>[
          MealPlanItem(id: "i1", mealPlanId: "p1", recipeId: "r1", plannedDate: "2026-04-15", mealSlot: "dinner", sortOrder: 2),
          MealPlanItem(id: "i2", mealPlanId: "p1", recipeId: "r2", plannedDate: "2026-04-15", mealSlot: "lunch", sortOrder: 1),
          MealPlanItem(id: "i3", mealPlanId: "p1", recipeId: "r1", plannedDate: "2026-04-16", mealSlot: "breakfast", sortOrder: 0),
        ],
      }
      ..recentRecipeId = "r2"
      ..groceryLists = const <GroceryListSummary>[GroceryListSummary(id: "g1", name: "Latest", generatedAt: "2026-04-15T10:00:00Z")]
      ..workingSet = const <RecipeSummary>[RecipeSummary(id: "r1", title: "Soup", scope: "local", status: "draft")]
      ..recentOpened = const <RecipeSummary>[RecipeSummary(id: "r2", title: "Toast", scope: "local", status: "draft")];

    final HomeService service = HomeService(repo);
    final HomeSnapshot snapshot = await service.loadSnapshot(now: DateTime(2026, 4, 15));
    expect(snapshot.todayMeals.length, 2);
    expect(snapshot.todayMeals.first.recipe.id, "r2");
    expect(snapshot.weekByDate.keys.first, "2026-04-15");
    expect(snapshot.quickResume.recentRecipe?.id, "r2");
    expect(snapshot.quickResume.latestGroceryList?.id, "g1");
  });

  test("home snapshot handles empty state calmly", () async {
    final HomeService service = HomeService(_FakeHomeRepository());
    final HomeSnapshot snapshot = await service.loadSnapshot(now: DateTime(2026, 4, 15));
    expect(snapshot.todayMeals, isEmpty);
    expect(snapshot.weekMeals, isEmpty);
    expect(snapshot.quickResume.recentRecipe, isNull);
    expect(snapshot.quickResume.latestGroceryList, isNull);
    expect(snapshot.looksLikeFirstVisit, isTrue);
  });

  test("home snapshot is not first-visit when something is on the calendar", () async {
    final _FakeHomeRepository repo = _FakeHomeRepository()
      ..recipes = const <RecipeSummary>[
        RecipeSummary(id: "r1", title: "Soup", scope: "local", status: "draft"),
      ]
      ..mealPlans = const <MealPlanSummary>[MealPlanSummary(id: "p1", name: "Plan")]
      ..itemsByPlan = <String, List<MealPlanItem>>{
        "p1": const <MealPlanItem>[
          MealPlanItem(id: "i1", mealPlanId: "p1", recipeId: "r1", plannedDate: "2026-04-15", mealSlot: "dinner", sortOrder: 0),
        ],
      };
    final HomeSnapshot snapshot = await HomeService(repo).loadSnapshot(now: DateTime(2026, 4, 15));
    expect(snapshot.looksLikeFirstVisit, isFalse);
  });
}
