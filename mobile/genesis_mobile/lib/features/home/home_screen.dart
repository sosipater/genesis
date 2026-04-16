import "package:flutter/material.dart";

import "../../data/models/recipe_models.dart";
import "home_controller.dart";
import "home_service.dart";

class HomeScreen extends StatefulWidget {
  final HomeController controller;
  final void Function(String recipeId) onOpenRecipe;
  final void Function(String mealPlanId) onOpenMealPlan;
  final void Function(String groceryListId) onOpenGroceryList;
  final VoidCallback onOpenPlanner;
  final VoidCallback onCreateRecipe;
  final VoidCallback onOpenLibrary;

  const HomeScreen({
    super.key,
    required this.controller,
    required this.onOpenRecipe,
    required this.onOpenMealPlan,
    required this.onOpenGroceryList,
    required this.onOpenPlanner,
    required this.onCreateRecipe,
    required this.onOpenLibrary,
  });

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  @override
  void initState() {
    super.initState();
    widget.controller.addListener(_onChanged);
    widget.controller.load();
  }

  @override
  void dispose() {
    widget.controller.removeListener(_onChanged);
    super.dispose();
  }

  void _onChanged() {
    if (mounted) {
      setState(() {});
    }
  }

  @override
  Widget build(BuildContext context) {
    final HomeController c = widget.controller;
    if (c.loading && c.snapshot == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (c.error != null && c.snapshot == null) {
      return Center(child: Text("Error: ${c.error}"));
    }
    final HomeSnapshot snapshot = c.snapshot!;
    return RefreshIndicator(
      onRefresh: c.load,
      child: ListView(
        padding: const EdgeInsets.all(12),
        children: <Widget>[
          if (snapshot.looksLikeFirstVisit) ...<Widget>[
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text("Get started", style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 8),
                    const Text("Create a recipe or plan a meal—everything stays on your devices."),
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: <Widget>[
                        FilledButton(onPressed: widget.onCreateRecipe, child: const Text("Create recipe")),
                        FilledButton.tonal(onPressed: widget.onOpenPlanner, child: const Text("Plan a meal")),
                      ],
                    ),
                    const SizedBox(height: 8),
                    TextButton(onPressed: widget.onOpenLibrary, child: const Text("Browse library")),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
          ],
          _sectionTitle("Today"),
          _buildToday(snapshot),
          const SizedBox(height: 12),
          _sectionTitle("This Week"),
          _buildWeek(snapshot),
          const SizedBox(height: 12),
          _sectionTitle("Quick Resume"),
          _buildQuickResume(snapshot),
          const SizedBox(height: 12),
          _sectionTitle("Favorites & Recent"),
          _buildFavoritesRecent(snapshot),
        ],
      ),
    );
  }

  Widget _buildToday(HomeSnapshot snapshot) {
    if (snapshot.todayMeals.isEmpty) {
      return Card(
        child: ListTile(
          title: const Text("Nothing on the calendar today"),
          subtitle: const Text("Pick a recipe and a day in Plan"),
          trailing: FilledButton.tonal(onPressed: widget.onOpenPlanner, child: const Text("Plan")),
        ),
      );
    }
    return Card(
      child: Column(
        children: snapshot.todayMeals
            .map(
              (HomeMealEntry entry) => ListTile(
                title: Text(entry.recipe.title),
                subtitle: Text("${_slotLabel(entry.item)} • ${entry.mealPlanName}"),
                trailing: Wrap(
                  spacing: 4,
                  children: <Widget>[
                    IconButton(
                      icon: const Icon(Icons.check_circle_outline),
                      tooltip: "Mark cooked",
                      onPressed: () => widget.controller.markCookedFromHome(entry.recipe.id),
                    ),
                    IconButton(
                      icon: const Icon(Icons.open_in_new),
                      tooltip: "Open recipe",
                      onPressed: () => widget.onOpenRecipe(entry.recipe.id),
                    ),
                  ],
                ),
              ),
            )
            .toList(),
      ),
    );
  }

  Widget _buildWeek(HomeSnapshot snapshot) {
    if (snapshot.weekByDate.isEmpty) {
      return Card(
        child: ListTile(
          title: const Text("This week is open"),
          subtitle: const Text("Schedule a meal in a few taps"),
          trailing: FilledButton.tonal(onPressed: widget.onOpenPlanner, child: const Text("Plan")),
        ),
      );
    }
    return Card(
      child: Column(
        children: snapshot.weekByDate.entries
            .map(
              (MapEntry<String, List<HomeMealEntry>> entry) => ExpansionTile(
                title: Text(entry.key),
                subtitle: Text("${entry.value.length} meal(s)"),
                children: entry.value
                    .map(
                      (HomeMealEntry meal) => ListTile(
                        dense: true,
                        title: Text(meal.recipe.title),
                        subtitle: Text(_slotLabel(meal.item)),
                        onTap: () => widget.onOpenRecipe(meal.recipe.id),
                      ),
                    )
                    .toList(),
              ),
            )
            .toList(),
      ),
    );
  }

  Widget _buildQuickResume(HomeSnapshot snapshot) {
    final List<Widget> tiles = <Widget>[];
    final HomeQuickResume quick = snapshot.quickResume;
    if (quick.recentRecipe != null) {
      tiles.add(
        ListTile(
          title: Text(quick.recentRecipe!.title),
          subtitle: const Text("Most recently opened recipe"),
          trailing: const Icon(Icons.history),
          onTap: () => widget.onOpenRecipe(quick.recentRecipe!.id),
        ),
      );
    }
    if (quick.latestGroceryList != null) {
      tiles.add(
        ListTile(
          title: Text(quick.latestGroceryList!.name),
          subtitle: const Text("Latest grocery snapshot"),
          trailing: const Icon(Icons.shopping_cart),
          onTap: () => widget.onOpenGroceryList(quick.latestGroceryList!.id),
        ),
      );
    }
    if (quick.activeMealPlan != null) {
      tiles.add(
        ListTile(
          title: Text(quick.activeMealPlan!.name),
          subtitle: const Text("Active meal plan"),
          trailing: const Icon(Icons.calendar_month),
          onTap: () => widget.onOpenMealPlan(quick.activeMealPlan!.id),
        ),
      );
    }
    tiles.add(
      ListTile(
        title: Text("Working set (${quick.workingSetCount})"),
        subtitle: const Text("Current recipe focus set"),
        trailing: const Icon(Icons.playlist_play),
        onTap: () {},
      ),
    );
    return Card(child: Column(children: tiles));
  }

  Widget _buildFavoritesRecent(HomeSnapshot snapshot) {
    if (snapshot.favorites.isEmpty && snapshot.recentOpened.isEmpty) {
      return Card(
        child: ListTile(
          title: const Text("No favorites or recents yet"),
          subtitle: const Text("Save time by starring recipes you cook often"),
          trailing: FilledButton.tonal(onPressed: widget.onOpenLibrary, child: const Text("Library")),
        ),
      );
    }
    return Card(
      child: Column(
        children: <Widget>[
          if (snapshot.favorites.isNotEmpty)
            ListTile(
              title: const Text("Favorites"),
              subtitle: Text(snapshot.favorites.map((RecipeSummary r) => r.title).take(3).join(" • ")),
            ),
          if (snapshot.recentOpened.isNotEmpty)
            ...snapshot.recentOpened
                .take(3)
                .map(
                  (RecipeSummary recipe) => ListTile(
                    dense: true,
                    title: Text(recipe.title),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => widget.onOpenRecipe(recipe.id),
                  ),
                ),
        ],
      ),
    );
  }

  Widget _sectionTitle(String title) {
    return Text(
      title,
      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
    );
  }

  String _slotLabel(MealPlanItem item) {
    if (item.mealSlot == null) {
      return "Unslotted";
    }
    if (item.mealSlot == "custom") {
      return item.slotLabel?.isNotEmpty == true ? item.slotLabel! : "Custom";
    }
    return item.mealSlot!;
  }
}
