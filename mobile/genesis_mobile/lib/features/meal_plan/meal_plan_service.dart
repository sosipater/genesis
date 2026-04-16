import "package:uuid/uuid.dart";

import "../../data/models/recipe_models.dart";
import "../../data/repositories/recipe_repository.dart";

class MealPlanService {
  final RecipeRepository _repository;
  final Uuid _uuid;

  MealPlanService(this._repository, {Uuid? uuid}) : _uuid = uuid ?? const Uuid();

  Future<String> createMealPlan(String name, {String? startDate, String? endDate, String? notes}) {
    final String now = DateTime.now().toUtc().toIso8601String();
    return _repository.createMealPlan(
      id: _uuid.v4(),
      name: name,
      startDate: startDate,
      endDate: endDate,
      notes: notes,
      updatedAtUtc: now,
    );
  }

  Future<String> addRecipeToMealPlan({
    required String mealPlanId,
    required String recipeId,
    double? servingsOverride,
    String? notes,
    String? plannedDate,
    String? mealSlot,
    String? slotLabel,
    int sortOrder = 0,
    bool reminderEnabled = false,
    int? preReminderMinutes,
    bool startCookingPrompt = false,
  }) {
    final String now = DateTime.now().toUtc().toIso8601String();
    return _repository.addMealPlanItem(
      id: _uuid.v4(),
      mealPlanId: mealPlanId,
      recipeId: recipeId,
      servingsOverride: servingsOverride,
      notes: notes,
      plannedDate: plannedDate,
      mealSlot: mealSlot,
      slotLabel: slotLabel,
      sortOrder: sortOrder,
      reminderEnabled: reminderEnabled,
      preReminderMinutes: preReminderMinutes,
      startCookingPrompt: startCookingPrompt,
      updatedAtUtc: now,
    );
  }

  Future<String> generateGroceryListFromMealPlan(
    String mealPlanId, {
    String? startDate,
    String? endDate,
  }) async {
    final List<MealPlanItem> allItems = await _repository.listMealPlanItems(mealPlanId);
    final List<MealPlanItem> mealItems = allItems.where((MealPlanItem item) {
      if (startDate == null && endDate == null) {
        return true;
      }
      if (item.plannedDate == null) {
        return false;
      }
      if (startDate != null && item.plannedDate!.compareTo(startDate) < 0) {
        return false;
      }
      if (endDate != null && item.plannedDate!.compareTo(endDate) > 0) {
        return false;
      }
      return true;
    }).toList();
    final Map<String, _AggregatedItem> grouped = <String, _AggregatedItem>{};

    for (final MealPlanItem mealItem in mealItems) {
      final RecipeDetail? recipe = await _repository.getRecipeById(mealItem.recipeId);
      if (recipe == null) {
        continue;
      }
      final double factor = _factor(recipeServings: recipe.servings, override: mealItem.servingsOverride);
      for (final RecipeIngredientItem ingredient in recipe.ingredients) {
        final String normalizedName = (ingredient.ingredientName ?? ingredient.rawText).trim().toLowerCase();
        final String displayName = ingredient.ingredientName ?? ingredient.rawText;
        final String? normalizedUnit = ingredient.unit?.trim().toLowerCase();
        final String key = "$normalizedName::${normalizedUnit ?? "_"}";
        final double? scaledQuantity = ingredient.quantityValue == null ? null : ingredient.quantityValue! * factor;
        final _AggregatedItem? existing = grouped[key];
        if (existing == null) {
          grouped[key] = _AggregatedItem(
            name: displayName,
            quantityValue: scaledQuantity,
            unit: ingredient.unit,
            sourceRecipeIds: <String>{recipe.id},
            generatedGroupKey: key,
          );
        } else {
          existing.sourceRecipeIds.add(recipe.id);
          if (existing.quantityValue != null && scaledQuantity != null) {
            existing.quantityValue = double.parse((existing.quantityValue! + scaledQuantity).toStringAsFixed(3));
          } else {
            existing.quantityValue = null;
          }
        }
      }
    }

    final String now = DateTime.now().toUtc().toIso8601String();
    final String groceryListId = await _repository.createGroceryList(
      id: _uuid.v4(),
      mealPlanId: mealPlanId,
      name: _buildGroceryName(now.substring(0, 10), startDate: startDate, endDate: endDate),
      generatedAtUtc: now,
    );
    final List<GroceryListItem> items = grouped.values
        .map(
          (_AggregatedItem item) => GroceryListItem(
            id: _uuid.v4(),
            groceryListId: groceryListId,
            name: item.name,
            quantityValue: item.quantityValue,
            unit: item.unit,
            checked: false,
            sourceRecipeIds: item.sourceRecipeIds.toList()..sort(),
            sourceType: "generated",
            generatedGroupKey: item.generatedGroupKey,
            wasUserModified: false,
          ),
        )
        .toList()
      ..sort((GroceryListItem a, GroceryListItem b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()));
    await _repository.replaceGroceryListItems(groceryListId, items, now);
    return groceryListId;
  }

  Future<String> generateWeeklyGroceryList(String mealPlanId, DateTime weekStartLocal) {
    final DateTime weekStart = DateTime(weekStartLocal.year, weekStartLocal.month, weekStartLocal.day);
    final DateTime weekEnd = weekStart.add(const Duration(days: 6));
    return generateGroceryListFromMealPlan(
      mealPlanId,
      startDate: _asDate(weekStart),
      endDate: _asDate(weekEnd),
    );
  }

  double _factor({required double? recipeServings, double? override}) {
    if (override == null || recipeServings == null || recipeServings <= 0) {
      return 1.0;
    }
    if (override <= 0) {
      return 1.0;
    }
    return override / recipeServings;
  }

  String _buildGroceryName(String dayStamp, {String? startDate, String? endDate}) {
    if (startDate == null && endDate == null) {
      return "Grocery $dayStamp";
    }
    final String start = startDate ?? "?";
    final String end = endDate ?? start;
    return "Grocery $start..$end";
  }

  String _asDate(DateTime day) {
    return "${day.year.toString().padLeft(4, "0")}-${day.month.toString().padLeft(2, "0")}-${day.day.toString().padLeft(2, "0")}";
  }
}

class _AggregatedItem {
  final String name;
  double? quantityValue;
  final String? unit;
  final Set<String> sourceRecipeIds;
  final String generatedGroupKey;

  _AggregatedItem({
    required this.name,
    required this.quantityValue,
    required this.unit,
    required this.sourceRecipeIds,
    required this.generatedGroupKey,
  });
}
