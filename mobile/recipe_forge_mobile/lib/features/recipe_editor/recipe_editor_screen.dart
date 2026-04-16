import "package:flutter/material.dart";

import "../../data/models/recipe_models.dart";
import "../recipe_view/link_resolution.dart";
import "recipe_editor_controller.dart";

class RecipeEditorScreen extends StatefulWidget {
  final RecipeEditorController controller;
  final String? recipeId;

  const RecipeEditorScreen({
    super.key,
    required this.controller,
    this.recipeId,
  });

  @override
  State<RecipeEditorScreen> createState() => _RecipeEditorScreenState();
}

class _RecipeEditorScreenState extends State<RecipeEditorScreen> with SingleTickerProviderStateMixin {
  late final TabController _tabs;
  final TextEditingController _title = TextEditingController();
  final TextEditingController _subtitle = TextEditingController();
  final TextEditingController _author = TextEditingController();
  final TextEditingController _sourceName = TextEditingController();
  final TextEditingController _sourceUrl = TextEditingController();
  final TextEditingController _notes = TextEditingController();
  final TextEditingController _servings = TextEditingController();
  final TextEditingController _prep = TextEditingController();
  final TextEditingController _cook = TextEditingController();
  final TextEditingController _total = TextEditingController();
  String _status = "draft";
  String _difficulty = "";

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 4, vsync: this);
    widget.controller.addListener(_onChanged);
    if (widget.recipeId == null) {
      widget.controller.createNew();
    } else {
      widget.controller.load(widget.recipeId!);
    }
  }

  @override
  void dispose() {
    widget.controller.removeListener(_onChanged);
    _tabs.dispose();
    _title.dispose();
    _subtitle.dispose();
    _author.dispose();
    _sourceName.dispose();
    _sourceUrl.dispose();
    _notes.dispose();
    _servings.dispose();
    _prep.dispose();
    _cook.dispose();
    _total.dispose();
    super.dispose();
  }

  void _onChanged() {
    final RecipeDetail? recipe = widget.controller.recipe;
    if (recipe != null && _title.text != recipe.title) {
      _title.text = recipe.title;
      _subtitle.text = recipe.subtitle ?? "";
      _author.text = recipe.author ?? "";
      _sourceName.text = recipe.sourceName ?? "";
      _sourceUrl.text = recipe.sourceUrl ?? "";
      _notes.text = recipe.notes ?? "";
      _servings.text = recipe.servings?.toString() ?? "";
      _prep.text = recipe.prepMinutes?.toString() ?? "";
      _cook.text = recipe.cookMinutes?.toString() ?? "";
      _total.text = recipe.totalMinutes?.toString() ?? "";
      _status = recipe.status;
      _difficulty = recipe.difficulty ?? "";
    }
    if (mounted) {
      setState(() {});
    }
  }

  @override
  Widget build(BuildContext context) {
    if (widget.controller.loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    final RecipeDetail? recipe = widget.controller.recipe;
    if (recipe == null) {
      return Scaffold(
        appBar: AppBar(title: const Text("Recipe Editor")),
        body: Center(child: Text(widget.controller.error ?? "Unable to load recipe")),
      );
    }
    final bool bundled = recipe.scope == "bundled";
    return PopScope(
      canPop: !widget.controller.isDirty,
      onPopInvokedWithResult: (bool didPop, Object? result) async {
        if (didPop || !widget.controller.isDirty) {
          return;
        }
        final NavigatorState navigator = Navigator.of(context);
        final bool leave = await _confirmDiscard(context);
        if (leave && mounted) {
          navigator.pop();
        }
      },
      child: Scaffold(
        appBar: AppBar(
          title: Text(recipe.title),
          actions: <Widget>[
            if (bundled)
              TextButton(
                onPressed: widget.controller.duplicateAsLocal,
                child: const Text("Duplicate"),
              ),
            TextButton(
              onPressed: widget.controller.saving ? null : _onSave,
              child: const Text("Save"),
            ),
          ],
          bottom: TabBar(
            controller: _tabs,
            tabs: const <Tab>[
              Tab(text: "Meta"),
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
                title: Text(bundled ? "Bundled recipe is read-only" : "Local recipe (editable)"),
                subtitle: Text(widget.controller.isDirty ? "Unsaved changes" : "Saved"),
                trailing: Chip(label: Text(bundled ? "BUNDLED" : "LOCAL")),
              ),
            ),
            if (widget.controller.error != null)
              Padding(
                padding: const EdgeInsets.all(8),
                child: Text(widget.controller.error!, style: const TextStyle(color: Colors.redAccent)),
              ),
            Expanded(
              child: TabBarView(
                controller: _tabs,
                children: <Widget>[
                  _buildMetadataTab(recipe),
                  _EquipmentEditor(controller: widget.controller),
                  _IngredientsEditor(controller: widget.controller),
                  _StepsEditor(controller: widget.controller),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMetadataTab(RecipeDetail recipe) {
    return ListView(
      padding: const EdgeInsets.all(12),
      children: <Widget>[
        Text(
          "Start here",
          style: Theme.of(context).textTheme.labelLarge,
        ),
        const SizedBox(height: 6),
        TextField(
          controller: _title,
          enabled: widget.controller.canEdit,
          style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w600),
          decoration: const InputDecoration(
            labelText: "Recipe name",
            hintText: "Required",
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _notes,
          enabled: widget.controller.canEdit,
          maxLines: 5,
          decoration: const InputDecoration(
            labelText: "Notes",
            hintText: "Optional — tips, substitutions, or story",
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 8),
        ExpansionTile(
          title: const Text("More details"),
          subtitle: const Text("Optional — add when you are ready"),
          initiallyExpanded: false,
          children: <Widget>[
            TextField(controller: _subtitle, enabled: widget.controller.canEdit, decoration: const InputDecoration(labelText: "Subtitle")),
            TextField(controller: _author, enabled: widget.controller.canEdit, decoration: const InputDecoration(labelText: "Author")),
            TextField(controller: _sourceName, enabled: widget.controller.canEdit, decoration: const InputDecoration(labelText: "Source Name")),
            TextField(controller: _sourceUrl, enabled: widget.controller.canEdit, decoration: const InputDecoration(labelText: "Source URL")),
            DropdownButtonFormField<String>(
              initialValue: _status,
              decoration: const InputDecoration(labelText: "Status"),
              items: const <DropdownMenuItem<String>>[
                DropdownMenuItem<String>(value: "draft", child: Text("Draft")),
                DropdownMenuItem<String>(value: "published", child: Text("Published")),
                DropdownMenuItem<String>(value: "archived", child: Text("Archived")),
              ],
              onChanged: widget.controller.canEdit ? (String? value) => setState(() => _status = value ?? "draft") : null,
            ),
            DropdownButtonFormField<String>(
              initialValue: _difficulty.isEmpty ? null : _difficulty,
              decoration: const InputDecoration(labelText: "Difficulty"),
              items: const <DropdownMenuItem<String>>[
                DropdownMenuItem<String>(value: "easy", child: Text("Easy")),
                DropdownMenuItem<String>(value: "medium", child: Text("Medium")),
                DropdownMenuItem<String>(value: "hard", child: Text("Hard")),
              ],
              onChanged: widget.controller.canEdit ? (String? value) => setState(() => _difficulty = value ?? "") : null,
            ),
            TextField(controller: _servings, keyboardType: TextInputType.number, enabled: widget.controller.canEdit, decoration: const InputDecoration(labelText: "Servings")),
            TextField(controller: _prep, keyboardType: TextInputType.number, enabled: widget.controller.canEdit, decoration: const InputDecoration(labelText: "Prep Minutes")),
            TextField(controller: _cook, keyboardType: TextInputType.number, enabled: widget.controller.canEdit, decoration: const InputDecoration(labelText: "Cook Minutes")),
            TextField(controller: _total, keyboardType: TextInputType.number, enabled: widget.controller.canEdit, decoration: const InputDecoration(labelText: "Total Minutes")),
            const SizedBox(height: 8),
            Row(
              children: <Widget>[
                Expanded(
                  child: FilledButton.tonal(
                    onPressed: widget.controller.canEdit ? _attachCoverImageByPath : null,
                    child: Text(
                      widget.controller.recipe?.coverMediaId == null ? "Attach cover image" : "Replace cover image",
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                FilledButton.tonal(
                  onPressed: (widget.controller.canEdit && widget.controller.recipe?.coverMediaId != null)
                      ? () => widget.controller.removeCoverMedia()
                      : null,
                  child: const Text("Remove cover"),
                ),
              ],
            ),
          ],
        ),
        const SizedBox(height: 12),
        FilledButton(
          onPressed: widget.controller.canEdit ? _saveMetadataOnly : null,
          child: const Text("Apply metadata changes"),
        ),
      ],
    );
  }

  Future<void> _onSave() async {
    _saveMetadataOnly();
    final bool ok = await widget.controller.save();
    if (!mounted) {
      return;
    }
    if (ok) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Recipe saved")));
      Navigator.of(context).pop(widget.controller.recipe!.id);
    }
  }

  void _saveMetadataOnly() {
    widget.controller.updateMetadata(
      title: _title.text,
      subtitle: _subtitle.text,
      author: _author.text,
      sourceName: _sourceName.text,
      sourceUrl: _sourceUrl.text,
      notes: _notes.text,
      difficulty: _difficulty,
      status: _status,
      servings: double.tryParse(_servings.text),
      prepMinutes: int.tryParse(_prep.text),
      cookMinutes: int.tryParse(_cook.text),
      totalMinutes: int.tryParse(_total.text),
    );
  }

  Future<bool> _confirmDiscard(BuildContext context) async {
    final bool? result = await showDialog<bool>(
      context: context,
      builder: (BuildContext context) => AlertDialog(
        title: const Text("Discard changes?"),
        content: const Text("You have unsaved edits."),
        actions: <Widget>[
          TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text("Cancel")),
          FilledButton(onPressed: () => Navigator.of(context).pop(true), child: const Text("Discard")),
        ],
      ),
    );
    return result ?? false;
  }

  Future<void> _attachCoverImageByPath() async {
    final TextEditingController path = TextEditingController();
    final bool? ok = await showDialog<bool>(
      context: context,
      builder: (BuildContext context) => AlertDialog(
        title: const Text("Attach cover image"),
        content: TextField(
          controller: path,
          decoration: const InputDecoration(labelText: "Image file path"),
        ),
        actions: <Widget>[
          TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text("Cancel")),
          FilledButton(onPressed: () => Navigator.of(context).pop(true), child: const Text("Attach")),
        ],
      ),
    );
    if (ok == true && path.text.trim().isNotEmpty) {
      await widget.controller.attachCoverMediaFromPath(path.text.trim());
    }
  }
}

class _EquipmentEditor extends StatelessWidget {
  final RecipeEditorController controller;
  const _EquipmentEditor({required this.controller});
  @override
  Widget build(BuildContext context) {
    final List<RecipeEquipmentItem> items = controller.recipe?.equipment ?? const <RecipeEquipmentItem>[];
    return Column(children: <Widget>[
      Align(
        alignment: Alignment.centerRight,
        child: IconButton(
          onPressed: controller.canEdit ? () => _showEquipmentDialog(context, controller) : null,
          icon: const Icon(Icons.add),
        ),
      ),
      Expanded(
        child: ReorderableListView.builder(
          itemCount: items.length,
          onReorder: controller.canEdit ? controller.reorderEquipment : (_, __) {},
          itemBuilder: (BuildContext context, int index) {
            final RecipeEquipmentItem item = items[index];
            return ListTile(
              key: ValueKey<String>(item.id),
              title: Text(item.name),
              subtitle: Text(item.description ?? ""),
              trailing: Wrap(spacing: 4, children: <Widget>[
                IconButton(onPressed: controller.canEdit ? () => _showEquipmentDialog(context, controller, item: item) : null, icon: const Icon(Icons.edit)),
                IconButton(onPressed: controller.canEdit ? () => controller.deleteEquipment(item.id) : null, icon: const Icon(Icons.delete)),
              ]),
            );
          },
        ),
      ),
    ]);
  }
}

class _IngredientsEditor extends StatefulWidget {
  final RecipeEditorController controller;
  const _IngredientsEditor({required this.controller});

  @override
  State<_IngredientsEditor> createState() => _IngredientsEditorState();
}

class _IngredientsEditorState extends State<_IngredientsEditor> {
  final TextEditingController _quickLine = TextEditingController();

  @override
  void dispose() {
    _quickLine.dispose();
    super.dispose();
  }

  void _addQuickLine() {
    final String line = _quickLine.text.trim();
    if (line.isEmpty || !widget.controller.canEdit) {
      return;
    }
    widget.controller.addIngredient(rawText: line);
    _quickLine.clear();
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final List<RecipeIngredientItem> items = widget.controller.recipe?.ingredients ?? const <RecipeIngredientItem>[];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        if (widget.controller.canEdit)
          Padding(
            padding: const EdgeInsets.fromLTRB(8, 8, 8, 0),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Expanded(
                  child: TextField(
                    controller: _quickLine,
                    textInputAction: TextInputAction.done,
                    onSubmitted: (_) => _addQuickLine(),
                    decoration: const InputDecoration(
                      labelText: "Add ingredient",
                      hintText: "e.g. 2 cups flour",
                      border: OutlineInputBorder(),
                    ),
                  ),
                ),
                IconButton(
                  tooltip: "Add line",
                  onPressed: _addQuickLine,
                  icon: const Icon(Icons.add_circle_outline),
                ),
              ],
            ),
          ),
        Align(
          alignment: Alignment.centerRight,
          child: TextButton.icon(
            onPressed: widget.controller.canEdit ? () => _showIngredientDialog(context, widget.controller) : null,
            icon: const Icon(Icons.tune, size: 18),
            label: const Text("Structured row"),
          ),
        ),
        Expanded(
          child: ReorderableListView.builder(
            itemCount: items.length,
            onReorder: widget.controller.canEdit ? widget.controller.reorderIngredients : (_, __) {},
            itemBuilder: (BuildContext context, int index) {
              final RecipeIngredientItem item = items[index];
              final String structured = <String>[
                if (item.quantityValue != null) item.quantityValue.toString(),
                item.unit ?? "",
                item.ingredientName ?? "",
              ].join(" ").trim();
              return ListTile(
                key: ValueKey<String>(item.id),
                title: Text(item.rawText),
                subtitle: structured.isEmpty ? const Text("Tap edit to split quantity, unit, or name", style: TextStyle(fontSize: 12)) : Text(structured),
                trailing: Wrap(
                  spacing: 4,
                  children: <Widget>[
                    IconButton(
                      onPressed: widget.controller.canEdit ? () => _showIngredientDialog(context, widget.controller, item: item) : null,
                      icon: const Icon(Icons.edit_outlined),
                    ),
                    IconButton(
                      onPressed: widget.controller.canEdit ? () => widget.controller.deleteIngredient(item.id) : null,
                      icon: const Icon(Icons.delete_outline),
                    ),
                  ],
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}

class _StepsEditor extends StatelessWidget {
  final RecipeEditorController controller;
  const _StepsEditor({required this.controller});
  @override
  Widget build(BuildContext context) {
    final RecipeDetail? recipe = controller.recipe;
    final List<RecipeStep> steps = recipe?.steps ?? const <RecipeStep>[];
    return Column(children: <Widget>[
      Align(
        alignment: Alignment.centerRight,
        child: IconButton(
          onPressed: controller.canEdit ? () => _showStepDialog(context, controller) : null,
          icon: const Icon(Icons.add),
        ),
      ),
      Expanded(
        child: ReorderableListView.builder(
          itemCount: steps.length,
          onReorder: controller.canEdit ? controller.reorderSteps : (_, __) {},
          itemBuilder: (BuildContext context, int index) {
            final RecipeStep step = steps[index];
            final int linkCount = recipe?.stepLinks.where((StepLink link) => link.stepId == step.id).length ?? 0;
            final List<String> hints = <String>[step.stepType];
            if (step.timers.isNotEmpty) {
              hints.add("${step.timers.length} timer(s)");
            }
            if (linkCount > 0) {
              hints.add("$linkCount link(s)");
            }
            return ListTile(
              key: ValueKey<String>(step.id),
              title: Text(step.title ?? "Step ${index + 1}"),
              subtitle: Text(hints.join(" • ")),
              onTap: () => _showStepDialog(context, controller, step: step),
              trailing: IconButton(
                onPressed: controller.canEdit ? () => controller.deleteStep(step.id) : null,
                icon: const Icon(Icons.delete),
              ),
            );
          },
        ),
      ),
    ]);
  }
}

Future<void> _showEquipmentDialog(BuildContext context, RecipeEditorController controller, {RecipeEquipmentItem? item}) async {
  final TextEditingController name = TextEditingController(text: item?.name ?? "");
  final TextEditingController description = TextEditingController(text: item?.description ?? "");
  final TextEditingController notes = TextEditingController(text: item?.notes ?? "");
  final TextEditingController affiliate = TextEditingController(text: item?.affiliateUrl ?? "");
  bool required = item?.isRequired ?? true;
  await showDialog<void>(
    context: context,
    builder: (BuildContext context) => AlertDialog(
      title: Text(item == null ? "Add Equipment" : "Edit Equipment"),
      content: StatefulBuilder(
        builder: (BuildContext context, void Function(void Function()) setState) => SingleChildScrollView(
          child: Column(mainAxisSize: MainAxisSize.min, children: <Widget>[
            TextField(controller: name, decoration: const InputDecoration(labelText: "Name")),
            TextField(controller: description, decoration: const InputDecoration(labelText: "Description")),
            TextField(controller: notes, decoration: const InputDecoration(labelText: "Notes")),
            TextField(controller: affiliate, decoration: const InputDecoration(labelText: "Affiliate URL")),
            SwitchListTile(
              value: required,
              title: const Text("Required"),
              onChanged: (bool value) => setState(() => required = value),
            ),
          ]),
        ),
      ),
      actions: <Widget>[
        TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text("Cancel")),
        FilledButton(
          onPressed: () {
            if (item == null) {
              controller.addEquipment(
                name: name.text,
                description: description.text,
                notes: notes.text,
                affiliateUrl: affiliate.text,
                isRequired: required,
              );
            } else {
              controller.updateEquipment(
                item.id,
                name: name.text,
                description: description.text,
                notes: notes.text,
                affiliateUrl: affiliate.text,
                isRequired: required,
              );
            }
            Navigator.of(context).pop();
          },
          child: const Text("Apply"),
        ),
      ],
    ),
  );
}

Future<void> _showIngredientDialog(BuildContext context, RecipeEditorController controller, {RecipeIngredientItem? item}) async {
  final TextEditingController raw = TextEditingController(text: item?.rawText ?? "");
  final TextEditingController qty = TextEditingController(text: item?.quantityValue?.toString() ?? "");
  final TextEditingController unit = TextEditingController(text: item?.unit ?? "");
  final TextEditingController name = TextEditingController(text: item?.ingredientName ?? "");
  final TextEditingController sub = TextEditingController(text: item?.substitutions ?? "");
  final TextEditingController prep = TextEditingController(text: item?.preparationNotes ?? "");
  bool optional = item?.isOptional ?? false;
  await showDialog<void>(
    context: context,
    builder: (BuildContext context) => AlertDialog(
      title: Text(item == null ? "Add Ingredient" : "Edit Ingredient"),
      content: StatefulBuilder(
        builder: (BuildContext context, void Function(void Function()) setState) => SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              TextField(
                controller: raw,
                decoration: const InputDecoration(
                  labelText: "Ingredient line",
                  hintText: "e.g. 2 cups flour, sifted",
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 8),
              ExpansionTile(
                title: const Text("Structured fields"),
                subtitle: const Text("Optional — split quantity, unit, and name"),
                initiallyExpanded: false,
                children: <Widget>[
                  TextField(controller: qty, decoration: const InputDecoration(labelText: "Quantity")),
                  TextField(controller: unit, decoration: const InputDecoration(labelText: "Unit")),
                  TextField(controller: name, decoration: const InputDecoration(labelText: "Name")),
                  TextField(controller: sub, decoration: const InputDecoration(labelText: "Substitutions")),
                  TextField(controller: prep, decoration: const InputDecoration(labelText: "Preparation notes")),
                  SwitchListTile(
                    value: optional,
                    title: const Text("Optional ingredient"),
                    onChanged: (bool value) => setState(() => optional = value),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
      actions: <Widget>[
        TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text("Cancel")),
        FilledButton(
          onPressed: () {
            if (item == null) {
              controller.addIngredient(
                rawText: raw.text,
                quantityValue: double.tryParse(qty.text),
                unit: unit.text,
                ingredientName: name.text,
                substitutions: sub.text,
                preparationNotes: prep.text,
                isOptional: optional,
              );
            } else {
              controller.updateIngredient(
                item.id,
                rawText: raw.text,
                quantityValue: double.tryParse(qty.text),
                unit: unit.text,
                ingredientName: name.text,
                substitutions: sub.text,
                preparationNotes: prep.text,
                isOptional: optional,
              );
            }
            Navigator.of(context).pop();
          },
          child: const Text("Apply"),
        ),
      ],
    ),
  );
}

Future<void> _showStepDialog(BuildContext context, RecipeEditorController controller, {RecipeStep? step}) async {
  final RecipeDetail? recipe = controller.recipe;
  if (recipe == null) {
    return;
  }
  final TextEditingController title = TextEditingController(text: step?.title ?? "");
  final TextEditingController body = TextEditingController(text: step?.bodyText ?? "");
  final TextEditingController estimate = TextEditingController(text: step?.estimatedSeconds?.toString() ?? "");
  String stepType = step?.stepType ?? "instruction";

  await showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    builder: (BuildContext context) {
      return StatefulBuilder(
        builder: (BuildContext context, void Function(void Function()) setState) {
          final RecipeStep? stepValue = step == null
              ? null
              : (controller.recipe?.steps.where((RecipeStep s) => s.id == step.id).isNotEmpty ?? false)
                  ? controller.recipe!.steps.firstWhere((RecipeStep s) => s.id == step.id)
                  : null;
          final List<StepLink> links = stepValue == null
              ? const <StepLink>[]
              : recipe.stepLinks.where((StepLink link) => link.stepId == stepValue.id).toList();
          return Padding(
            padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
            child: ListView(
              shrinkWrap: true,
              padding: const EdgeInsets.all(16),
              children: <Widget>[
                Text(step == null ? "Add Step" : "Edit Step", style: Theme.of(context).textTheme.titleLarge),
                TextField(controller: title, decoration: const InputDecoration(labelText: "Title")),
                TextField(controller: body, maxLines: 4, decoration: const InputDecoration(labelText: "Body")),
                DropdownButtonFormField<String>(
                initialValue: stepType,
                  decoration: const InputDecoration(labelText: "Step Type"),
                  items: const <DropdownMenuItem<String>>[
                    DropdownMenuItem<String>(value: "instruction", child: Text("Instruction")),
                    DropdownMenuItem<String>(value: "note", child: Text("Note")),
                    DropdownMenuItem<String>(value: "section_break", child: Text("Section Break")),
                  ],
                  onChanged: (String? value) => setState(() => stepType = value ?? "instruction"),
                ),
                TextField(controller: estimate, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: "Estimated Seconds")),
                const SizedBox(height: 8),
                FilledButton(
                  onPressed: () {
                    if (step == null) {
                      controller.addStep(
                        title: title.text,
                        bodyText: body.text,
                        stepType: stepType,
                        estimatedSeconds: int.tryParse(estimate.text),
                      );
                    } else {
                      controller.updateStep(
                        step.id,
                        title: title.text,
                        bodyText: body.text,
                        stepType: stepType,
                        estimatedSeconds: int.tryParse(estimate.text),
                      );
                    }
                    Navigator.of(context).pop();
                  },
                  child: const Text("Apply Step"),
                ),
                if (stepValue != null) ...<Widget>[
                  const Divider(),
                  ExpansionTile(
                    initiallyExpanded: false,
                    title: const Text("Optional — links, timers & image"),
                    subtitle: const Text("Jump to another ingredient or step, add a timer, or attach a photo"),
                    children: <Widget>[
                      Text("Links", style: Theme.of(context).textTheme.titleSmall),
                      ...links.map(
                        (StepLink link) => ListTile(
                          title: Text("${link.targetType}:${link.tokenKey}"),
                          subtitle: Text(link.labelOverride ?? link.labelSnapshot),
                          trailing: IconButton(
                            onPressed: () {
                              controller.removeStepLink(link.id);
                              setState(() {});
                            },
                            icon: const Icon(Icons.delete),
                          ),
                          onTap: () async {
                            await _showLinkDialog(context, controller, stepValue, recipe, existing: link);
                            setState(() {});
                          },
                        ),
                      ),
                      TextButton(
                        onPressed: () async {
                          await _showLinkDialog(context, controller, stepValue, recipe);
                          setState(() {});
                        },
                        child: const Text("Add link"),
                      ),
                      const Divider(height: 24),
                      Text("Timers", style: Theme.of(context).textTheme.titleSmall),
                      ...stepValue.timers.map(
                        (StepTimer timer) => ListTile(
                          title: Text(timer.label),
                          subtitle: Text("${timer.durationSeconds}s ${timer.autoStart ? "auto" : "manual"}"),
                          trailing: IconButton(
                            onPressed: () {
                              controller.removeTimer(stepId: stepValue.id, timerId: timer.id);
                              setState(() {});
                            },
                            icon: const Icon(Icons.delete),
                          ),
                          onTap: () async {
                            await _showTimerDialog(context, controller, stepValue, existing: timer);
                            setState(() {});
                          },
                        ),
                      ),
                      TextButton(
                        onPressed: () async {
                          await _showTimerDialog(context, controller, stepValue);
                          setState(() {});
                        },
                        child: const Text("Add timer"),
                      ),
                      const Divider(height: 24),
                      Text("Step image", style: Theme.of(context).textTheme.titleSmall),
                      ListTile(
                        title: Text(stepValue.mediaId == null ? "No image attached" : "Media ID: ${stepValue.mediaId}"),
                        trailing: Wrap(
                          spacing: 4,
                          children: <Widget>[
                            TextButton(
                              onPressed: () async {
                                final TextEditingController path = TextEditingController();
                                final bool? ok = await showDialog<bool>(
                                  context: context,
                                  builder: (BuildContext context) => AlertDialog(
                                    title: const Text("Attach step image"),
                                    content: TextField(
                                      controller: path,
                                      decoration: const InputDecoration(labelText: "Image file path"),
                                    ),
                                    actions: <Widget>[
                                      TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text("Cancel")),
                                      FilledButton(onPressed: () => Navigator.of(context).pop(true), child: const Text("Attach")),
                                    ],
                                  ),
                                );
                                if (ok == true && path.text.trim().isNotEmpty) {
                                  await controller.attachStepMediaFromPath(stepId: stepValue.id, sourcePath: path.text.trim());
                                  setState(() {});
                                }
                              },
                              child: const Text("Attach"),
                            ),
                            TextButton(
                              onPressed: stepValue.mediaId == null
                                  ? null
                                  : () async {
                                      await controller.removeStepMedia(stepValue.id);
                                      setState(() {});
                                    },
                              child: const Text("Remove"),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text("Preview", style: Theme.of(context).textTheme.titleMedium),
                  Wrap(
                    spacing: 4,
                    children: resolveStepTextSegments(recipe, stepValue).segments
                        .map((ResolvedStepSegment segment) => segment.isLink
                            ? Chip(label: Text(segment.text))
                            : Text(segment.text))
                        .toList(),
                  ),
                ],
              ],
            ),
          );
        },
      );
    },
  );
}

Future<void> _showLinkDialog(
  BuildContext context,
  RecipeEditorController controller,
  RecipeStep step,
  RecipeDetail recipe, {
  StepLink? existing,
}) async {
  String targetType = existing?.targetType ?? "ingredient";
  String? targetId = existing?.targetId;
  final TextEditingController token = TextEditingController(text: existing?.tokenKey ?? "");
  final TextEditingController label = TextEditingController(text: existing?.labelOverride ?? "");

  await showDialog<void>(
    context: context,
    builder: (BuildContext context) => StatefulBuilder(
      builder: (BuildContext context, void Function(void Function()) setState) {
        final List<DropdownMenuItem<String>> targetItems = (targetType == "ingredient"
                ? recipe.ingredients.map((RecipeIngredientItem item) => DropdownMenuItem<String>(value: item.id, child: Text(item.ingredientName ?? item.rawText)))
                : recipe.equipment.map((RecipeEquipmentItem item) => DropdownMenuItem<String>(value: item.id, child: Text(item.name))))
            .toList();
        targetId ??= targetItems.isNotEmpty ? targetItems.first.value : null;
        return AlertDialog(
          title: Text(existing == null ? "Add Link" : "Edit Link"),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              DropdownButtonFormField<String>(
                initialValue: targetType,
                decoration: const InputDecoration(labelText: "Target Type"),
                items: const <DropdownMenuItem<String>>[
                  DropdownMenuItem<String>(value: "ingredient", child: Text("Ingredient")),
                  DropdownMenuItem<String>(value: "equipment", child: Text("Equipment")),
                ],
                onChanged: (String? value) => setState(() {
                  targetType = value ?? "ingredient";
                  targetId = null;
                }),
              ),
              DropdownButtonFormField<String>(
                initialValue: targetId,
                decoration: const InputDecoration(labelText: "Target"),
                items: targetItems,
                onChanged: (String? value) => setState(() => targetId = value),
              ),
              TextField(controller: token, decoration: const InputDecoration(labelText: "Token Key")),
              TextField(controller: label, decoration: const InputDecoration(labelText: "Label Override")),
            ],
          ),
          actions: <Widget>[
            TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text("Cancel")),
            FilledButton(
              onPressed: targetId == null
                  ? null
                  : () {
                      controller.addOrUpdateStepLink(
                        linkId: existing?.id,
                        stepId: step.id,
                        targetType: targetType,
                        targetId: targetId!,
                        tokenKey: token.text,
                        labelOverride: label.text,
                      );
                      Navigator.of(context).pop();
                    },
              child: const Text("Apply"),
            ),
          ],
        );
      },
    ),
  );
}

Future<void> _showTimerDialog(BuildContext context, RecipeEditorController controller, RecipeStep step, {StepTimer? existing}) async {
  final TextEditingController label = TextEditingController(text: existing?.label ?? "");
  final TextEditingController duration = TextEditingController(text: existing?.durationSeconds.toString() ?? "60");
  final TextEditingController sound = TextEditingController(text: existing?.alertSoundKey ?? "");
  bool autoStart = existing?.autoStart ?? false;
  await showDialog<void>(
    context: context,
    builder: (BuildContext context) => StatefulBuilder(
      builder: (BuildContext context, void Function(void Function()) setState) => AlertDialog(
        title: Text(existing == null ? "Add Timer" : "Edit Timer"),
        content: Column(mainAxisSize: MainAxisSize.min, children: <Widget>[
          TextField(controller: label, decoration: const InputDecoration(labelText: "Label")),
          TextField(controller: duration, decoration: const InputDecoration(labelText: "Duration Seconds")),
          TextField(controller: sound, decoration: const InputDecoration(labelText: "Alert Sound Key")),
          SwitchListTile(value: autoStart, title: const Text("Auto Start"), onChanged: (bool value) => setState(() => autoStart = value)),
        ]),
        actions: <Widget>[
          TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text("Cancel")),
          FilledButton(
            onPressed: () {
              final int secs = int.tryParse(duration.text) ?? 60;
              if (existing == null) {
                controller.addTimer(
                  stepId: step.id,
                  label: label.text,
                  durationSeconds: secs,
                  autoStart: autoStart,
                  alertSoundKey: sound.text,
                );
              } else {
                controller.updateTimer(
                  stepId: step.id,
                  timerId: existing.id,
                  label: label.text,
                  durationSeconds: secs,
                  autoStart: autoStart,
                  alertSoundKey: sound.text,
                );
              }
              Navigator.of(context).pop();
            },
            child: const Text("Apply"),
          ),
        ],
      ),
    ),
  );
}
