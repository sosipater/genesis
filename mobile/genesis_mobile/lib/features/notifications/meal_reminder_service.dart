import "dart:convert";

import "package:uuid/uuid.dart";

import "../../data/models/recipe_models.dart";
import "../../data/repositories/recipe_repository.dart";
import "local_notification_service.dart";
import "notification_preferences_repository.dart";

class MealReminderService {
  final RecipeRepository _repository;
  final LocalNotificationService _notifications;
  final NotificationPreferencesRepository _preferences;
  final Uuid _uuid;

  MealReminderService(
    this._repository,
    this._notifications,
    this._preferences, {
    Uuid? uuid,
  }) : _uuid = uuid ?? const Uuid();

  Future<NotificationPreferences> loadPreferences() => _preferences.load();

  Future<void> setGlobalEnabled(bool enabled) async {
    await _preferences.setNotificationsEnabled(enabled);
    if (enabled) {
      await _notifications.requestPermissionsIfNeeded();
    }
  }

  Future<void> updateDefaults({
    bool? mealReminderEnabled,
    int? preReminderMinutes,
    bool? startCookingPrompt,
  }) async {
    if (mealReminderEnabled != null) {
      await _preferences.setMealDefaultReminderEnabled(mealReminderEnabled);
    }
    await _preferences.setMealDefaultPreReminderMinutes(preReminderMinutes);
    if (startCookingPrompt != null) {
      await _preferences.setDefaultStartCookingPrompt(startCookingPrompt);
    }
  }

  Future<void> syncMealPlanItemReminder(MealPlanItem item, String recipeTitle) async {
    final NotificationPreferences prefs = await _preferences.load();
    final List<ReminderNotification> existing = await _repository.listReminderNotificationsForReference("meal_plan_item", item.id);
    for (final ReminderNotification reminder in existing) {
      await _notifications.cancel(_stableNotificationId(reminder.id));
      await _repository.deleteReminderNotification(reminder.id, DateTime.now().toUtc().toIso8601String());
    }
    if (!prefs.notificationsEnabled || !item.reminderEnabled || item.plannedDate == null || item.mealSlot == null) {
      return;
    }

    final DateTime mealTime = _scheduledMealDateTime(item.plannedDate!, item.mealSlot!);
    await _createAndSchedule(
      id: _uuid.v4(),
      type: "meal_reminder",
      referenceId: item.id,
      scheduledAt: mealTime,
      title: "Meal reminder",
      body: "Time to cook: $recipeTitle",
      payload: <String, dynamic>{
        "type": "meal_reminder",
        "meal_plan_item_id": item.id,
        "recipe_id": item.recipeId,
      },
    );

    final int? preMinutes = item.preReminderMinutes;
    if (preMinutes != null && preMinutes > 0) {
      final DateTime preTime = mealTime.subtract(Duration(minutes: preMinutes));
      if (preTime.isAfter(DateTime.now())) {
        await _createAndSchedule(
          id: _uuid.v4(),
          type: "meal_pre_reminder",
          referenceId: item.id,
          scheduledAt: preTime,
          title: "Upcoming meal",
          body: "$recipeTitle in $preMinutes minutes",
          payload: <String, dynamic>{
            "type": "meal_pre_reminder",
            "meal_plan_item_id": item.id,
            "recipe_id": item.recipeId,
          },
        );
      }
    }

    if (item.startCookingPrompt) {
      final DateTime promptAt = mealTime.subtract(const Duration(minutes: 5));
      if (promptAt.isAfter(DateTime.now())) {
        await _createAndSchedule(
          id: _uuid.v4(),
          type: "start_cooking_prompt",
          referenceId: item.id,
          scheduledAt: promptAt,
          title: "Start cooking soon",
          body: "Open $recipeTitle and start prep",
          payload: <String, dynamic>{
            "type": "start_cooking_prompt",
            "meal_plan_item_id": item.id,
            "recipe_id": item.recipeId,
          },
        );
      }
    }
  }

  Future<void> cancelMealPlanItemReminder(String mealPlanItemId) async {
    final List<ReminderNotification> existing =
        await _repository.listReminderNotificationsForReference("meal_plan_item", mealPlanItemId);
    for (final ReminderNotification reminder in existing) {
      await _notifications.cancel(_stableNotificationId(reminder.id));
      await _repository.deleteReminderNotification(reminder.id, DateTime.now().toUtc().toIso8601String());
    }
  }

  Future<void> notifyTimerCompleted({
    required String timerId,
    required String recipeId,
    required String stepId,
    required String label,
  }) async {
    final NotificationPreferences prefs = await _preferences.load();
    if (!prefs.notificationsEnabled) {
      return;
    }
    await _notifications.showNow(
      id: _stableNotificationId("timer-$timerId"),
      title: "Timer complete",
      body: label,
      payload: <String, dynamic>{
        "type": "timer_complete",
        "timer_id": timerId,
        "recipe_id": recipeId,
        "step_id": stepId,
      },
    );
  }

  Future<void> _createAndSchedule({
    required String id,
    required String type,
    required String referenceId,
    required DateTime scheduledAt,
    required String title,
    required String body,
    required Map<String, dynamic> payload,
  }) async {
    final String nowUtc = DateTime.now().toUtc().toIso8601String();
    await _repository.upsertReminderNotification(
      ReminderNotification(
        id: id,
        type: type,
        referenceType: "meal_plan_item",
        referenceId: referenceId,
        scheduledTimeUtc: scheduledAt.toUtc().toIso8601String(),
        enabled: true,
        payloadJson: jsonEncode(payload),
        updatedAt: nowUtc,
      ),
    );
    await _notifications.schedule(
      LocalNotificationRequest(
        id: _stableNotificationId(id),
        scheduledAtLocal: scheduledAt,
        title: title,
        body: body,
        payload: payload,
      ),
    );
  }

  DateTime _scheduledMealDateTime(String plannedDate, String slot) {
    final List<String> parts = plannedDate.split("-");
    final int year = int.parse(parts[0]);
    final int month = int.parse(parts[1]);
    final int day = int.parse(parts[2]);
    final _SlotTime slotTime = _slotTime(slot);
    return DateTime(year, month, day, slotTime.hour, slotTime.minute);
  }

  _SlotTime _slotTime(String slot) {
    switch (slot) {
      case "breakfast":
        return const _SlotTime(8, 0);
      case "lunch":
        return const _SlotTime(12, 0);
      case "dinner":
        return const _SlotTime(18, 0);
      case "snack":
        return const _SlotTime(15, 0);
      case "custom":
      default:
        return const _SlotTime(18, 0);
    }
  }

  int _stableNotificationId(String key) {
    return key.hashCode & 0x7fffffff;
  }
}

class _SlotTime {
  final int hour;
  final int minute;

  const _SlotTime(this.hour, this.minute);
}
