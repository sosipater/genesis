import "package:flutter/foundation.dart";
import "package:uuid/uuid.dart";

import "../../data/models/recipe_models.dart";
import "../../data/repositories/recipe_editor_repository_port.dart";
import "../media/mobile_media_service.dart";
import "recipe_editor_service.dart";

class RecipeEditorController extends ChangeNotifier {
  final RecipeEditorRepositoryPort _repository;
  final RecipeEditorService _service;
  final MobileMediaService? _mediaService;
  final Uuid _uuid;

  bool loading = false;
  bool saving = false;
  bool isDirty = false;
  bool wasBundledAtLoad = false;
  String? error;
  RecipeDetail? _original;
  RecipeDetail? _draft;

  RecipeEditorController(
    this._repository, {
    RecipeEditorService? service,
    MobileMediaService? mediaService,
    Uuid? uuid,
  })  : _service = service ?? RecipeEditorService(),
        _mediaService = mediaService,
        _uuid = uuid ?? const Uuid();

  RecipeDetail? get recipe => _draft;
  bool get canEdit => (_draft?.scope ?? "local") == "local";

  Future<void> createNew() async {
    loading = true;
    error = null;
    notifyListeners();
    _draft = _service.createEmptyRecipe();
    _original = _draft;
    isDirty = false;
    wasBundledAtLoad = false;
    loading = false;
    notifyListeners();
  }

  Future<void> load(String recipeId) async {
    loading = true;
    error = null;
    notifyListeners();
    try {
      final RecipeDetail? loaded = await _repository.getRecipeById(recipeId);
      if (loaded == null) {
        throw StateError("Recipe not found");
      }
      _draft = loaded;
      _original = loaded;
      isDirty = false;
      wasBundledAtLoad = loaded.scope == "bundled";
    } catch (e) {
      error = "$e";
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<void> duplicateAsLocal() async {
    if (_draft == null || _draft!.scope != "bundled") {
      return;
    }
    _draft = _service.duplicateBundledAsLocal(_draft!);
    isDirty = true;
    notifyListeners();
  }

  void discardChanges() {
    if (_original == null) {
      return;
    }
    _draft = _original;
    isDirty = false;
    notifyListeners();
  }

  Future<bool> save() async {
    final RecipeDetail? draft = _draft;
    if (draft == null) {
      return false;
    }
    if (draft.scope != "local") {
      error = "Bundled recipes are read-only. Duplicate to local first.";
      notifyListeners();
      return false;
    }
    if (draft.title.trim().isEmpty) {
      error = "Title is required";
      notifyListeners();
      return false;
    }
    saving = true;
    error = null;
    notifyListeners();
    try {
      final RecipeDetail normalized = _service.normalizeOrders(draft);
      final String now = DateTime.now().toUtc().toIso8601String();
      await _repository.upsertRecipeGraph(normalized, updatedAt: now);
      _draft = normalized;
      _original = normalized;
      isDirty = false;
      return true;
    } catch (e) {
      error = "$e";
      return false;
    } finally {
      saving = false;
      notifyListeners();
    }
  }

  void updateMetadata({
    required String title,
    String? subtitle,
    String? author,
    String? sourceName,
    String? sourceUrl,
    String? notes,
    String? difficulty,
    String? status,
    double? servings,
    int? prepMinutes,
    int? cookMinutes,
    int? totalMinutes,
  }) {
    final RecipeDetail? current = _draft;
    if (current == null || !canEdit) {
      return;
    }
    _draft = RecipeDetail(
      id: current.id,
      title: title.trim(),
      subtitle: _nullable(subtitle),
      scope: current.scope,
      status: _nullable(status) ?? current.status,
      author: _nullable(author),
      sourceName: _nullable(sourceName),
      sourceUrl: _nullable(sourceUrl),
      difficulty: _nullable(difficulty),
      notes: _nullable(notes),
      servings: servings,
      prepMinutes: prepMinutes,
      cookMinutes: cookMinutes,
      totalMinutes: totalMinutes,
      coverMediaId: current.coverMediaId,
      equipment: current.equipment,
      ingredients: current.ingredients,
      steps: current.steps,
      stepLinks: current.stepLinks,
    );
    _markDirty();
  }

  void addEquipment({
    required String name,
    String? description,
    String? notes,
    String? affiliateUrl,
    bool isRequired = true,
  }) {
    final RecipeDetail? current = _draft;
    if (current == null || !canEdit) {
      return;
    }
    final List<RecipeEquipmentItem> next = <RecipeEquipmentItem>[
      ...current.equipment,
      RecipeEquipmentItem(
        id: _uuid.v4(),
        recipeId: current.id,
        name: name.trim(),
        description: _nullable(description),
        notes: _nullable(notes),
        affiliateUrl: _nullable(affiliateUrl),
        mediaId: null,
        isRequired: isRequired,
        displayOrder: current.equipment.length,
      ),
    ];
    _updateRecipe(current, equipment: next);
  }

  void updateEquipment(
    String equipmentId, {
    required String name,
    String? description,
    String? notes,
    String? affiliateUrl,
    required bool isRequired,
  }) {
    final RecipeDetail? current = _draft;
    if (current == null || !canEdit) {
      return;
    }
    final List<RecipeEquipmentItem> next = current.equipment
        .map(
          (RecipeEquipmentItem item) => item.id == equipmentId
              ? RecipeEquipmentItem(
                  id: item.id,
                  recipeId: item.recipeId,
                  name: name.trim(),
                  description: _nullable(description),
                  notes: _nullable(notes),
                  affiliateUrl: _nullable(affiliateUrl),
                  mediaId: item.mediaId,
                  isRequired: isRequired,
                  displayOrder: item.displayOrder,
                )
              : item,
        )
        .toList();
    _updateRecipe(current, equipment: next);
  }

  void deleteEquipment(String equipmentId) {
    final RecipeDetail? current = _draft;
    if (current == null || !canEdit) {
      return;
    }
    final List<RecipeEquipmentItem> next = current.equipment.where((RecipeEquipmentItem item) => item.id != equipmentId).toList();
    final List<StepLink> links = current.stepLinks
        .where((StepLink link) => !(link.targetType == "equipment" && link.targetId == equipmentId))
        .toList();
    _updateRecipe(current, equipment: next, stepLinks: links);
  }

  void reorderEquipment(int oldIndex, int newIndex) {
    final RecipeDetail? current = _draft;
    if (current == null || !canEdit) {
      return;
    }
    final List<RecipeEquipmentItem> next = List<RecipeEquipmentItem>.from(current.equipment);
    if (newIndex > oldIndex) {
      newIndex -= 1;
    }
    final RecipeEquipmentItem moved = next.removeAt(oldIndex);
    next.insert(newIndex, moved);
    _updateRecipe(current, equipment: next);
  }

  void addIngredient({
    required String rawText,
    double? quantityValue,
    String? unit,
    String? ingredientName,
    String? substitutions,
    String? preparationNotes,
    bool isOptional = false,
  }) {
    final RecipeDetail? current = _draft;
    if (current == null || !canEdit) {
      return;
    }
    final List<RecipeIngredientItem> next = <RecipeIngredientItem>[
      ...current.ingredients,
      RecipeIngredientItem(
        id: _uuid.v4(),
        recipeId: current.id,
        rawText: rawText.trim(),
        quantityValue: quantityValue,
        unit: _nullable(unit),
        ingredientName: _nullable(ingredientName),
        substitutions: _nullable(substitutions),
        preparationNotes: _nullable(preparationNotes),
        mediaId: null,
        isOptional: isOptional,
        displayOrder: current.ingredients.length,
      ),
    ];
    _updateRecipe(current, ingredients: next);
  }

  void updateIngredient(
    String ingredientId, {
    required String rawText,
    double? quantityValue,
    String? unit,
    String? ingredientName,
    String? substitutions,
    String? preparationNotes,
    required bool isOptional,
  }) {
    final RecipeDetail? current = _draft;
    if (current == null || !canEdit) {
      return;
    }
    final List<RecipeIngredientItem> next = current.ingredients
        .map(
          (RecipeIngredientItem item) => item.id == ingredientId
              ? RecipeIngredientItem(
                  id: item.id,
                  recipeId: item.recipeId,
                  rawText: rawText.trim(),
                  quantityValue: quantityValue,
                  unit: _nullable(unit),
                  ingredientName: _nullable(ingredientName),
                  substitutions: _nullable(substitutions),
                  preparationNotes: _nullable(preparationNotes),
                  mediaId: item.mediaId,
                  isOptional: isOptional,
                  displayOrder: item.displayOrder,
                )
              : item,
        )
        .toList();
    _updateRecipe(current, ingredients: next);
  }

  void deleteIngredient(String ingredientId) {
    final RecipeDetail? current = _draft;
    if (current == null || !canEdit) {
      return;
    }
    final List<RecipeIngredientItem> next = current.ingredients.where((RecipeIngredientItem item) => item.id != ingredientId).toList();
    final List<StepLink> links = current.stepLinks
        .where((StepLink link) => !(link.targetType == "ingredient" && link.targetId == ingredientId))
        .toList();
    _updateRecipe(current, ingredients: next, stepLinks: links);
  }

  void reorderIngredients(int oldIndex, int newIndex) {
    final RecipeDetail? current = _draft;
    if (current == null || !canEdit) {
      return;
    }
    final List<RecipeIngredientItem> next = List<RecipeIngredientItem>.from(current.ingredients);
    if (newIndex > oldIndex) {
      newIndex -= 1;
    }
    final RecipeIngredientItem moved = next.removeAt(oldIndex);
    next.insert(newIndex, moved);
    _updateRecipe(current, ingredients: next);
  }

  void addStep({
    String? title,
    required String bodyText,
    String stepType = "instruction",
    int? estimatedSeconds,
  }) {
    final RecipeDetail? current = _draft;
    if (current == null || !canEdit) {
      return;
    }
    final List<RecipeStep> next = <RecipeStep>[
      ...current.steps,
      RecipeStep(
        id: _uuid.v4(),
        recipeId: current.id,
        title: _nullable(title),
        bodyText: bodyText.trim(),
        stepType: stepType,
        estimatedSeconds: estimatedSeconds,
        mediaId: null,
        displayOrder: current.steps.length,
      ),
    ];
    _updateRecipe(current, steps: next);
  }

  void updateStep(
    String stepId, {
    String? title,
    required String bodyText,
    required String stepType,
    int? estimatedSeconds,
  }) {
    final RecipeDetail? current = _draft;
    if (current == null || !canEdit) {
      return;
    }
    final List<RecipeStep> next = current.steps
        .map(
          (RecipeStep step) => step.id == stepId
              ? RecipeStep(
                  id: step.id,
                  recipeId: step.recipeId,
                  title: _nullable(title),
                  bodyText: bodyText.trim(),
                  stepType: stepType,
                  estimatedSeconds: estimatedSeconds,
                  mediaId: step.mediaId,
                  displayOrder: step.displayOrder,
                  timers: step.timers,
                )
              : step,
        )
        .toList();
    _updateRecipe(current, steps: next);
  }

  void deleteStep(String stepId) {
    final RecipeDetail? current = _draft;
    if (current == null || !canEdit) {
      return;
    }
    final List<RecipeStep> next = current.steps.where((RecipeStep step) => step.id != stepId).toList();
    final List<StepLink> links = current.stepLinks.where((StepLink link) => link.stepId != stepId).toList();
    _updateRecipe(current, steps: next, stepLinks: links);
  }

  void reorderSteps(int oldIndex, int newIndex) {
    final RecipeDetail? current = _draft;
    if (current == null || !canEdit) {
      return;
    }
    final List<RecipeStep> next = List<RecipeStep>.from(current.steps);
    if (newIndex > oldIndex) {
      newIndex -= 1;
    }
    final RecipeStep moved = next.removeAt(oldIndex);
    next.insert(newIndex, moved);
    _updateRecipe(current, steps: next);
  }

  void addOrUpdateStepLink({
    String? linkId,
    required String stepId,
    required String targetType,
    required String targetId,
    required String tokenKey,
    String? labelOverride,
  }) {
    final RecipeDetail? current = _draft;
    if (current == null || !canEdit) {
      return;
    }
    final RecipeStep? step = _findStep(current, stepId);
    if (step == null) {
      return;
    }
    final List<StepLink> links = List<StepLink>.from(current.stepLinks);
    String bodyText = step.bodyText;
    final int existingIdx = linkId == null ? -1 : links.indexWhere((StepLink l) => l.id == linkId);
    if (existingIdx >= 0) {
      final StepLink existing = links[existingIdx];
      final StepLink next = StepLink(
        id: existing.id,
        stepId: stepId,
        targetType: targetType,
        targetId: targetId,
        tokenKey: tokenKey.trim(),
        labelSnapshot: _labelForTarget(current, targetType, targetId),
        labelOverride: _nullable(labelOverride),
      );
      bodyText = _service.syncBodyForLinkToken(
        bodyText: bodyText,
        oldTokenKey: existing.tokenKey,
        tokenKey: next.tokenKey,
        targetType: next.targetType,
      );
      links[existingIdx] = next;
    } else {
      final StepLink next = _service.createStepLink(
        recipe: current,
        step: step,
        targetType: targetType,
        targetId: targetId,
        tokenKey: tokenKey.trim(),
        labelOverride: labelOverride,
      );
      bodyText = _service.syncBodyForLinkToken(
        bodyText: bodyText,
        tokenKey: next.tokenKey,
        targetType: next.targetType,
      );
      links.add(next);
    }
    final List<RecipeStep> steps = current.steps
        .map((RecipeStep s) => s.id == stepId
            ? RecipeStep(
                id: s.id,
                recipeId: s.recipeId,
                title: s.title,
                bodyText: bodyText,
                stepType: s.stepType,
                estimatedSeconds: s.estimatedSeconds,
                mediaId: s.mediaId,
                displayOrder: s.displayOrder,
                timers: s.timers,
              )
            : s)
        .toList();
    _updateRecipe(current, steps: steps, stepLinks: links);
  }

  void removeStepLink(String linkId) {
    final RecipeDetail? current = _draft;
    if (current == null || !canEdit) {
      return;
    }
    final StepLink? link = _findLink(current, linkId);
    if (link == null) {
      return;
    }
    final List<StepLink> links = current.stepLinks.where((StepLink l) => l.id != linkId).toList();
    final List<RecipeStep> steps = current.steps
        .map((RecipeStep step) => step.id == link.stepId
            ? RecipeStep(
                id: step.id,
                recipeId: step.recipeId,
                title: step.title,
                bodyText: _service.removeLinkTokenFromBody(
                  bodyText: step.bodyText,
                  targetType: link.targetType,
                  tokenKey: link.tokenKey,
                ),
                stepType: step.stepType,
                estimatedSeconds: step.estimatedSeconds,
                mediaId: step.mediaId,
                displayOrder: step.displayOrder,
                timers: step.timers,
              )
            : step)
        .toList();
    _updateRecipe(current, steps: steps, stepLinks: links);
  }

  void addTimer({
    required String stepId,
    required String label,
    required int durationSeconds,
    bool autoStart = false,
    String? alertSoundKey,
  }) {
    final RecipeDetail? current = _draft;
    if (current == null || !canEdit) {
      return;
    }
    final List<RecipeStep> steps = current.steps
        .map(
          (RecipeStep step) => step.id == stepId
              ? RecipeStep(
                  id: step.id,
                  recipeId: step.recipeId,
                  title: step.title,
                  bodyText: step.bodyText,
                  stepType: step.stepType,
                  estimatedSeconds: step.estimatedSeconds,
                  mediaId: step.mediaId,
                  displayOrder: step.displayOrder,
                  timers: <StepTimer>[
                    ...step.timers,
                    StepTimer(
                      id: _uuid.v4(),
                      stepId: stepId,
                      label: label.trim(),
                      durationSeconds: durationSeconds,
                      autoStart: autoStart,
                      alertSoundKey: _nullable(alertSoundKey),
                    ),
                  ],
                )
              : step,
        )
        .toList();
    _updateRecipe(current, steps: steps);
  }

  void updateTimer({
    required String stepId,
    required String timerId,
    required String label,
    required int durationSeconds,
    required bool autoStart,
    String? alertSoundKey,
  }) {
    final RecipeDetail? current = _draft;
    if (current == null || !canEdit) {
      return;
    }
    final List<RecipeStep> steps = current.steps
        .map(
          (RecipeStep step) => step.id == stepId
              ? RecipeStep(
                  id: step.id,
                  recipeId: step.recipeId,
                  title: step.title,
                  bodyText: step.bodyText,
                  stepType: step.stepType,
                  estimatedSeconds: step.estimatedSeconds,
                  mediaId: step.mediaId,
                  displayOrder: step.displayOrder,
                  timers: step.timers
                      .map(
                        (StepTimer timer) => timer.id == timerId
                            ? StepTimer(
                                id: timer.id,
                                stepId: step.id,
                                label: label.trim(),
                                durationSeconds: durationSeconds,
                                autoStart: autoStart,
                                alertSoundKey: _nullable(alertSoundKey),
                              )
                            : timer,
                      )
                      .toList(),
                )
              : step,
        )
        .toList();
    _updateRecipe(current, steps: steps);
  }

  void removeTimer({required String stepId, required String timerId}) {
    final RecipeDetail? current = _draft;
    if (current == null || !canEdit) {
      return;
    }
    final List<RecipeStep> steps = current.steps
        .map(
          (RecipeStep step) => step.id == stepId
              ? RecipeStep(
                  id: step.id,
                  recipeId: step.recipeId,
                  title: step.title,
                  bodyText: step.bodyText,
                  stepType: step.stepType,
                  estimatedSeconds: step.estimatedSeconds,
                  mediaId: step.mediaId,
                  displayOrder: step.displayOrder,
                  timers: step.timers.where((StepTimer timer) => timer.id != timerId).toList(),
                )
              : step,
        )
        .toList();
    _updateRecipe(current, steps: steps);
  }

  Future<void> attachCoverMediaFromPath(String sourcePath) async {
    final RecipeDetail? current = _draft;
    if (current == null || !canEdit || _mediaService == null) {
      return;
    }
    final MediaAsset asset = await _mediaService.importFromPath(
      ownerType: "recipe_cover",
      ownerId: current.id,
      sourcePath: sourcePath,
    );
    _draft = RecipeDetail(
      id: current.id,
      title: current.title,
      subtitle: current.subtitle,
      scope: current.scope,
      status: current.status,
      author: current.author,
      sourceName: current.sourceName,
      sourceUrl: current.sourceUrl,
      difficulty: current.difficulty,
      notes: current.notes,
      servings: current.servings,
      prepMinutes: current.prepMinutes,
      cookMinutes: current.cookMinutes,
      totalMinutes: current.totalMinutes,
      coverMediaId: asset.id,
      equipment: current.equipment,
      ingredients: current.ingredients,
      steps: current.steps,
      stepLinks: current.stepLinks,
    );
    _markDirty();
  }

  Future<void> removeCoverMedia() async {
    final RecipeDetail? current = _draft;
    if (current == null || !canEdit || _mediaService == null) {
      return;
    }
    if (current.coverMediaId != null) {
      await _mediaService.remove(current.coverMediaId!);
    }
    _draft = RecipeDetail(
      id: current.id,
      title: current.title,
      subtitle: current.subtitle,
      scope: current.scope,
      status: current.status,
      author: current.author,
      sourceName: current.sourceName,
      sourceUrl: current.sourceUrl,
      difficulty: current.difficulty,
      notes: current.notes,
      servings: current.servings,
      prepMinutes: current.prepMinutes,
      cookMinutes: current.cookMinutes,
      totalMinutes: current.totalMinutes,
      coverMediaId: null,
      equipment: current.equipment,
      ingredients: current.ingredients,
      steps: current.steps,
      stepLinks: current.stepLinks,
    );
    _markDirty();
  }

  Future<void> attachStepMediaFromPath({required String stepId, required String sourcePath}) async {
    final RecipeDetail? current = _draft;
    if (current == null || !canEdit || _mediaService == null) {
      return;
    }
    final MediaAsset asset = await _mediaService.importFromPath(
      ownerType: "step",
      ownerId: stepId,
      sourcePath: sourcePath,
    );
    final List<RecipeStep> steps = current.steps
        .map(
          (RecipeStep step) => step.id == stepId
              ? RecipeStep(
                  id: step.id,
                  recipeId: step.recipeId,
                  title: step.title,
                  bodyText: step.bodyText,
                  stepType: step.stepType,
                  estimatedSeconds: step.estimatedSeconds,
                  mediaId: asset.id,
                  displayOrder: step.displayOrder,
                  timers: step.timers,
                )
              : step,
        )
        .toList();
    _updateRecipe(current, steps: steps);
  }

  Future<void> removeStepMedia(String stepId) async {
    final RecipeDetail? current = _draft;
    if (current == null || !canEdit || _mediaService == null) {
      return;
    }
    final List<RecipeStep> steps = <RecipeStep>[];
    for (final RecipeStep step in current.steps) {
      if (step.id == stepId) {
        if (step.mediaId != null) {
          await _mediaService.remove(step.mediaId!);
        }
        steps.add(
          RecipeStep(
            id: step.id,
            recipeId: step.recipeId,
            title: step.title,
            bodyText: step.bodyText,
            stepType: step.stepType,
            estimatedSeconds: step.estimatedSeconds,
            mediaId: null,
            displayOrder: step.displayOrder,
            timers: step.timers,
          ),
        );
      } else {
        steps.add(step);
      }
    }
    _updateRecipe(current, steps: steps);
  }

  void _updateRecipe(
    RecipeDetail current, {
    List<RecipeEquipmentItem>? equipment,
    List<RecipeIngredientItem>? ingredients,
    List<RecipeStep>? steps,
    List<StepLink>? stepLinks,
  }) {
    _draft = RecipeDetail(
      id: current.id,
      title: current.title,
      subtitle: current.subtitle,
      scope: current.scope,
      status: current.status,
      author: current.author,
      sourceName: current.sourceName,
      sourceUrl: current.sourceUrl,
      difficulty: current.difficulty,
      notes: current.notes,
      servings: current.servings,
      prepMinutes: current.prepMinutes,
      cookMinutes: current.cookMinutes,
      totalMinutes: current.totalMinutes,
      coverMediaId: current.coverMediaId,
      equipment: equipment ?? current.equipment,
      ingredients: ingredients ?? current.ingredients,
      steps: steps ?? current.steps,
      stepLinks: stepLinks ?? current.stepLinks,
    );
    _markDirty();
  }

  String _labelForTarget(RecipeDetail recipe, String targetType, String targetId) {
    if (targetType == "ingredient") {
      for (final RecipeIngredientItem item in recipe.ingredients) {
        if (item.id == targetId) {
          return item.ingredientName?.trim().isNotEmpty == true ? item.ingredientName! : item.rawText;
        }
      }
    }
    for (final RecipeEquipmentItem item in recipe.equipment) {
      if (item.id == targetId) {
        return item.name;
      }
    }
    return targetId;
  }

  RecipeStep? _findStep(RecipeDetail recipe, String stepId) {
    for (final RecipeStep step in recipe.steps) {
      if (step.id == stepId) {
        return step;
      }
    }
    return null;
  }

  StepLink? _findLink(RecipeDetail recipe, String linkId) {
    for (final StepLink link in recipe.stepLinks) {
      if (link.id == linkId) {
        return link;
      }
    }
    return null;
  }

  void _markDirty() {
    isDirty = true;
    notifyListeners();
  }

  String? _nullable(String? value) {
    if (value == null) {
      return null;
    }
    final String trimmed = value.trim();
    return trimmed.isEmpty ? null : trimmed;
  }
}
