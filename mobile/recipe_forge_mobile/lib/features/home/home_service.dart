import "../../data/models/recipe_models.dart";
import "../../data/repositories/recipe_repository.dart";

class HomeMealEntry {
  final String mealPlanId;
  final String mealPlanName;
  final MealPlanItem item;
  final RecipeSummary recipe;
  final String date;

  const HomeMealEntry({
    required this.mealPlanId,
    required this.mealPlanName,
    required this.item,
    required this.recipe,
    required this.date,
  });
}

class HomeQuickResume {
  final RecipeSummary? recentRecipe;
  final GroceryListSummary? latestGroceryList;
  final MealPlanSummary? activeMealPlan;
  final int workingSetCount;

  const HomeQuickResume({
    this.recentRecipe,
    this.latestGroceryList,
    this.activeMealPlan,
    this.workingSetCount = 0,
  });
}

class HomeSnapshot {
  final List<HomeMealEntry> todayMeals;
  final List<HomeMealEntry> weekMeals;
  final Map<String, List<HomeMealEntry>> weekByDate;
  final HomeQuickResume quickResume;
  final List<RecipeSummary> favorites;
  final List<RecipeSummary> recentOpened;

  const HomeSnapshot({
    required this.todayMeals,
    required this.weekMeals,
    required this.weekByDate,
    required this.quickResume,
    required this.favorites,
    required this.recentOpened,
  });

  /// True when the home dashboard has almost nothing to show yet (typical first launch).
  bool get looksLikeFirstVisit =>
      todayMeals.isEmpty &&
      weekByDate.isEmpty &&
      favorites.isEmpty &&
      recentOpened.isEmpty &&
      quickResume.recentRecipe == null &&
      quickResume.activeMealPlan == null &&
      quickResume.latestGroceryList == null &&
      quickResume.workingSetCount == 0;
}

class HomeService {
  final RecipeRepository _repository;

  HomeService(this._repository);

  Future<HomeSnapshot> loadSnapshot({DateTime? now}) async {
    final DateTime current = now ?? DateTime.now();
    final String today = _dateOnly(current);
    final DateTime weekStart = _weekStart(current);
    final DateTime weekEnd = weekStart.add(const Duration(days: 6));
    final String weekStartKey = _dateOnly(weekStart);
    final String weekEndKey = _dateOnly(weekEnd);

    final List<RecipeSummary> recipes = await _repository.listRecipes();
    final Map<String, RecipeSummary> recipesById = <String, RecipeSummary>{for (final RecipeSummary recipe in recipes) recipe.id: recipe};
    final List<MealPlanSummary> mealPlans = await _repository.listMealPlans();
    final List<HomeMealEntry> allScheduled = <HomeMealEntry>[];
    for (final MealPlanSummary mealPlan in mealPlans) {
      final List<MealPlanItem> items = await _repository.listMealPlanItems(mealPlan.id);
      for (final MealPlanItem item in items) {
        final String? plannedDate = item.plannedDate;
        final RecipeSummary? recipe = recipesById[item.recipeId];
        if (plannedDate == null || recipe == null) {
          continue;
        }
        allScheduled.add(
          HomeMealEntry(
            mealPlanId: mealPlan.id,
            mealPlanName: mealPlan.name,
            item: item,
            recipe: recipe,
            date: plannedDate,
          ),
        );
      }
    }

    allScheduled.sort(_compareMealEntry);
    final List<HomeMealEntry> todayMeals = allScheduled.where((HomeMealEntry entry) => entry.date == today).toList();
    final List<HomeMealEntry> weekMeals = allScheduled
        .where((HomeMealEntry entry) => entry.date.compareTo(weekStartKey) >= 0 && entry.date.compareTo(weekEndKey) <= 0)
        .toList();
    final Map<String, List<HomeMealEntry>> weekByDate = <String, List<HomeMealEntry>>{};
    for (final HomeMealEntry entry in weekMeals) {
      weekByDate.putIfAbsent(entry.date, () => <HomeMealEntry>[]).add(entry);
    }
    final List<String> sortedDateKeys = weekByDate.keys.toList()..sort();
    final Map<String, List<HomeMealEntry>> orderedWeekByDate = <String, List<HomeMealEntry>>{
      for (final String day in sortedDateKeys) day: weekByDate[day]!,
    };

    final String? recentRecipeId = await _repository.getMostRecentRecipeId();
    RecipeSummary? recentRecipe;
    if (recentRecipeId != null) {
      recentRecipe = recipesById[recentRecipeId];
    }
    final List<GroceryListSummary> groceryLists = await _repository.listGroceryLists();
    final GroceryListSummary? latestGrocery = groceryLists.isEmpty ? null : groceryLists.first;
    final List<RecipeSummary> workingSet = await _repository.listWorkingSetRecipes();
    final HomeQuickResume quickResume = HomeQuickResume(
      recentRecipe: recentRecipe,
      latestGroceryList: latestGrocery,
      activeMealPlan: mealPlans.isEmpty ? null : mealPlans.first,
      workingSetCount: workingSet.length,
    );

    final List<RecipeSummary> favorites = recipes.where((RecipeSummary recipe) => recipe.isFavorite).toList()
      ..sort((RecipeSummary a, RecipeSummary b) => a.title.toLowerCase().compareTo(b.title.toLowerCase()));
    final List<RecipeSummary> recentOpened = await _repository.listRecentOpenedRecipes(limit: 6);

    return HomeSnapshot(
      todayMeals: todayMeals,
      weekMeals: weekMeals,
      weekByDate: orderedWeekByDate,
      quickResume: quickResume,
      favorites: favorites.take(6).toList(),
      recentOpened: recentOpened,
    );
  }

  int _compareMealEntry(HomeMealEntry a, HomeMealEntry b) {
    final int byDate = a.date.compareTo(b.date);
    if (byDate != 0) {
      return byDate;
    }
    final int bySlot = _slotOrder(a.item.mealSlot).compareTo(_slotOrder(b.item.mealSlot));
    if (bySlot != 0) {
      return bySlot;
    }
    final int bySort = a.item.sortOrder.compareTo(b.item.sortOrder);
    if (bySort != 0) {
      return bySort;
    }
    return a.recipe.title.toLowerCase().compareTo(b.recipe.title.toLowerCase());
  }

  int _slotOrder(String? slot) {
    switch (slot) {
      case "breakfast":
        return 0;
      case "lunch":
        return 1;
      case "dinner":
        return 2;
      case "snack":
        return 3;
      case "custom":
        return 4;
      default:
        return 5;
    }
  }

  DateTime _weekStart(DateTime value) {
    final DateTime local = DateTime(value.year, value.month, value.day);
    final int delta = (local.weekday - DateTime.monday) % 7;
    return local.subtract(Duration(days: delta));
  }

  String _dateOnly(DateTime value) {
    return "${value.year.toString().padLeft(4, "0")}-${value.month.toString().padLeft(2, "0")}-${value.day.toString().padLeft(2, "0")}";
  }
}
