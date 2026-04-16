import "package:http/http.dart" as http;

import "../config/app_config.dart";
import "../data/db/app_database.dart";
import "../data/repositories/recipe_repository.dart";
import "../data/repositories/sync_meta_repository.dart";
import "../data/sync/sync_api_client.dart";
import "../data/sync/sync_service.dart";
import "../features/notifications/local_notification_service.dart";
import "../features/notifications/meal_reminder_service.dart";
import "../features/notifications/notification_preferences_repository.dart";
import "../features/recipe_view/timer_runtime_controller.dart";

class AppDependencies {
  final AppDatabase database;
  final RecipeRepository recipeRepository;
  final SyncMetaRepository syncMetaRepository;
  final SyncService syncService;
  final TimerRuntimeController timerRuntimeController;
  final MealReminderService mealReminderService;
  final NotificationPreferencesRepository notificationPreferencesRepository;
  final LocalNotificationService localNotificationService;

  AppDependencies._({
    required this.database,
    required this.recipeRepository,
    required this.syncMetaRepository,
    required this.syncService,
    required this.timerRuntimeController,
    required this.mealReminderService,
    required this.notificationPreferencesRepository,
    required this.localNotificationService,
  });

  static Future<AppDependencies> create() async {
    final AppDatabase database = AppDatabase();
    final RecipeRepository recipeRepository = RecipeRepository(database);
    final SyncMetaRepository syncMetaRepository = SyncMetaRepository();
    final SyncApiClient syncApiClient = SyncApiClient(http.Client());
    final SyncService syncService = SyncService(
      syncApiClient,
      recipeRepository,
      syncMetaRepository,
      deviceId: "android-device-01",
      sessionId: "mobile-session-01",
    );
    final TimerRuntimeController timerRuntimeController = TimerRuntimeController();
    final NotificationPreferencesRepository notificationPreferencesRepository = NotificationPreferencesRepository();
    final LocalNotificationService localNotificationService = LocalNotificationService();
    final MealReminderService mealReminderService = MealReminderService(
      recipeRepository,
      localNotificationService,
      notificationPreferencesRepository,
    );
    final String? existingHost = await syncMetaRepository.getHost();
    if (existingHost == null || existingHost.isEmpty) {
      await syncMetaRepository.setHost(kAppConfig.defaultHost);
    }
    return AppDependencies._(
      database: database,
      recipeRepository: recipeRepository,
      syncMetaRepository: syncMetaRepository,
      syncService: syncService,
      timerRuntimeController: timerRuntimeController,
      mealReminderService: mealReminderService,
      notificationPreferencesRepository: notificationPreferencesRepository,
      localNotificationService: localNotificationService,
    );
  }
}

