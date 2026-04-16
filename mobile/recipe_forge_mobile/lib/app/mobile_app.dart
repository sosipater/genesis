import "package:flutter/material.dart";
import "dart:async";

import "../features/home/home_controller.dart";
import "../features/home/home_screen.dart";
import "../features/home/home_service.dart";
import "../features/library/library_controller.dart";
import "../features/library/library_screen.dart";
import "../features/meal_plan/meal_plan_controller.dart";
import "../features/meal_plan/meal_plan_screen.dart";
import "../features/recipe_editor/recipe_editor_controller.dart";
import "../features/recipe_editor/recipe_editor_screen.dart";
import "../features/meal_plan/meal_plan_service.dart";
import "../features/media/mobile_media_service.dart";
import "../features/recipe_view/recipe_view_controller.dart";
import "../features/recipe_view/recipe_view_screen.dart";
import "../features/recipe_view/timer_runtime_controller.dart";
import "../features/sync/sync_controller.dart";
import "../features/sync/sync_screen.dart";
import "dependencies.dart";

class MobileApp extends StatefulWidget {
  final AppDependencies dependencies;

  const MobileApp({super.key, required this.dependencies});

  @override
  State<MobileApp> createState() => _MobileAppState();
}

class _MobileAppState extends State<MobileApp> {
  /// [MobileApp]'s [State.context] is *above* [MaterialApp], so it cannot see the
  /// root [Navigator] or [ScaffoldMessenger]. Keys keep pushes/snackbars on the app subtree.
  final GlobalKey<NavigatorState> _rootNavigatorKey = GlobalKey<NavigatorState>();
  final GlobalKey<ScaffoldMessengerState> _scaffoldMessengerKey = GlobalKey<ScaffoldMessengerState>();

  int _index = 0;
  late final HomeController _homeController;
  late final LibraryController _libraryController;
  late final SyncController _syncController;
  late final MealPlanController _mealPlanController;
  StreamSubscription<Map<String, dynamic>>? _notificationTapSubscription;

  @override
  void initState() {
    super.initState();
    _homeController = HomeController(
      widget.dependencies.recipeRepository,
      HomeService(widget.dependencies.recipeRepository),
    );
    _libraryController = LibraryController(widget.dependencies.recipeRepository);
    _syncController = SyncController(
      widget.dependencies.syncService,
      widget.dependencies.syncMetaRepository,
    );
    _mealPlanController = MealPlanController(
      widget.dependencies.recipeRepository,
      MealPlanService(widget.dependencies.recipeRepository),
      widget.dependencies.mealReminderService,
    );
    widget.dependencies.timerRuntimeController.onTimerCompleted = (state) {
      widget.dependencies.mealReminderService.notifyTimerCompleted(
        timerId: state.timerId,
        recipeId: state.recipeId,
        stepId: state.stepId,
        label: state.label,
      );
    };
    _notificationTapSubscription = widget.dependencies.localNotificationService.tapEvents.listen(_onNotificationTap);
    widget.dependencies.timerRuntimeController.addListener(_onTimerChanged);
  }

  @override
  void dispose() {
    _notificationTapSubscription?.cancel();
    widget.dependencies.timerRuntimeController.onTimerCompleted = null;
    widget.dependencies.timerRuntimeController.removeListener(_onTimerChanged);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final TimerRuntimeController timers = widget.dependencies.timerRuntimeController;
    return MaterialApp(
      navigatorKey: _rootNavigatorKey,
      scaffoldMessengerKey: _scaffoldMessengerKey,
      title: "Recipe Forge Mobile",
      debugShowCheckedModeBanner: false,
      themeMode: ThemeMode.dark,
      darkTheme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.deepOrange, brightness: Brightness.dark),
      ),
      home: Scaffold(
        appBar: AppBar(
          title: const Text("Recipe Forge"),
          actions: <Widget>[
            IconButton(
              icon: const Icon(Icons.history),
              tooltip: "Open Recent",
              onPressed: _openMostRecentRecipe,
            ),
          ],
        ),
        body: IndexedStack(
          index: _index,
          children: <Widget>[
            HomeScreen(
              controller: _homeController,
              onOpenRecipe: _openRecipe,
              onOpenMealPlan: _openMealPlanFromHome,
              onOpenGroceryList: _openGroceryFromHome,
              onOpenPlanner: _openPlannerTab,
              onCreateRecipe: _createRecipe,
              onOpenLibrary: _openLibraryTab,
            ),
            LibraryScreen(
              controller: _libraryController,
              onOpenRecipe: _openRecipe,
              onCreateRecipe: _createRecipe,
              onEditRecipe: _editRecipe,
              onOpenSync: _openSyncTab,
            ),
            SyncScreen(
              controller: _syncController,
              onSyncComplete: () {
                _libraryController.load();
                _homeController.load();
              },
            ),
            MealPlanScreen(
              controller: _mealPlanController,
              onBrowseRecipes: _openLibraryTab,
            ),
          ],
        ),
        persistentFooterButtons: timers.activeTimers.isEmpty
            ? null
            : timers.activeTimers
                .map(
                  (state) => Chip(
                    label: Text("${state.label}: ${_formatSeconds(state.remainingSeconds)}"),
                    avatar: const Icon(Icons.timer, size: 16),
                  ),
                )
                .toList(),
        bottomNavigationBar: NavigationBar(
          selectedIndex: _index,
          onDestinationSelected: (int value) => setState(() => _index = value),
          destinations: const <Widget>[
            NavigationDestination(icon: Icon(Icons.home), label: "Home"),
            NavigationDestination(icon: Icon(Icons.menu_book), label: "Library"),
            NavigationDestination(icon: Icon(Icons.sync), label: "Sync"),
            NavigationDestination(icon: Icon(Icons.calendar_month), label: "Plan"),
          ],
        ),
      ),
    );
  }

  void _openRecipe(String recipeId) {
    _rootNavigatorKey.currentState?.push(
      MaterialPageRoute<void>(
        builder: (_) => RecipeViewScreen(
          recipeId: recipeId,
          controller: RecipeViewController(widget.dependencies.recipeRepository),
          timerRuntimeController: widget.dependencies.timerRuntimeController,
          onEditRequested: () => _editRecipe(recipeId),
        ),
      ),
    );
  }

  Future<void> _createRecipe() async {
    final NavigatorState? nav = _rootNavigatorKey.currentState;
    if (nav == null) {
      return;
    }
    final String? changedId = await nav.push<String>(
      MaterialPageRoute<String>(
        builder: (_) => RecipeEditorScreen(
          controller: RecipeEditorController(
            widget.dependencies.recipeRepository,
            mediaService: MobileMediaService(widget.dependencies.recipeRepository),
          ),
        ),
      ),
    );
    if (changedId != null) {
      _libraryController.load();
      _homeController.load();
    }
  }

  Future<void> _editRecipe(String recipeId) async {
    final NavigatorState? nav = _rootNavigatorKey.currentState;
    if (nav == null) {
      return;
    }
    final String? changedId = await nav.push<String>(
      MaterialPageRoute<String>(
        builder: (_) => RecipeEditorScreen(
          controller: RecipeEditorController(
            widget.dependencies.recipeRepository,
            mediaService: MobileMediaService(widget.dependencies.recipeRepository),
          ),
          recipeId: recipeId,
        ),
      ),
    );
    if (changedId != null) {
      _libraryController.load();
      _homeController.load();
    }
  }

  Future<void> _openMostRecentRecipe() async {
    final String? recipeId = await widget.dependencies.recipeRepository.getMostRecentRecipeId();
    if (!mounted) {
      return;
    }
    if (recipeId == null) {
      _scaffoldMessengerKey.currentState?.showSnackBar(
        const SnackBar(content: Text("No recent recipe yet")),
      );
      return;
    }
    _openRecipe(recipeId);
  }

  void _onTimerChanged() {
    if (mounted) {
      setState(() {});
    }
  }

  Future<void> _openMealPlanFromHome(String mealPlanId) async {
    await _mealPlanController.selectMealPlan(mealPlanId);
    if (mounted) {
      setState(() => _index = 3);
    }
  }

  Future<void> _openGroceryFromHome(String groceryListId) async {
    await _mealPlanController.selectGroceryList(groceryListId);
    if (mounted) {
      setState(() => _index = 3);
    }
  }

  void _openPlannerTab() {
    setState(() => _index = 3);
  }

  void _openLibraryTab() {
    setState(() => _index = 1);
  }

  void _openSyncTab() {
    setState(() => _index = 2);
  }

  void _onNotificationTap(Map<String, dynamic> payload) {
    final String? recipeId = payload["recipe_id"] as String?;
    if (recipeId != null && recipeId.isNotEmpty) {
      _openRecipe(recipeId);
      return;
    }
    _openPlannerTab();
  }

  String _formatSeconds(int seconds) {
    final int mins = seconds ~/ 60;
    final int secs = seconds % 60;
    return "${mins.toString().padLeft(2, "0")}:${secs.toString().padLeft(2, "0")}";
  }
}

