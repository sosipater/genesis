import "package:flutter_test/flutter_test.dart";
import "package:genesis_mobile/data/models/recipe_models.dart";
import "package:genesis_mobile/data/repositories/recipe_repository.dart";
import "package:genesis_mobile/features/notifications/local_notification_service.dart";
import "package:genesis_mobile/features/notifications/meal_reminder_service.dart";
import "package:genesis_mobile/features/notifications/notification_preferences_repository.dart";

class _FakeRecipeRepository extends Fake implements RecipeRepository {
  final Map<String, List<ReminderNotification>> byReference = <String, List<ReminderNotification>>{};

  @override
  Future<void> upsertReminderNotification(ReminderNotification reminder) async {
    final String key = "${reminder.referenceType}:${reminder.referenceId}";
    byReference.putIfAbsent(key, () => <ReminderNotification>[]).add(reminder);
  }

  @override
  Future<List<ReminderNotification>> listReminderNotificationsForReference(String referenceType, String referenceId) async {
    return List<ReminderNotification>.from(byReference["$referenceType:$referenceId"] ?? <ReminderNotification>[]);
  }

  @override
  Future<void> deleteReminderNotification(String id, String deletedAtUtc) async {
    for (final List<ReminderNotification> list in byReference.values) {
      list.removeWhere((ReminderNotification item) => item.id == id);
    }
  }
}

class _FakeNotificationService extends LocalNotificationService {
  final List<LocalNotificationRequest> scheduled = <LocalNotificationRequest>[];
  final List<int> cancelled = <int>[];
  final List<int> shown = <int>[];

  @override
  Future<void> initialize() async {}

  @override
  Future<void> requestPermissionsIfNeeded() async {}

  @override
  Future<void> schedule(LocalNotificationRequest request) async {
    scheduled.add(request);
  }

  @override
  Future<void> cancel(int id) async {
    cancelled.add(id);
  }

  @override
  Future<void> showNow({
    required int id,
    required String title,
    required String body,
    required Map<String, dynamic> payload,
  }) async {
    shown.add(id);
  }
}

class _FakePrefsRepository extends NotificationPreferencesRepository {
  NotificationPreferences value = const NotificationPreferences(
    notificationsEnabled: true,
    defaultMealReminderEnabled: true,
    defaultPreReminderMinutes: 15,
    defaultStartCookingPrompt: false,
  );

  @override
  Future<NotificationPreferences> load() async => value;

  @override
  Future<void> setNotificationsEnabled(bool enabled) async {
    value = NotificationPreferences(
      notificationsEnabled: enabled,
      defaultMealReminderEnabled: value.defaultMealReminderEnabled,
      defaultPreReminderMinutes: value.defaultPreReminderMinutes,
      defaultStartCookingPrompt: value.defaultStartCookingPrompt,
    );
  }
}

void main() {
  test("schedules meal reminder and pre-reminder for enabled item", () async {
    final _FakeRecipeRepository repository = _FakeRecipeRepository();
    final _FakeNotificationService notifications = _FakeNotificationService();
    final _FakePrefsRepository prefs = _FakePrefsRepository();
    final MealReminderService service = MealReminderService(repository, notifications, prefs);
    const MealPlanItem item = MealPlanItem(
      id: "item-1",
      mealPlanId: "plan-1",
      recipeId: "recipe-1",
      plannedDate: "2026-04-20",
      mealSlot: "dinner",
      reminderEnabled: true,
      preReminderMinutes: 15,
    );

    await service.syncMealPlanItemReminder(item, "Soup");
    expect(notifications.scheduled.length, 2);
    final List<ReminderNotification> stored =
        await repository.listReminderNotificationsForReference("meal_plan_item", "item-1");
    expect(stored.length, 2);
  });

  test("cancels existing reminders when item reminder disabled", () async {
    final _FakeRecipeRepository repository = _FakeRecipeRepository();
    final _FakeNotificationService notifications = _FakeNotificationService();
    final _FakePrefsRepository prefs = _FakePrefsRepository();
    final MealReminderService service = MealReminderService(repository, notifications, prefs);
    const MealPlanItem enabled = MealPlanItem(
      id: "item-2",
      mealPlanId: "plan-1",
      recipeId: "recipe-1",
      plannedDate: "2026-04-20",
      mealSlot: "dinner",
      reminderEnabled: true,
    );
    const MealPlanItem disabled = MealPlanItem(
      id: "item-2",
      mealPlanId: "plan-1",
      recipeId: "recipe-1",
      plannedDate: "2026-04-20",
      mealSlot: "dinner",
      reminderEnabled: false,
    );

    await service.syncMealPlanItemReminder(enabled, "Soup");
    await service.syncMealPlanItemReminder(disabled, "Soup");
    final List<ReminderNotification> stored =
        await repository.listReminderNotificationsForReference("meal_plan_item", "item-2");
    expect(stored, isEmpty);
    expect(notifications.cancelled, isNotEmpty);
  });
}
