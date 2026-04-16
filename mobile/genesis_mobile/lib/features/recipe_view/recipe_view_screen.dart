import "package:flutter/material.dart";
import "dart:io";

import "../../data/models/recipe_models.dart";
import "link_resolution.dart";
import "recipe_view_controller.dart";
import "timer_runtime_controller.dart";

class RecipeViewScreen extends StatefulWidget {
  final String recipeId;
  final RecipeViewController controller;
  final TimerRuntimeController timerRuntimeController;
  final VoidCallback? onEditRequested;
  /// Opens another recipe from a sub-recipe ingredient line (e.g. lasagna → béchamel).
  final void Function(String recipeId)? onNavigateToSubRecipe;

  const RecipeViewScreen({
    super.key,
    required this.recipeId,
    required this.controller,
    required this.timerRuntimeController,
    this.onEditRequested,
    this.onNavigateToSubRecipe,
  });

  @override
  State<RecipeViewScreen> createState() => _RecipeViewScreenState();
}

class _RecipeViewScreenState extends State<RecipeViewScreen> with SingleTickerProviderStateMixin {
  late final TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this, initialIndex: 2);
    widget.controller.addListener(_onChanged);
    widget.controller.loadRecipe(widget.recipeId);
  }

  @override
  void dispose() {
    widget.controller.removeListener(_onChanged);
    _tabController.dispose();
    super.dispose();
  }

  void _onChanged() {
    if (mounted) {
      setState(() {});
    }
  }

  @override
  Widget build(BuildContext context) {
    if (widget.controller.loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (widget.controller.error != null) {
      return Scaffold(
        appBar: AppBar(title: const Text("Recipe")),
        body: Center(child: Text(widget.controller.error!)),
      );
    }
    final RecipeDetail recipe = widget.controller.recipe!;
    final bool bundled = recipe.scope == "bundled";
    return Scaffold(
      appBar: AppBar(
        title: Text(recipe.title),
        actions: <Widget>[
          IconButton(
            icon: Icon(widget.controller.isFavorite ? Icons.favorite : Icons.favorite_border),
            tooltip: "Toggle favorite",
            onPressed: () => widget.controller.toggleFavorite(),
          ),
          IconButton(
            icon: const Icon(Icons.check_circle_outline),
            tooltip: "Mark cooked",
            onPressed: () => widget.controller.markCooked(),
          ),
          IconButton(
            icon: const Icon(Icons.edit),
            tooltip: "Edit recipe",
            onPressed: widget.onEditRequested,
          ),
        ],
        bottom: TabBar(
          controller: _tabController,
          tabs: const <Tab>[
            Tab(text: "Equipment"),
            Tab(text: "Ingredients"),
            Tab(text: "Steps"),
          ],
        ),
      ),
      body: Column(
        children: <Widget>[
          Material(
            color: Colors.black26,
            child: ListTile(
              dense: true,
              title: Text(recipe.subtitle ?? "Cooking view"),
              subtitle: Text(bundled ? "Bundled read-only recipe" : "Local recipe"),
              trailing: Chip(label: Text(bundled ? "BUNDLED" : "LOCAL")),
            ),
          ),
          if (widget.controller.coverImagePath != null)
            SizedBox(
              height: 160,
              width: double.infinity,
              child: Image.file(
                File(widget.controller.coverImagePath!),
                fit: BoxFit.cover,
              ),
            )
          else if (recipe.coverMediaId != null)
            const Padding(
              padding: EdgeInsets.all(8),
              child: Text("Cover image metadata exists but file is missing on this device."),
            ),
          Expanded(
            child: TabBarView(
              controller: _tabController,
              children: <Widget>[
                _EquipmentTab(recipe: recipe),
                _IngredientsTab(recipe: recipe, onNavigateToSubRecipe: widget.onNavigateToSubRecipe),
                _StepsTab(
                  recipe: recipe,
                  timerRuntimeController: widget.timerRuntimeController,
                  stepImagePaths: widget.controller.stepImagePaths,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _EquipmentTab extends StatelessWidget {
  final RecipeDetail recipe;

  const _EquipmentTab({required this.recipe});

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      itemCount: recipe.equipment.length,
      itemBuilder: (BuildContext context, int index) {
        final RecipeEquipmentItem item = recipe.equipment[index];
        return ListTile(
          leading: Text("${index + 1}"),
          title: Text(item.name),
          subtitle: Text(<String>[
            if (item.description != null && item.description!.isNotEmpty) item.description!,
            if (item.notes != null && item.notes!.isNotEmpty) "Notes: ${item.notes}",
            if (item.affiliateUrl != null && item.affiliateUrl!.isNotEmpty) "Affiliate: ${item.affiliateUrl}",
          ].join("\n")),
          trailing: Text(item.isRequired ? "Required" : "Optional"),
          isThreeLine: true,
        );
      },
    );
  }
}

class _IngredientsTab extends StatelessWidget {
  final RecipeDetail recipe;
  final void Function(String recipeId)? onNavigateToSubRecipe;

  const _IngredientsTab({required this.recipe, this.onNavigateToSubRecipe});

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      itemCount: recipe.ingredients.length,
      itemBuilder: (BuildContext context, int index) {
        final RecipeIngredientItem item = recipe.ingredients[index];
        final String structured = <String>[
          if (item.quantityValue != null) item.quantityValue.toString(),
          if (item.unit != null && item.unit!.isNotEmpty) item.unit!,
          if (item.ingredientName != null && item.ingredientName!.isNotEmpty) item.ingredientName!,
        ].join(" ");
        final bool isSub = item.subRecipeId != null && item.subRecipeId!.isNotEmpty;
        final bool canOpenSub = isSub && onNavigateToSubRecipe != null;
        return ListTile(
          leading: Text("${index + 1}"),
          title: Text(item.rawText),
          subtitle: Text(<String>[
            if (isSub) "Sub-recipe · expands for grocery",
            if (structured.isNotEmpty) structured,
            if (item.substitutions != null && item.substitutions!.isNotEmpty) "Substitute: ${item.substitutions}",
            if (item.preparationNotes != null && item.preparationNotes!.isNotEmpty) "Prep: ${item.preparationNotes}",
            if (!isSub &&
                structured.isEmpty &&
                (item.substitutions == null || item.substitutions!.isEmpty) &&
                (item.preparationNotes == null || item.preparationNotes!.isEmpty))
              "Unstructured entry",
          ].join("\n")),
          trailing: Text(item.isOptional ? "Optional" : ""),
          isThreeLine: true,
          onTap: canOpenSub ? () => onNavigateToSubRecipe!(item.subRecipeId!) : null,
        );
      },
    );
  }
}

class _StepsTab extends StatelessWidget {
  final RecipeDetail recipe;
  final TimerRuntimeController timerRuntimeController;
  final Map<String, String> stepImagePaths;

  const _StepsTab({
    required this.recipe,
    required this.timerRuntimeController,
    required this.stepImagePaths,
  });

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      itemCount: recipe.steps.length,
      itemBuilder: (BuildContext context, int index) {
        final RecipeStep step = recipe.steps[index];
        return Card(
          margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  "Step ${index + 1} • ${step.title ?? step.stepType}",
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                if (stepImagePaths.containsKey(step.id))
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Image.file(File(stepImagePaths[step.id]!), height: 140, fit: BoxFit.cover),
                  )
                else if (step.mediaId != null)
                  const Padding(
                    padding: EdgeInsets.only(bottom: 8),
                    child: Text("Step image missing on this device"),
                  ),
                _LinkedStepBody(
                  recipe: recipe,
                  step: step,
                ),
                const SizedBox(height: 10),
                if (step.timers.isNotEmpty)
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: step.timers
                        .map(
                          (StepTimer timer) => _TimerChip(
                            timer: timer,
                            controller: timerRuntimeController,
                            recipeId: recipe.id,
                          ),
                        )
                        .toList(),
                  )
                else
                  Text(
                    "No timers",
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _LinkedStepBody extends StatelessWidget {
  final RecipeDetail recipe;
  final RecipeStep step;

  const _LinkedStepBody({
    required this.recipe,
    required this.step,
  });

  @override
  Widget build(BuildContext context) {
    final LinkResolutionResult resolved = resolveStepTextSegments(recipe, step);
    return Wrap(
      spacing: 4,
      runSpacing: 4,
      children: resolved.segments.map((ResolvedStepSegment segment) {
        if (!segment.isLink) {
          return Text(segment.text);
        }
        return ActionChip(
          label: Text(segment.text),
          onPressed: () => _showLinkDetail(context, segment.link, segment.text),
        );
      }).toList(),
    );
  }

  void _showLinkDetail(BuildContext context, StepLink? link, String fallbackLabel) {
    showModalBottomSheet<void>(
      context: context,
      builder: (BuildContext context) {
        if (link == null) {
          return ListTile(
            title: Text(fallbackLabel),
            subtitle: const Text("Linked item is missing."),
          );
        }
        if (link.targetType == "ingredient") {
          final RecipeIngredientItem? ingredient = findIngredientById(recipe, link.targetId);
          if (ingredient == null) {
            return ListTile(
              title: Text(link.labelOverride ?? link.labelSnapshot),
              subtitle: const Text("Ingredient no longer exists."),
            );
          }
          return ListView(
            padding: const EdgeInsets.all(16),
            shrinkWrap: true,
            children: <Widget>[
              Text(ingredient.rawText, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              Text(
                <String>[
                  if (ingredient.quantityValue != null) ingredient.quantityValue.toString(),
                  if (ingredient.unit != null) ingredient.unit!,
                  if (ingredient.ingredientName != null) ingredient.ingredientName!,
                ].join(" "),
              ),
              if (ingredient.substitutions != null && ingredient.substitutions!.isNotEmpty)
                Text("Substitutions: ${ingredient.substitutions}"),
              if (ingredient.preparationNotes != null && ingredient.preparationNotes!.isNotEmpty)
                Text("Notes: ${ingredient.preparationNotes}"),
            ],
          );
        }
        final RecipeEquipmentItem? equipment = findEquipmentById(recipe, link.targetId);
        if (equipment == null) {
          return ListTile(
            title: Text(link.labelOverride ?? link.labelSnapshot),
            subtitle: const Text("Equipment no longer exists."),
          );
        }
        return ListView(
          padding: const EdgeInsets.all(16),
          shrinkWrap: true,
          children: <Widget>[
            Text(equipment.name, style: Theme.of(context).textTheme.titleMedium),
            if (equipment.description != null && equipment.description!.isNotEmpty) Text(equipment.description!),
            Text(equipment.isRequired ? "Required" : "Optional"),
            if (equipment.notes != null && equipment.notes!.isNotEmpty) Text("Notes: ${equipment.notes}"),
            if (equipment.affiliateUrl != null && equipment.affiliateUrl!.isNotEmpty)
              Text("Affiliate: ${equipment.affiliateUrl}"),
          ],
        );
      },
    );
  }
}

class _TimerChip extends StatefulWidget {
  final StepTimer timer;
  final TimerRuntimeController controller;
  final String recipeId;

  const _TimerChip({
    required this.timer,
    required this.controller,
    required this.recipeId,
  });

  @override
  State<_TimerChip> createState() => _TimerChipState();
}

class _TimerChipState extends State<_TimerChip> {
  @override
  void initState() {
    super.initState();
    widget.controller.addListener(_onChanged);
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
    final ActiveTimerState? state = widget.controller.getTimer(widget.timer.id);
    if (state == null) {
      return FilledButton.tonal(
        onPressed: () => widget.controller.startTimer(widget.timer, recipeId: widget.recipeId),
        child: Text("Start ${widget.timer.label} (${_fmt(widget.timer.durationSeconds)})"),
      );
    }
    return Wrap(
      crossAxisAlignment: WrapCrossAlignment.center,
      spacing: 6,
      children: <Widget>[
        Chip(label: Text("${state.label}: ${_fmt(state.remainingSeconds)}")),
        IconButton(
          onPressed: () => state.isRunning ? widget.controller.pauseTimer(state.timerId) : widget.controller.resumeTimer(state.timerId),
          icon: Icon(state.isRunning ? Icons.pause : Icons.play_arrow),
          tooltip: state.isRunning ? "Pause" : "Resume",
        ),
        IconButton(
          onPressed: () => widget.controller.cancelTimer(state.timerId),
          icon: const Icon(Icons.close),
          tooltip: "Cancel",
        ),
      ],
    );
  }

  String _fmt(int seconds) {
    final int mins = seconds ~/ 60;
    final int secs = seconds % 60;
    return "${mins.toString().padLeft(2, "0")}:${secs.toString().padLeft(2, "0")}";
  }
}

