import "package:flutter/material.dart";

import "../../data/models/recipe_models.dart";
import "meal_plan_controller.dart";
import "meal_plan_defaults.dart";

class MealPlanScreen extends StatefulWidget {
  final MealPlanController controller;
  final VoidCallback? onBrowseRecipes;

  const MealPlanScreen({super.key, required this.controller, this.onBrowseRecipes});

  @override
  State<MealPlanScreen> createState() => _MealPlanScreenState();
}

class _MealPlanScreenState extends State<MealPlanScreen> {
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
    final MealPlanController c = widget.controller;
    if (c.loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (c.error != null) {
      return Center(child: Text(c.error!));
    }
    return Padding(
      padding: const EdgeInsets.all(8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          if (c.mealPlans.isEmpty)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text("Plan a meal", style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 8),
                    const Text("Create a plan, add recipes, then build a grocery list when you are ready."),
                    const SizedBox(height: 12),
                    FilledButton(onPressed: _createMealPlan, child: const Text("New meal plan")),
                    if (widget.onBrowseRecipes != null) ...<Widget>[
                      const SizedBox(height: 8),
                      OutlinedButton(onPressed: widget.onBrowseRecipes, child: const Text("Choose a recipe")),
                    ],
                  ],
                ),
              ),
            ),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: <Widget>[
              if (c.mealPlans.isNotEmpty)
                FilledButton.tonal(onPressed: _createMealPlan, child: const Text("New meal plan")),
              FilledButton.tonal(
                onPressed: c.selectedMealPlanId == null ? null : c.generateGroceryForSelectedMealPlan,
                child: const Text("Generate grocery"),
              ),
              FilledButton.tonal(
                onPressed: c.selectedMealPlanId == null ? null : _deleteMealPlanWithUndo,
                child: const Text("Delete meal plan"),
              ),
              FilledButton.tonal(
                onPressed: c.selectedMealPlanId == null ? null : c.generateGroceryForCurrentWeek,
                child: const Text("Grocery this week"),
              ),
              FilledButton.tonal(
                onPressed: c.selectedMealPlanId == null ? null : _generateRangeGroceryDialog,
                child: const Text("Grocery range"),
              ),
              FilledButton.tonal(
                onPressed: c.selectedMealPlanId == null ? null : _regenerateGroceryWithWarning,
                child: const Text("Regenerate snapshot"),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ExpansionTile(
            title: const Text("Reminders & defaults"),
            subtitle: const Text("Optional"),
            initiallyExpanded: false,
            children: <Widget>[
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                child: Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: <Widget>[
                    FilterChip(
                      label: const Text("Notifications"),
                      selected: c.notificationPreferences.notificationsEnabled,
                      onSelected: (bool selected) => c.setNotificationsEnabled(selected),
                    ),
                    FilterChip(
                      label: const Text("Default meal reminder"),
                      selected: c.notificationPreferences.defaultMealReminderEnabled,
                      onSelected: (bool selected) => c.updateReminderDefaults(mealReminderEnabled: selected),
                    ),
                    ActionChip(
                      label: Text(
                        c.notificationPreferences.defaultPreReminderMinutes == null
                            ? "Default pre: none"
                            : "Default pre: ${c.notificationPreferences.defaultPreReminderMinutes}m",
                      ),
                      onPressed: _editReminderDefaultsDialog,
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          if (c.mealPlans.isNotEmpty) ...<Widget>[
            const Text("Meal Plans", style: TextStyle(fontWeight: FontWeight.bold)),
            SizedBox(
              height: 56,
              child: ListView(
                scrollDirection: Axis.horizontal,
                children: c.mealPlans
                    .map(
                      (MealPlanSummary plan) => Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: ChoiceChip(
                          selected: c.selectedMealPlanId == plan.id,
                          label: Text("${plan.name} (${plan.itemCount})"),
                          onSelected: (_) => c.selectMealPlan(plan.id),
                        ),
                      ),
                    )
                    .toList(),
              ),
            ),
          ],
          if (c.selectedMealPlanId != null) ...<Widget>[
            Row(
              children: <Widget>[
                Expanded(
                  child: DropdownButtonFormField<String>(
                    decoration: const InputDecoration(labelText: "Quick add recipe (unassigned)"),
                    items: c.availableRecipes
                        .map((RecipeSummary recipe) => DropdownMenuItem<String>(value: recipe.id, child: Text(recipe.title)))
                        .toList(),
                    onChanged: (String? recipeId) {
                      if (recipeId != null) {
                        c.addRecipeToSelectedMealPlan(recipeId);
                      }
                    },
                  ),
                ),
                const SizedBox(width: 8),
                FilledButton.tonal(
                  onPressed: _scheduleRecipeDialog,
                  child: const Text("Schedule"),
                ),
              ],
            ),
            const SizedBox(height: 8),
            _buildWeekHeader(c),
            _buildTodayUpcoming(c),
            const Text("Plan items", style: TextStyle(fontWeight: FontWeight.bold)),
            Expanded(
              child: _buildWeeklyPlanner(c),
            ),
          ],
          const SizedBox(height: 8),
          const Text("Grocery Lists", style: TextStyle(fontWeight: FontWeight.bold)),
          if (c.groceryLists.isEmpty)
            Card(
              child: ListTile(
                title: const Text("No grocery list yet"),
                subtitle: Text(
                  c.selectedMealPlanId == null
                      ? "Create a meal plan and schedule meals, then tap Generate grocery."
                      : "When this plan has scheduled meals, generate a grocery list from the buttons above.",
                ),
              ),
            ),
          if (c.groceryLists.isNotEmpty)
            SizedBox(
              height: 56,
              child: ListView(
                scrollDirection: Axis.horizontal,
                children: c.groceryLists
                    .map(
                      (GroceryListSummary list) => Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: ActionChip(
                          label: Text(list.name),
                          onPressed: () => c.selectGroceryList(list.id),
                        ),
                      ),
                    )
                    .toList(),
              ),
            ),
          if (c.groceryItems.isNotEmpty)
            Expanded(
              child: ListView.builder(
                itemCount: c.groceryItems.length,
                itemBuilder: (BuildContext context, int index) {
                  final GroceryListItem item = c.groceryItems[index];
                  final String qty = item.quantityValue == null ? "" : "${item.quantityValue}";
                  final String unit = item.unit ?? "";
                  final String sourceLabel = item.sourceType == "manual"
                      ? "MANUAL"
                      : (item.wasUserModified ? "EDITED" : "GENERATED");
                  return ListTile(
                    leading: Checkbox(
                      value: item.checked,
                      onChanged: (bool? checked) => c.toggleGroceryItem(item.id, checked ?? false),
                    ),
                    title: Text(item.name),
                    subtitle: Text("$qty $unit".trim()),
                    trailing: Wrap(
                      spacing: 4,
                      children: <Widget>[
                        Chip(label: Text(sourceLabel)),
                        IconButton(
                          icon: const Icon(Icons.arrow_upward, size: 18),
                          onPressed: () => c.moveGroceryItem(index, -1),
                        ),
                        IconButton(
                          icon: const Icon(Icons.arrow_downward, size: 18),
                          onPressed: () => c.moveGroceryItem(index, 1),
                        ),
                        IconButton(
                          icon: const Icon(Icons.edit_outlined),
                          onPressed: () => _editGroceryItem(item),
                        ),
                        IconButton(
                          icon: const Icon(Icons.delete_outline),
                          onPressed: () => c.deleteGroceryItem(item.id),
                        ),
                      ],
                    ),
                  );
                },
              ),
            ),
          if (c.selectedGroceryListId != null)
            FilledButton.icon(
              onPressed: _addManualGroceryItem,
              icon: const Icon(Icons.add),
              label: const Text("Add manual item"),
            ),
        ],
      ),
    );
  }

  Widget _buildWeekHeader(MealPlanController c) {
    final String start = _labelDate(c.selectedWeekStart);
    final String end = _labelDate(c.selectedWeekStart.add(const Duration(days: 6)));
    return Row(
      children: <Widget>[
        IconButton(onPressed: () => c.shiftWeek(-1), icon: const Icon(Icons.chevron_left)),
        Expanded(
          child: Text(
            "Week: $start - $end",
            textAlign: TextAlign.center,
            style: const TextStyle(fontWeight: FontWeight.bold),
          ),
        ),
        IconButton(onPressed: () => c.shiftWeek(1), icon: const Icon(Icons.chevron_right)),
      ],
    );
  }

  Widget _buildTodayUpcoming(MealPlanController c) {
    final int todayCount = c.plannedForToday().length;
    final int weekCount = c.plannedForSelectedWeek().length;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: <Widget>[
          Chip(label: Text("Today: $todayCount")),
          const SizedBox(width: 8),
          Chip(label: Text("This week: $weekCount")),
        ],
      ),
    );
  }

  Widget _buildWeeklyPlanner(MealPlanController c) {
    final List<DateTime> days = c.getSelectedWeekDays();
    return ListView(
      children: <Widget>[
        for (final DateTime day in days) _buildDayGroup(c, day),
        _buildUnassignedGroup(c),
      ],
    );
  }

  Widget _buildDayGroup(MealPlanController c, DateTime day) {
    final String dateKey = _dateOnly(day);
    final List<MealPlanItem> items = c.plannedForDate(dateKey);
    return Card(
      child: ExpansionTile(
        initiallyExpanded: items.isNotEmpty,
        title: Text(_labelDate(day, includeWeekday: true)),
        subtitle: Text("${items.length} meals"),
        children: items.isEmpty
            ? const <Widget>[ListTile(title: Text("No meals scheduled"))]
            : items.map((MealPlanItem item) => _buildMealItemTile(c, item)).toList(),
      ),
    );
  }

  Widget _buildUnassignedGroup(MealPlanController c) {
    final List<MealPlanItem> unassigned = c.mealPlanItems.where((MealPlanItem item) => item.plannedDate == null).toList();
    return Card(
      child: ExpansionTile(
        title: const Text("Unassigned"),
        subtitle: Text("${unassigned.length} items"),
        children: unassigned.isEmpty
            ? const <Widget>[ListTile(title: Text("No unassigned items"))]
            : unassigned.map((MealPlanItem item) => _buildMealItemTile(c, item)).toList(),
      ),
    );
  }

  Widget _buildMealItemTile(MealPlanController c, MealPlanItem item) {
    final RecipeSummary? recipe = c.availableRecipes.cast<RecipeSummary?>().firstWhere(
          (RecipeSummary? candidate) => candidate?.id == item.recipeId,
          orElse: () => null,
        );
    final String slotText = item.mealSlot == null
        ? "No slot"
        : (item.mealSlot == "custom" ? (item.slotLabel ?? "Custom") : item.mealSlot!);
    final String subtitle = <String>[
      slotText,
      if (item.servingsOverride != null) "Servings ${item.servingsOverride}",
    ].join(" • ");
    return ListTile(
      title: Text(recipe?.title ?? item.recipeId),
      subtitle: Text(subtitle),
      trailing: Wrap(
        spacing: 4,
        children: <Widget>[
          IconButton(
            icon: const Icon(Icons.today),
            tooltip: "Set today",
            onPressed: () => c.updateMealItemSchedule(
              itemId: item.id,
              plannedDate: _dateOnly(DateTime.now()),
              mealSlot: item.mealSlot ?? "dinner",
              slotLabel: item.slotLabel,
            ),
          ),
          IconButton(
            icon: const Icon(Icons.edit_calendar),
            tooltip: "Edit schedule",
            onPressed: () => _editScheduleDialog(item),
          ),
          IconButton(
            icon: const Icon(Icons.check_circle_outline),
            tooltip: "Mark cooked",
            onPressed: recipe == null ? null : () => c.markMealItemCooked(recipe.id),
          ),
          IconButton(
            icon: const Icon(Icons.delete_outline),
            onPressed: () => c.removeMealPlanItem(item.id),
          ),
        ],
      ),
    );
  }

  Future<void> _createMealPlan() async {
    final TextEditingController input = TextEditingController();
    final bool? ok = await showDialog<bool>(
      context: context,
      builder: (BuildContext context) => AlertDialog(
        title: const Text("New Meal Plan"),
        content: TextField(controller: input, decoration: const InputDecoration(labelText: "Name")),
        actions: <Widget>[
          TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text("Cancel")),
          FilledButton(onPressed: () => Navigator.of(context).pop(true), child: const Text("Create")),
        ],
      ),
    );
    if (ok == true && input.text.trim().isNotEmpty) {
      await widget.controller.createMealPlan(input.text.trim());
    }
  }

  Future<void> _scheduleRecipeDialog() async {
    final MealPlanController c = widget.controller;
    if (c.selectedMealPlanId == null) {
      return;
    }
    String? recipeId;
    final DateTime initial = DateTime.now();
    DateTime selectedDate = DateTime(initial.year, initial.month, initial.day);
    String slot = kDefaultMealSlot;
    String customLabel = "";
    final TextEditingController servingsController = TextEditingController();
    bool reminderEnabled = c.notificationPreferences.defaultMealReminderEnabled;
    int? preReminderMinutes = c.notificationPreferences.defaultPreReminderMinutes;
    bool startCookingPrompt = c.notificationPreferences.defaultStartCookingPrompt;
    final bool? ok = await showDialog<bool>(
      context: context,
      builder: (BuildContext context) => StatefulBuilder(
        builder: (BuildContext context, void Function(void Function()) setState) => AlertDialog(
          title: const Text("Schedule meal"),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                DropdownButtonFormField<String>(
                  decoration: const InputDecoration(labelText: "Recipe"),
                  items: c.availableRecipes
                      .map((RecipeSummary recipe) => DropdownMenuItem<String>(value: recipe.id, child: Text(recipe.title)))
                      .toList(),
                  onChanged: (String? value) => setState(() => recipeId = value),
                ),
                ListTile(
                  title: Text("Date: ${_dateOnly(selectedDate)}"),
                  trailing: Wrap(
                    spacing: 4,
                    children: <Widget>[
                      TextButton(
                        child: const Text("Today"),
                        onPressed: () {
                          final DateTime n = DateTime.now();
                          setState(() => selectedDate = DateTime(n.year, n.month, n.day));
                        },
                      ),
                      const Icon(Icons.calendar_today),
                    ],
                  ),
                  onTap: () async {
                    final DateTime? picked = await showDatePicker(
                      context: context,
                      initialDate: selectedDate,
                      firstDate: DateTime(2020, 1, 1),
                      lastDate: DateTime(2100, 12, 31),
                    );
                    if (picked != null) {
                      setState(() => selectedDate = picked);
                    }
                  },
                ),
                ExpansionTile(
                  title: const Text("Meal time & reminders"),
                  subtitle: const Text("Optional — dinner by default"),
                  initiallyExpanded: false,
                  children: <Widget>[
                    DropdownButtonFormField<String>(
                      initialValue: slot,
                      decoration: const InputDecoration(labelText: "Meal slot"),
                      items: kMealSlotsOrderedForPicker
                          .map(
                            (String value) =>
                                DropdownMenuItem<String>(value: value, child: Text(mealSlotPickerLabel(value))),
                          )
                          .toList(),
                      onChanged: (String? value) => setState(() => slot = value ?? kDefaultMealSlot),
                    ),
                    if (slot == "custom")
                      TextField(
                        decoration: const InputDecoration(labelText: "Custom label"),
                        onChanged: (String value) => customLabel = value,
                      ),
                    TextField(
                      controller: servingsController,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(labelText: "Servings override (optional)"),
                    ),
                    SwitchListTile(
                      value: reminderEnabled,
                      title: const Text("Meal reminder"),
                      onChanged: (bool value) => setState(() => reminderEnabled = value),
                    ),
                    if (reminderEnabled)
                      DropdownButtonFormField<int?>(
                        initialValue: preReminderMinutes,
                        decoration: const InputDecoration(labelText: "Pre-reminder"),
                        items: const <DropdownMenuItem<int?>>[
                          DropdownMenuItem<int?>(value: null, child: Text("None")),
                          DropdownMenuItem<int?>(value: 15, child: Text("15 min before")),
                          DropdownMenuItem<int?>(value: 30, child: Text("30 min before")),
                        ],
                        onChanged: (int? value) => setState(() => preReminderMinutes = value),
                      ),
                    if (reminderEnabled)
                      SwitchListTile(
                        value: startCookingPrompt,
                        title: const Text("Start cooking prompt (5 min before)"),
                        onChanged: (bool value) => setState(() => startCookingPrompt = value),
                      ),
                  ],
                ),
              ],
            ),
          ),
          actions: <Widget>[
            TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text("Cancel")),
            FilledButton(onPressed: () => Navigator.of(context).pop(true), child: const Text("Add")),
          ],
        ),
      ),
    );
    if (ok == true && recipeId != null) {
      await c.addRecipeToSelectedMealPlanScheduled(
        recipeId: recipeId!,
        plannedDate: _dateOnly(selectedDate),
        mealSlot: slot,
        slotLabel: slot == "custom" ? customLabel.trim() : null,
        servingsOverride: double.tryParse(servingsController.text.trim()),
        reminderEnabled: reminderEnabled,
        preReminderMinutes: preReminderMinutes,
        startCookingPrompt: startCookingPrompt,
      );
    }
  }

  Future<void> _editScheduleDialog(MealPlanItem item) async {
    final MealPlanController c = widget.controller;
    DateTime selectedDate = _parseDate(item.plannedDate) ?? DateTime.now();
    String slot = item.mealSlot ?? kDefaultMealSlot;
    String customLabel = item.slotLabel ?? "";
    bool reminderEnabled = item.reminderEnabled;
    int? preReminderMinutes = item.preReminderMinutes;
    bool startCookingPrompt = item.startCookingPrompt;
    final bool? ok = await showDialog<bool>(
      context: context,
      builder: (BuildContext context) => StatefulBuilder(
        builder: (BuildContext context, void Function(void Function()) setState) => AlertDialog(
          title: const Text("Edit schedule"),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                ListTile(
                  title: Text("Date: ${_dateOnly(selectedDate)}"),
                  trailing: Wrap(
                    spacing: 4,
                    children: <Widget>[
                      TextButton(
                        child: const Text("Today"),
                        onPressed: () {
                          final DateTime n = DateTime.now();
                          setState(() => selectedDate = DateTime(n.year, n.month, n.day));
                        },
                      ),
                      const Icon(Icons.calendar_today),
                    ],
                  ),
                  onTap: () async {
                    final DateTime? picked = await showDatePicker(
                      context: context,
                      initialDate: selectedDate,
                      firstDate: DateTime(2020, 1, 1),
                      lastDate: DateTime(2100, 12, 31),
                    );
                    if (picked != null) {
                      setState(() => selectedDate = picked);
                    }
                  },
                ),
                ExpansionTile(
                  title: const Text("Meal time & reminders"),
                  subtitle: const Text("Optional — dinner by default"),
                  initiallyExpanded: false,
                  children: <Widget>[
                    DropdownButtonFormField<String>(
                      initialValue: slot,
                      decoration: const InputDecoration(labelText: "Meal slot"),
                      items: kMealSlotsOrderedForPicker
                          .map(
                            (String value) =>
                                DropdownMenuItem<String>(value: value, child: Text(mealSlotPickerLabel(value))),
                          )
                          .toList(),
                      onChanged: (String? value) => setState(() => slot = value ?? kDefaultMealSlot),
                    ),
                    if (slot == "custom")
                      TextField(
                        controller: TextEditingController(text: customLabel),
                        decoration: const InputDecoration(labelText: "Custom label"),
                        onChanged: (String value) => customLabel = value,
                      ),
                    SwitchListTile(
                      value: reminderEnabled,
                      title: const Text("Meal reminder"),
                      onChanged: (bool value) => setState(() => reminderEnabled = value),
                    ),
                    if (reminderEnabled)
                      DropdownButtonFormField<int?>(
                        initialValue: preReminderMinutes,
                        decoration: const InputDecoration(labelText: "Pre-reminder"),
                        items: const <DropdownMenuItem<int?>>[
                          DropdownMenuItem<int?>(value: null, child: Text("None")),
                          DropdownMenuItem<int?>(value: 15, child: Text("15 min before")),
                          DropdownMenuItem<int?>(value: 30, child: Text("30 min before")),
                        ],
                        onChanged: (int? value) => setState(() => preReminderMinutes = value),
                      ),
                    if (reminderEnabled)
                      SwitchListTile(
                        value: startCookingPrompt,
                        title: const Text("Start cooking prompt (5 min before)"),
                        onChanged: (bool value) => setState(() => startCookingPrompt = value),
                      ),
                  ],
                ),
              ],
            ),
          ),
          actions: <Widget>[
            TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text("Cancel")),
            FilledButton(onPressed: () => Navigator.of(context).pop(true), child: const Text("Save")),
          ],
        ),
      ),
    );
    if (ok == true) {
      await c.updateMealItemSchedule(
        itemId: item.id,
        plannedDate: _dateOnly(selectedDate),
        mealSlot: slot,
        slotLabel: slot == "custom" ? customLabel.trim() : null,
        reminderEnabled: reminderEnabled,
        preReminderMinutes: preReminderMinutes,
        startCookingPrompt: startCookingPrompt,
      );
    }
  }

  Future<void> _editReminderDefaultsDialog() async {
    final MealPlanController c = widget.controller;
    int? selected = c.notificationPreferences.defaultPreReminderMinutes;
    final bool? ok = await showDialog<bool>(
      context: context,
      builder: (BuildContext context) => StatefulBuilder(
        builder: (BuildContext context, void Function(void Function()) setState) => AlertDialog(
          title: const Text("Reminder defaults"),
          content: DropdownButtonFormField<int?>(
            initialValue: selected,
            decoration: const InputDecoration(labelText: "Default pre-reminder"),
            items: const <DropdownMenuItem<int?>>[
              DropdownMenuItem<int?>(value: null, child: Text("None")),
              DropdownMenuItem<int?>(value: 15, child: Text("15 min")),
              DropdownMenuItem<int?>(value: 30, child: Text("30 min")),
            ],
            onChanged: (int? value) => setState(() => selected = value),
          ),
          actions: <Widget>[
            TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text("Cancel")),
            FilledButton(onPressed: () => Navigator.of(context).pop(true), child: const Text("Save")),
          ],
        ),
      ),
    );
    if (ok == true) {
      await c.updateReminderDefaults(preReminderMinutes: selected);
    }
  }

  String _dateOnly(DateTime value) {
    return "${value.year.toString().padLeft(4, "0")}-${value.month.toString().padLeft(2, "0")}-${value.day.toString().padLeft(2, "0")}";
  }

  DateTime? _parseDate(String? value) {
    if (value == null || value.isEmpty) {
      return null;
    }
    final List<String> parts = value.split("-");
    if (parts.length != 3) {
      return null;
    }
    final int? y = int.tryParse(parts[0]);
    final int? m = int.tryParse(parts[1]);
    final int? d = int.tryParse(parts[2]);
    if (y == null || m == null || d == null) {
      return null;
    }
    return DateTime(y, m, d);
  }

  String _labelDate(DateTime day, {bool includeWeekday = false}) {
    const List<String> weekdays = <String>["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    const List<String> months = <String>["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    final String base = "${months[day.month - 1]} ${day.day}";
    if (!includeWeekday) {
      return base;
    }
    return "${weekdays[day.weekday - 1]}, $base";
  }

  Future<void> _addManualGroceryItem() async {
    final TextEditingController nameController = TextEditingController();
    final TextEditingController qtyController = TextEditingController();
    final TextEditingController unitController = TextEditingController();
    final bool? ok = await showDialog<bool>(
      context: context,
      builder: (BuildContext context) => AlertDialog(
        title: const Text("Add manual grocery item"),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            TextField(controller: nameController, decoration: const InputDecoration(labelText: "Name")),
            TextField(controller: qtyController, decoration: const InputDecoration(labelText: "Quantity (optional)")),
            TextField(controller: unitController, decoration: const InputDecoration(labelText: "Unit (optional)")),
          ],
        ),
        actions: <Widget>[
          TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text("Cancel")),
          FilledButton(onPressed: () => Navigator.of(context).pop(true), child: const Text("Add")),
        ],
      ),
    );
    if (ok == true && nameController.text.trim().isNotEmpty) {
      final double? qty = double.tryParse(qtyController.text.trim());
      await widget.controller.addManualGroceryItem(
        name: nameController.text.trim(),
        quantityValue: qty,
        unit: unitController.text.trim().isEmpty ? null : unitController.text.trim(),
      );
    }
  }

  Future<void> _editGroceryItem(GroceryListItem item) async {
    final TextEditingController nameController = TextEditingController(text: item.name);
    final TextEditingController qtyController =
        TextEditingController(text: item.quantityValue == null ? "" : item.quantityValue.toString());
    final TextEditingController unitController = TextEditingController(text: item.unit ?? "");
    final bool? ok = await showDialog<bool>(
      context: context,
      builder: (BuildContext context) => AlertDialog(
        title: const Text("Edit grocery item"),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            TextField(controller: nameController, decoration: const InputDecoration(labelText: "Name")),
            TextField(controller: qtyController, decoration: const InputDecoration(labelText: "Quantity (optional)")),
            TextField(controller: unitController, decoration: const InputDecoration(labelText: "Unit (optional)")),
          ],
        ),
        actions: <Widget>[
          TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text("Cancel")),
          FilledButton(onPressed: () => Navigator.of(context).pop(true), child: const Text("Save")),
        ],
      ),
    );
    if (ok == true && nameController.text.trim().isNotEmpty) {
      await widget.controller.updateGroceryItem(
        itemId: item.id,
        name: nameController.text.trim(),
        quantityValue: double.tryParse(qtyController.text.trim()),
        unit: unitController.text.trim().isEmpty ? null : unitController.text.trim(),
      );
    }
  }

  Future<void> _regenerateGroceryWithWarning() async {
    final bool? confirmed = await showDialog<bool>(
      context: context,
      builder: (BuildContext context) => AlertDialog(
        title: const Text("Regenerate grocery snapshot"),
        content: const Text(
          "This generates a NEW grocery snapshot from the meal plan.\n\nExisting lists and manual edits are preserved.",
        ),
        actions: <Widget>[
          TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text("Cancel")),
          FilledButton(onPressed: () => Navigator.of(context).pop(true), child: const Text("Generate New Snapshot")),
        ],
      ),
    );
    if (confirmed == true) {
      await widget.controller.regenerateGroceryForSelectedMealPlan();
    }
  }

  Future<void> _generateRangeGroceryDialog() async {
    final TextEditingController start = TextEditingController(text: _dateOnly(DateTime.now()));
    final TextEditingController end = TextEditingController(
      text: _dateOnly(DateTime.now().add(const Duration(days: 6))),
    );
    final bool? ok = await showDialog<bool>(
      context: context,
      builder: (BuildContext context) => AlertDialog(
        title: const Text("Generate range grocery"),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            TextField(controller: start, decoration: const InputDecoration(labelText: "Start YYYY-MM-DD")),
            TextField(controller: end, decoration: const InputDecoration(labelText: "End YYYY-MM-DD")),
          ],
        ),
        actions: <Widget>[
          TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text("Cancel")),
          FilledButton(onPressed: () => Navigator.of(context).pop(true), child: const Text("Generate")),
        ],
      ),
    );
    if (ok == true) {
      await widget.controller.generateGroceryForDateRange(start.text.trim(), end.text.trim());
    }
  }

  Future<void> _deleteMealPlanWithUndo() async {
    await widget.controller.deleteSelectedMealPlan();
    if (!mounted) {
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: const Text("Meal plan deleted"),
        duration: const Duration(seconds: 6),
        behavior: SnackBarBehavior.floating,
        action: SnackBarAction(
          label: "Undo",
          onPressed: () => widget.controller.undoDeleteMealPlan(),
        ),
      ),
    );
  }
}
