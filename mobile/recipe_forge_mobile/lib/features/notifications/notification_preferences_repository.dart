import "package:shared_preferences/shared_preferences.dart";

class NotificationPreferences {
  final bool notificationsEnabled;
  final bool defaultMealReminderEnabled;
  final int? defaultPreReminderMinutes;
  final bool defaultStartCookingPrompt;

  const NotificationPreferences({
    required this.notificationsEnabled,
    required this.defaultMealReminderEnabled,
    required this.defaultPreReminderMinutes,
    required this.defaultStartCookingPrompt,
  });
}

class NotificationPreferencesRepository {
  static const String _notificationsEnabledKey = "notifications.enabled";
  static const String _mealReminderDefaultEnabledKey = "notifications.meal.default_enabled";
  static const String _mealReminderDefaultPreMinutesKey = "notifications.meal.default_pre_minutes";
  static const String _startCookingDefaultKey = "notifications.meal.default_start_prompt";

  Future<NotificationPreferences> load() async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    return NotificationPreferences(
      notificationsEnabled: prefs.getBool(_notificationsEnabledKey) ?? false,
      defaultMealReminderEnabled: prefs.getBool(_mealReminderDefaultEnabledKey) ?? false,
      defaultPreReminderMinutes: prefs.getInt(_mealReminderDefaultPreMinutesKey),
      defaultStartCookingPrompt: prefs.getBool(_startCookingDefaultKey) ?? false,
    );
  }

  Future<void> setNotificationsEnabled(bool value) async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_notificationsEnabledKey, value);
  }

  Future<void> setMealDefaultReminderEnabled(bool value) async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_mealReminderDefaultEnabledKey, value);
  }

  Future<void> setMealDefaultPreReminderMinutes(int? value) async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    if (value == null) {
      await prefs.remove(_mealReminderDefaultPreMinutesKey);
      return;
    }
    await prefs.setInt(_mealReminderDefaultPreMinutesKey, value);
  }

  Future<void> setDefaultStartCookingPrompt(bool value) async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_startCookingDefaultKey, value);
  }
}
