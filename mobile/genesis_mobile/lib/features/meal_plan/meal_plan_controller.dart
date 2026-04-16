import "package:flutter/foundation.dart";
import "package:uuid/uuid.dart";

import "../../data/models/recipe_models.dart";
import "../../data/repositories/recipe_repository.dart";
import "../notifications/meal_reminder_service.dart";
import "../notifications/notification_preferences_repository.dart";
import "meal_plan_service.dart";

class MealPlanController extends ChangeNotifier {
  final RecipeRepository _repository;
  final MealPlanService _service;
  final MealReminderService _mealReminderService;
  final Uuid _uuid;

  MealPlanController(this._repository, this._service, this._mealReminderService, {Uuid? uuid})
      : _uuid = uuid ?? const Uuid();

  List<MealPlanSummary> mealPlans = <MealPlanSummary>[];
  List<MealPlanItem> mealPlanItems = <MealPlanItem>[];
  List<GroceryListSummary> groceryLists = <GroceryListSummary>[];
  List<GroceryListItem> groceryItems = <GroceryListItem>[];
  List<RecipeSummary> availableRecipes = <RecipeSummary>[];
  String? selectedMealPlanId;
  String? selectedGroceryListId;
  String? _lastDeletedMealPlanId;
  DateTime selectedWeekStart = _weekStartFor(DateTime.now());
  bool loading = false;
  String? error;
  /// Populated after grocery generation; cleared on next successful run with no notes.
  List<String> lastGroceryWarnings = <String>[];
  NotificationPreferences notificationPreferences = const NotificationPreferences(
    notificationsEnabled: false,
    defaultMealReminderEnabled: false,
    defaultPreReminderMinutes: null,
    defaultStartCookingPrompt: false,
  );

  Future<void> load() async {
    loading = true;
    error = null;
    notifyListeners();
    try {
      mealPlans = await _repository.listMealPlans();
      groceryLists = await _repository.listGroceryLists();
      availableRecipes = await _repository.listRecipes();
      if (selectedMealPlanId != null) {
        mealPlanItems = await _repository.listMealPlanItems(selectedMealPlanId!);
      }
      notificationPreferences = await _mealReminderService.loadPreferences();
      if (selectedGroceryListId != null) {
        groceryItems = await _repository.listGroceryListItems(selectedGroceryListId!);
      }
    } catch (e) {
      error = e.toString();
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<void> createMealPlan(String name) async {
    await _service.createMealPlan(name);
    await load();
  }

  Future<void> selectMealPlan(String mealPlanId) async {
    selectedMealPlanId = mealPlanId;
    mealPlanItems = await _repository.listMealPlanItems(mealPlanId);
    notifyListeners();
  }

  Future<void> addRecipeToSelectedMealPlan(
    String recipeId, {
    double? servingsOverride,
    bool? reminderEnabled,
    int? preReminderMinutes,
    bool? startCookingPrompt,
  }) async {
    if (selectedMealPlanId == null) return;
    await _service.addRecipeToMealPlan(
      mealPlanId: selectedMealPlanId!,
      recipeId: recipeId,
      servingsOverride: servingsOverride,
      reminderEnabled: reminderEnabled ?? notificationPreferences.defaultMealReminderEnabled,
      preReminderMinutes: preReminderMinutes ?? notificationPreferences.defaultPreReminderMinutes,
      startCookingPrompt: startCookingPrompt ?? notificationPreferences.defaultStartCookingPrompt,
    );
    mealPlanItems = await _repository.listMealPlanItems(selectedMealPlanId!);
    await _resyncReminderForLatestMealItem(recipeId);
    notifyListeners();
  }

  Future<void> addRecipeToSelectedMealPlanScheduled({
    required String recipeId,
    required String plannedDate,
    required String mealSlot,
    String? slotLabel,
    double? servingsOverride,
    bool? reminderEnabled,
    int? preReminderMinutes,
    bool? startCookingPrompt,
  }) async {
    if (selectedMealPlanId == null) return;
    await _service.addRecipeToMealPlan(
      mealPlanId: selectedMealPlanId!,
      recipeId: recipeId,
      servingsOverride: servingsOverride,
      plannedDate: plannedDate,
      mealSlot: mealSlot,
      slotLabel: slotLabel,
      reminderEnabled: reminderEnabled ?? notificationPreferences.defaultMealReminderEnabled,
      preReminderMinutes: preReminderMinutes ?? notificationPreferences.defaultPreReminderMinutes,
      startCookingPrompt: startCookingPrompt ?? notificationPreferences.defaultStartCookingPrompt,
    );
    mealPlanItems = await _repository.listMealPlanItems(selectedMealPlanId!);
    await _resyncReminderForLatestMealItem(recipeId);
    notifyListeners();
  }

  Future<void> removeMealPlanItem(String itemId) async {
    await _repository.removeMealPlanItem(itemId, DateTime.now().toUtc().toIso8601String());
    await _mealReminderService.cancelMealPlanItemReminder(itemId);
    if (selectedMealPlanId != null) {
      mealPlanItems = await _repository.listMealPlanItems(selectedMealPlanId!);
    }
    notifyListeners();
  }

  Future<List<String>> generateGroceryForSelectedMealPlan() async {
    if (selectedMealPlanId == null) return <String>[];
    final GroceryListGenerationResult result = await _service.generateGroceryListFromMealPlan(selectedMealPlanId!);
    selectedGroceryListId = result.groceryListId;
    groceryLists = await _repository.listGroceryLists();
    groceryItems = await _repository.listGroceryListItems(result.groceryListId);
    lastGroceryWarnings = result.warnings;
    notifyListeners();
    return result.warnings;
  }

  Future<List<String>> generateGroceryForCurrentWeek() async {
    if (selectedMealPlanId == null) return <String>[];
    final GroceryListGenerationResult result =
        await _service.generateWeeklyGroceryList(selectedMealPlanId!, selectedWeekStart);
    selectedGroceryListId = result.groceryListId;
    groceryLists = await _repository.listGroceryLists();
    groceryItems = await _repository.listGroceryListItems(result.groceryListId);
    lastGroceryWarnings = result.warnings;
    notifyListeners();
    return result.warnings;
  }

  Future<void> deleteSelectedMealPlan() async {
    if (selectedMealPlanId == null) {
      return;
    }
    for (final MealPlanItem item in mealPlanItems) {
      await _mealReminderService.cancelMealPlanItemReminder(item.id);
    }
    _lastDeletedMealPlanId = selectedMealPlanId;
    await _repository.deleteMealPlan(selectedMealPlanId!, DateTime.now().toUtc().toIso8601String());
    selectedMealPlanId = null;
    mealPlanItems = <MealPlanItem>[];
    await load();
  }

  Future<void> undoDeleteMealPlan() async {
    if (_lastDeletedMealPlanId == null) {
      return;
    }
    await _repository.restoreMealPlan(_lastDeletedMealPlanId!, DateTime.now().toUtc().toIso8601String());
    final String restoredId = _lastDeletedMealPlanId!;
    _lastDeletedMealPlanId = null;
    await load();
    await selectMealPlan(restoredId);
  }

  Future<List<String>> generateGroceryForDateRange(String startDate, String endDate) async {
    if (selectedMealPlanId == null) return <String>[];
    final GroceryListGenerationResult result = await _service.generateGroceryListFromMealPlan(
      selectedMealPlanId!,
      startDate: startDate,
      endDate: endDate,
    );
    selectedGroceryListId = result.groceryListId;
    groceryLists = await _repository.listGroceryLists();
    groceryItems = await _repository.listGroceryListItems(result.groceryListId);
    lastGroceryWarnings = result.warnings;
    notifyListeners();
    return result.warnings;
  }

  Future<List<String>> regenerateGroceryForSelectedMealPlan() async {
    // Explicitly creates a new snapshot and keeps prior edited list intact.
    return generateGroceryForSelectedMealPlan();
  }

  Future<void> selectGroceryList(String groceryListId) async {
    selectedGroceryListId = groceryListId;
    groceryItems = await _repository.listGroceryListItems(groceryListId);
    notifyListeners();
  }

  Future<void> updateMealItemSchedule({
    required String itemId,
    String? plannedDate,
    String? mealSlot,
    String? slotLabel,
    int? sortOrder,
    bool? reminderEnabled,
    int? preReminderMinutes,
    bool? startCookingPrompt,
  }) async {
    await _repository.updateMealPlanItemSchedule(
      itemId: itemId,
      plannedDate: plannedDate,
      mealSlot: mealSlot,
      slotLabel: slotLabel,
      sortOrder: sortOrder,
      reminderEnabled: reminderEnabled,
      preReminderMinutes: preReminderMinutes,
      startCookingPrompt: startCookingPrompt,
      updatedAtUtc: DateTime.now().toUtc().toIso8601String(),
    );
    if (selectedMealPlanId != null) {
      mealPlanItems = await _repository.listMealPlanItems(selectedMealPlanId!);
      final MealPlanItem? item = _mealPlanItemById(itemId);
      if (item != null) {
        await _resyncReminder(item);
      }
    }
    notifyListeners();
  }

  Future<void> setNotificationsEnabled(bool enabled) async {
    await _mealReminderService.setGlobalEnabled(enabled);
    notificationPreferences = await _mealReminderService.loadPreferences();
    if (selectedMealPlanId != null) {
      await _resyncAllVisibleReminders();
    }
    notifyListeners();
  }

  Future<void> updateReminderDefaults({
    bool? mealReminderEnabled,
    int? preReminderMinutes,
    bool? startCookingPrompt,
  }) async {
    await _mealReminderService.updateDefaults(
      mealReminderEnabled: mealReminderEnabled,
      preReminderMinutes: preReminderMinutes,
      startCookingPrompt: startCookingPrompt,
    );
    notificationPreferences = await _mealReminderService.loadPreferences();
    notifyListeners();
  }

  Future<void> markMealItemCooked(String recipeId) async {
    await _repository.markRecipeCooked(recipeId, DateTime.now().toUtc().toIso8601String());
    notifyListeners();
  }

  void shiftWeek(int offsetWeeks) {
    selectedWeekStart = selectedWeekStart.add(Duration(days: 7 * offsetWeeks));
    notifyListeners();
  }

  List<DateTime> getSelectedWeekDays() {
    return List<DateTime>.generate(7, (int index) => selectedWeekStart.add(Duration(days: index)));
  }

  List<MealPlanItem> plannedForDate(String date) {
    final List<MealPlanItem> items = mealPlanItems.where((MealPlanItem item) => item.plannedDate == date).toList();
    items.sort((MealPlanItem a, MealPlanItem b) {
      final int bySlot = _slotOrder(a.mealSlot).compareTo(_slotOrder(b.mealSlot));
      if (bySlot != 0) {
        return bySlot;
      }
      return a.sortOrder.compareTo(b.sortOrder);
    });
    return items;
  }

  List<MealPlanItem> plannedForToday() {
    return plannedForDate(_dateOnly(DateTime.now()));
  }

  List<MealPlanItem> plannedForSelectedWeek() {
    final String start = _dateOnly(selectedWeekStart);
    final String end = _dateOnly(selectedWeekStart.add(const Duration(days: 6)));
    final List<MealPlanItem> items = mealPlanItems
        .where((MealPlanItem item) =>
            item.plannedDate != null &&
            item.plannedDate!.compareTo(start) >= 0 &&
            item.plannedDate!.compareTo(end) <= 0)
        .toList();
    items.sort((MealPlanItem a, MealPlanItem b) {
      final int byDate = (a.plannedDate ?? "").compareTo(b.plannedDate ?? "");
      if (byDate != 0) return byDate;
      final int bySlot = _slotOrder(a.mealSlot).compareTo(_slotOrder(b.mealSlot));
      if (bySlot != 0) return bySlot;
      return a.sortOrder.compareTo(b.sortOrder);
    });
    return items;
  }

  Future<void> toggleGroceryItem(String itemId, bool checked) async {
    await _repository.toggleGroceryListItem(itemId, checked, DateTime.now().toUtc().toIso8601String());
    if (selectedGroceryListId != null) {
      groceryItems = await _repository.listGroceryListItems(selectedGroceryListId!);
    }
    notifyListeners();
  }

  Future<void> addManualGroceryItem({
    required String name,
    double? quantityValue,
    String? unit,
  }) async {
    if (selectedGroceryListId == null) return;
    await _repository.addManualGroceryItem(
      groceryListId: selectedGroceryListId!,
      id: _uuid.v4(),
      name: name,
      quantityValue: quantityValue,
      unit: unit,
      updatedAtUtc: DateTime.now().toUtc().toIso8601String(),
    );
    groceryItems = await _repository.listGroceryListItems(selectedGroceryListId!);
    notifyListeners();
  }

  Future<void> updateGroceryItem({
    required String itemId,
    required String name,
    double? quantityValue,
    String? unit,
  }) async {
    await _repository.updateGroceryListItem(
      id: itemId,
      name: name,
      quantityValue: quantityValue,
      unit: unit,
      updatedAtUtc: DateTime.now().toUtc().toIso8601String(),
    );
    if (selectedGroceryListId != null) {
      groceryItems = await _repository.listGroceryListItems(selectedGroceryListId!);
    }
    notifyListeners();
  }

  Future<void> deleteGroceryItem(String itemId) async {
    await _repository.deleteGroceryListItem(itemId, DateTime.now().toUtc().toIso8601String());
    if (selectedGroceryListId != null) {
      groceryItems = await _repository.listGroceryListItems(selectedGroceryListId!);
    }
    notifyListeners();
  }

  Future<void> moveGroceryItem(int index, int direction) async {
    if (selectedGroceryListId == null) return;
    final int newIndex = index + direction;
    if (newIndex < 0 || newIndex >= groceryItems.length) return;
    final List<GroceryListItem> reordered = List<GroceryListItem>.from(groceryItems);
    final GroceryListItem item = reordered.removeAt(index);
    reordered.insert(newIndex, item);
    await _repository.reorderGroceryListItems(
      selectedGroceryListId!,
      reordered.map((GroceryListItem value) => value.id).toList(),
      DateTime.now().toUtc().toIso8601String(),
    );
    groceryItems = await _repository.listGroceryListItems(selectedGroceryListId!);
    notifyListeners();
  }

  String newId() => _uuid.v4();

  static DateTime _weekStartFor(DateTime day) {
    final DateTime local = DateTime(day.year, day.month, day.day);
    final int delta = (local.weekday - DateTime.monday) % 7;
    return local.subtract(Duration(days: delta));
  }

  static String _dateOnly(DateTime value) {
    return "${value.year.toString().padLeft(4, "0")}-${value.month.toString().padLeft(2, "0")}-${value.day.toString().padLeft(2, "0")}";
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

  Future<void> _resyncReminderForLatestMealItem(String recipeId) async {
    MealPlanItem? latest;
    for (final MealPlanItem item in mealPlanItems) {
      if (item.recipeId == recipeId) {
        latest = item;
      }
    }
    if (latest != null) {
      await _resyncReminder(latest);
    }
  }

  Future<void> _resyncReminder(MealPlanItem item) async {
    final RecipeSummary? recipe = availableRecipes.cast<RecipeSummary?>().firstWhere(
          (RecipeSummary? candidate) => candidate?.id == item.recipeId,
          orElse: () => null,
        );
    await _mealReminderService.syncMealPlanItemReminder(item, recipe?.title ?? "Scheduled meal");
  }

  Future<void> _resyncAllVisibleReminders() async {
    for (final MealPlanItem item in mealPlanItems) {
      await _resyncReminder(item);
    }
  }

  MealPlanItem? _mealPlanItemById(String id) {
    for (final MealPlanItem item in mealPlanItems) {
      if (item.id == id) {
        return item;
      }
    }
    return null;
  }
}
