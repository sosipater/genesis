import "package:uuid/uuid.dart";

import "../../data/models/recipe_models.dart";

class RecipeEditorService {
  static const Uuid _uuid = Uuid();

  RecipeDetail createEmptyRecipe() {
    final String recipeId = _uuid.v4();
    return RecipeDetail(
      id: recipeId,
      title: "Untitled Recipe",
      scope: "local",
      status: "draft",
      equipment: const <RecipeEquipmentItem>[],
      ingredients: const <RecipeIngredientItem>[],
      steps: const <RecipeStep>[],
      stepLinks: const <StepLink>[],
    );
  }

  RecipeDetail duplicateBundledAsLocal(RecipeDetail source) {
    final String recipeId = _uuid.v4();
    final Map<String, String> equipmentIds = <String, String>{};
    final Map<String, String> ingredientIds = <String, String>{};
    final Map<String, String> stepIds = <String, String>{};

    final List<RecipeEquipmentItem> equipment = source.equipment.asMap().entries.map((entry) {
      final String newId = _uuid.v4();
      equipmentIds[entry.value.id] = newId;
      return RecipeEquipmentItem(
        id: newId,
        recipeId: recipeId,
        name: entry.value.name,
        description: entry.value.description,
        notes: entry.value.notes,
        affiliateUrl: entry.value.affiliateUrl,
        mediaId: entry.value.mediaId,
        globalEquipmentId: entry.value.globalEquipmentId,
        isRequired: entry.value.isRequired,
        displayOrder: entry.key,
      );
    }).toList();

    final List<RecipeIngredientItem> ingredients = source.ingredients.asMap().entries.map((entry) {
      final String newId = _uuid.v4();
      ingredientIds[entry.value.id] = newId;
      return RecipeIngredientItem(
        id: newId,
        recipeId: recipeId,
        rawText: entry.value.rawText,
        quantityValue: entry.value.quantityValue,
        unit: entry.value.unit,
        ingredientName: entry.value.ingredientName,
        substitutions: entry.value.substitutions,
        preparationNotes: entry.value.preparationNotes,
        mediaId: entry.value.mediaId,
        isOptional: entry.value.isOptional,
        displayOrder: entry.key,
        catalogIngredientId: entry.value.catalogIngredientId,
        subRecipeId: entry.value.subRecipeId,
        subRecipeUsageType: entry.value.subRecipeUsageType,
        subRecipeMultiplier: entry.value.subRecipeMultiplier,
        subRecipeDisplayName: entry.value.subRecipeDisplayName,
      );
    }).toList();

    final List<RecipeStep> steps = source.steps.asMap().entries.map((entry) {
      final RecipeStep step = entry.value;
      final String newStepId = _uuid.v4();
      stepIds[step.id] = newStepId;
      return RecipeStep(
        id: newStepId,
        recipeId: recipeId,
        title: step.title,
        bodyText: step.bodyText,
        stepType: step.stepType,
        estimatedSeconds: step.estimatedSeconds,
        mediaId: step.mediaId,
        displayOrder: entry.key,
        timers: step.timers
            .map(
              (StepTimer timer) => StepTimer(
                id: _uuid.v4(),
                stepId: newStepId,
                label: timer.label,
                durationSeconds: timer.durationSeconds,
                autoStart: timer.autoStart,
                alertSoundKey: timer.alertSoundKey,
                alertVibrate: timer.alertVibrate,
              ),
            )
            .toList(),
      );
    }).toList();

    final List<StepLink> links = source.stepLinks.map((StepLink link) {
      final String? newStepId = stepIds[link.stepId];
      final String? newTargetId = link.targetType == "ingredient" ? ingredientIds[link.targetId] : equipmentIds[link.targetId];
      if (newStepId == null || newTargetId == null) {
        return null;
      }
      return StepLink(
        id: _uuid.v4(),
        stepId: newStepId,
        targetType: link.targetType,
        targetId: newTargetId,
        tokenKey: link.tokenKey,
        labelSnapshot: link.labelSnapshot,
        labelOverride: link.labelOverride,
      );
    }).whereType<StepLink>().toList();

    return RecipeDetail(
      id: recipeId,
      title: source.title,
      subtitle: source.subtitle,
      scope: "local",
      status: source.status,
      author: source.author,
      sourceName: source.sourceName,
      sourceUrl: source.sourceUrl,
      difficulty: source.difficulty,
      notes: source.notes,
      servings: source.servings,
      prepMinutes: source.prepMinutes,
      cookMinutes: source.cookMinutes,
      totalMinutes: source.totalMinutes,
      coverMediaId: source.coverMediaId,
      tags: List<String>.from(source.tags),
      equipment: equipment,
      ingredients: ingredients,
      steps: steps,
      stepLinks: links,
    );
  }

  RecipeDetail normalizeOrders(RecipeDetail recipe) {
    final List<RecipeEquipmentItem> equipment = recipe.equipment.asMap().entries
        .map((entry) => RecipeEquipmentItem(
              id: entry.value.id,
              recipeId: recipe.id,
              name: entry.value.name,
              description: entry.value.description,
              notes: entry.value.notes,
              affiliateUrl: entry.value.affiliateUrl,
              mediaId: entry.value.mediaId,
              globalEquipmentId: entry.value.globalEquipmentId,
              isRequired: entry.value.isRequired,
              displayOrder: entry.key,
            ))
        .toList();
    final List<RecipeIngredientItem> ingredients = recipe.ingredients.asMap().entries
        .map((entry) => RecipeIngredientItem(
              id: entry.value.id,
              recipeId: recipe.id,
              rawText: entry.value.rawText,
              quantityValue: entry.value.quantityValue,
              unit: entry.value.unit,
              ingredientName: entry.value.ingredientName,
              substitutions: entry.value.substitutions,
              preparationNotes: entry.value.preparationNotes,
              mediaId: entry.value.mediaId,
              isOptional: entry.value.isOptional,
              displayOrder: entry.key,
              catalogIngredientId: entry.value.catalogIngredientId,
              subRecipeId: entry.value.subRecipeId,
              subRecipeUsageType: entry.value.subRecipeUsageType,
              subRecipeMultiplier: entry.value.subRecipeMultiplier,
              subRecipeDisplayName: entry.value.subRecipeDisplayName,
            ))
        .toList();
    final List<RecipeStep> steps = recipe.steps.asMap().entries
        .map((entry) => RecipeStep(
              id: entry.value.id,
              recipeId: recipe.id,
              title: entry.value.title,
              bodyText: entry.value.bodyText,
              stepType: entry.value.stepType,
              estimatedSeconds: entry.value.estimatedSeconds,
              mediaId: entry.value.mediaId,
              displayOrder: entry.key,
              timers: entry.value.timers
                  .map(
                    (StepTimer timer) => StepTimer(
                      id: timer.id,
                      stepId: entry.value.id,
                      label: timer.label,
                      durationSeconds: timer.durationSeconds,
                      autoStart: timer.autoStart,
                      alertSoundKey: timer.alertSoundKey,
                      alertVibrate: timer.alertVibrate,
                    ),
                  )
                  .toList(),
            ))
        .toList();
    final Set<String> stepIds = steps.map((RecipeStep step) => step.id).toSet();
    final Set<String> ingredientIds = ingredients.map((RecipeIngredientItem item) => item.id).toSet();
    final Set<String> equipmentIds = equipment.map((RecipeEquipmentItem item) => item.id).toSet();
    final List<StepLink> links = recipe.stepLinks
        .where((StepLink link) {
          if (!stepIds.contains(link.stepId)) {
            return false;
          }
          if (link.targetType == "ingredient") {
            return ingredientIds.contains(link.targetId);
          }
          if (link.targetType == "equipment") {
            return equipmentIds.contains(link.targetId);
          }
          return false;
        })
        .toList();
    return RecipeDetail(
      id: recipe.id,
      title: recipe.title,
      subtitle: recipe.subtitle,
      scope: recipe.scope,
      status: recipe.status,
      author: recipe.author,
      sourceName: recipe.sourceName,
      sourceUrl: recipe.sourceUrl,
      difficulty: recipe.difficulty,
      notes: recipe.notes,
      servings: recipe.servings,
      prepMinutes: recipe.prepMinutes,
      cookMinutes: recipe.cookMinutes,
      totalMinutes: recipe.totalMinutes,
      coverMediaId: recipe.coverMediaId,
      tags: List<String>.from(recipe.tags),
      equipment: equipment,
      ingredients: ingredients,
      steps: steps,
      stepLinks: links,
    );
  }

  StepLink createStepLink({
    required RecipeDetail recipe,
    required RecipeStep step,
    required String targetType,
    required String targetId,
    required String tokenKey,
    String? labelOverride,
  }) {
    return StepLink(
      id: _uuid.v4(),
      stepId: step.id,
      targetType: targetType,
      targetId: targetId,
      tokenKey: tokenKey,
      labelSnapshot: _resolveLabelSnapshot(recipe, targetType: targetType, targetId: targetId),
      labelOverride: _nullIfBlank(labelOverride),
    );
  }

  String syncBodyForLinkToken({
    required String bodyText,
    String? oldTokenKey,
    required String tokenKey,
    required String targetType,
  }) {
    final String token = "[[$targetType:$tokenKey]]";
    if (oldTokenKey != null && oldTokenKey.isNotEmpty && oldTokenKey != tokenKey) {
      final String oldToken = "[[$targetType:$oldTokenKey]]";
      if (bodyText.contains(oldToken)) {
        return bodyText.replaceAll(oldToken, token);
      }
    }
    if (bodyText.contains(token)) {
      return bodyText;
    }
    if (bodyText.trim().isEmpty) {
      return token;
    }
    return "$bodyText $token";
  }

  String removeLinkTokenFromBody({
    required String bodyText,
    required String targetType,
    required String tokenKey,
  }) {
    final String token = "[[$targetType:$tokenKey]]";
    return bodyText.replaceAll(token, "").replaceAll(RegExp(r"\s{2,}"), " ").trim();
  }

  String _resolveLabelSnapshot(RecipeDetail recipe, {required String targetType, required String targetId}) {
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

  String? _nullIfBlank(String? value) {
    if (value == null) {
      return null;
    }
    final String trimmed = value.trim();
    return trimmed.isEmpty ? null : trimmed;
  }
}
