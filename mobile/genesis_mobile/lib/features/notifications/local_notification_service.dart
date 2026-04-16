import "dart:convert";
import "dart:async";

import "package:flutter_local_notifications/flutter_local_notifications.dart";
import "package:timezone/data/latest.dart" as tzdata;
import "package:timezone/timezone.dart" as tz;

class LocalNotificationRequest {
  final int id;
  final DateTime scheduledAtLocal;
  final String title;
  final String body;
  final Map<String, dynamic> payload;

  const LocalNotificationRequest({
    required this.id,
    required this.scheduledAtLocal,
    required this.title,
    required this.body,
    required this.payload,
  });
}

class LocalNotificationService {
  final FlutterLocalNotificationsPlugin _plugin;
  bool _initialized = false;
  final StreamController<Map<String, dynamic>> _tapController = StreamController<Map<String, dynamic>>.broadcast();

  LocalNotificationService({FlutterLocalNotificationsPlugin? plugin})
      : _plugin = plugin ?? FlutterLocalNotificationsPlugin();

  Stream<Map<String, dynamic>> get tapEvents => _tapController.stream;

  Future<void> initialize() async {
    if (_initialized) {
      return;
    }
    tzdata.initializeTimeZones();
    await _plugin.initialize(
      const InitializationSettings(
        android: AndroidInitializationSettings("@mipmap/ic_launcher"),
      ),
      onDidReceiveNotificationResponse: (NotificationResponse response) {
        final String? payload = response.payload;
        if (payload == null || payload.isEmpty) {
          return;
        }
        final dynamic decoded = jsonDecode(payload);
        if (decoded is Map<String, dynamic>) {
          _tapController.add(decoded);
        }
      },
    );
    _initialized = true;
  }

  Future<void> requestPermissionsIfNeeded() async {
    await initialize();
    await _plugin
        .resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()
        ?.requestNotificationsPermission();
  }

  Future<void> schedule(LocalNotificationRequest request) async {
    await initialize();
    await _plugin.zonedSchedule(
      request.id,
      request.title,
      request.body,
      tz.TZDateTime.from(request.scheduledAtLocal, tz.local),
      const NotificationDetails(
        android: AndroidNotificationDetails(
          "genesis_reminders",
          "Recipe reminders",
          channelDescription: "Meal reminders and cooking timers",
          importance: Importance.high,
          priority: Priority.high,
        ),
      ),
      payload: jsonEncode(request.payload),
      androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
      uiLocalNotificationDateInterpretation: UILocalNotificationDateInterpretation.absoluteTime,
    );
  }

  Future<void> showNow({
    required int id,
    required String title,
    required String body,
    required Map<String, dynamic> payload,
  }) async {
    await initialize();
    await _plugin.show(
      id,
      title,
      body,
      const NotificationDetails(
        android: AndroidNotificationDetails(
          "genesis_timers",
          "Recipe timers",
          channelDescription: "Timer completion alerts",
          importance: Importance.high,
          priority: Priority.high,
        ),
      ),
      payload: jsonEncode(payload),
    );
  }

  Future<void> cancel(int id) async {
    await initialize();
    await _plugin.cancel(id);
  }
}
