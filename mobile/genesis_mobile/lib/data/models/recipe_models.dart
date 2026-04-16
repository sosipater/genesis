class RecipeSummary {
  final String id;
  final String title;
  final String? subtitle;
  final String? author;
  final String scope; // local | bundled
  final String status;
  final String? updatedAt;
  final bool isFavorite;
  final String? lastOpenedAt;
  final String? lastCookedAt;
  final int openCount;
  final int cookCount;
  final String? coverMediaId;
  final List<String> tags;
  /// Optional subtle hint when the library query matched outside the title (e.g. Ingredient · Tag).
  final String? searchMatchHint;

  const RecipeSummary({
    required this.id,
    required this.title,
    required this.scope,
    required this.status,
    this.subtitle,
    this.author,
    this.updatedAt,
    this.isFavorite = false,
    this.lastOpenedAt,
    this.lastCookedAt,
    this.openCount = 0,
    this.cookCount = 0,
    this.coverMediaId,
    this.tags = const <String>[],
    this.searchMatchHint,
  });
}

class CollectionSummary {
  final String id;
  final String name;
  final int recipeCount;

  const CollectionSummary({
    required this.id,
    required this.name,
    required this.recipeCount,
  });
}

class MealPlanSummary {
  final String id;
  final String name;
  final String? startDate;
  final String? endDate;
  final int itemCount;

  const MealPlanSummary({
    required this.id,
    required this.name,
    this.startDate,
    this.endDate,
    this.itemCount = 0,
  });
}

class MealPlanItem {
  final String id;
  final String mealPlanId;
  final String recipeId;
  final double? servingsOverride;
  final String? notes;
  final String? plannedDate; // YYYY-MM-DD
  final String? mealSlot; // breakfast|lunch|dinner|snack|custom
  final String? slotLabel;
  final int sortOrder;
  final bool reminderEnabled;
  final int? preReminderMinutes;
  final bool startCookingPrompt;

  const MealPlanItem({
    required this.id,
    required this.mealPlanId,
    required this.recipeId,
    this.servingsOverride,
    this.notes,
    this.plannedDate,
    this.mealSlot,
    this.slotLabel,
    this.sortOrder = 0,
    this.reminderEnabled = false,
    this.preReminderMinutes,
    this.startCookingPrompt = false,
  });
}

class ReminderNotification {
  final String id;
  final String type; // meal_reminder|meal_pre_reminder|timer_complete
  final String referenceType; // meal_plan_item|timer
  final String referenceId;
  final String scheduledTimeUtc;
  final bool enabled;
  final String payloadJson;
  final String? updatedAt;

  const ReminderNotification({
    required this.id,
    required this.type,
    required this.referenceType,
    required this.referenceId,
    required this.scheduledTimeUtc,
    required this.enabled,
    required this.payloadJson,
    this.updatedAt,
  });
}

class GroceryListSummary {
  final String id;
  final String? mealPlanId;
  final String name;
  final String generatedAt;

  const GroceryListSummary({
    required this.id,
    required this.name,
    required this.generatedAt,
    this.mealPlanId,
  });
}

class GroceryListItem {
  final String id;
  final String groceryListId;
  final String name;
  final double? quantityValue;
  final String? unit;
  final bool checked;
  final List<String> sourceRecipeIds;
  final String sourceType; // generated | manual
  final String? generatedGroupKey;
  final bool wasUserModified;
  final int sortOrder;

  const GroceryListItem({
    required this.id,
    required this.groceryListId,
    required this.name,
    required this.checked,
    this.quantityValue,
    this.unit,
    this.sourceRecipeIds = const <String>[],
    this.sourceType = "generated",
    this.generatedGroupKey,
    this.wasUserModified = false,
    this.sortOrder = 0,
  });
}

/// Library row for reusable ingredients (synced with desktop `catalog_ingredient`).
class CatalogIngredientSummary {
  final String id;
  final String name;
  final String? notes;

  const CatalogIngredientSummary({
    required this.id,
    required this.name,
    this.notes,
  });
}

/// Library row for reusable equipment (synced with desktop `global_equipment`).
class GlobalEquipmentSummary {
  final String id;
  final String name;
  final String? notes;
  final String? mediaId;

  const GlobalEquipmentSummary({
    required this.id,
    required this.name,
    this.notes,
    this.mediaId,
  });
}

class RecipeEquipmentItem {
  final String id;
  final String recipeId;
  final String name;
  final String? description;
  final String? notes;
  final String? affiliateUrl;
  final bool isRequired;
  final int displayOrder;
  final String? mediaId;
  /// Optional link to a row in `global_equipment` when picked from the shared pool.
  final String? globalEquipmentId;

  const RecipeEquipmentItem({
    required this.id,
    required this.recipeId,
    required this.name,
    required this.isRequired,
    required this.displayOrder,
    this.description,
    this.notes,
    this.affiliateUrl,
    this.mediaId,
    this.globalEquipmentId,
  });
}

class RecipeIngredientItem {
  final String id;
  final String recipeId;
  final String rawText;
  final double? quantityValue;
  final String? unit;
  final String? ingredientName;
  final String? substitutions;
  final String? preparationNotes;
  final bool isOptional;
  final int displayOrder;
  final String? mediaId;
  /// Optional link to [CatalogIngredientSummary] when picked from the shared library.
  final String? catalogIngredientId;
  /// Optional reference to another recipe as a component (sub-recipe).
  final String? subRecipeId;
  final String? subRecipeUsageType;
  final double? subRecipeMultiplier;
  final String? subRecipeDisplayName;

  const RecipeIngredientItem({
    required this.id,
    required this.recipeId,
    required this.rawText,
    required this.isOptional,
    required this.displayOrder,
    this.quantityValue,
    this.unit,
    this.ingredientName,
    this.substitutions,
    this.preparationNotes,
    this.mediaId,
    this.catalogIngredientId,
    this.subRecipeId,
    this.subRecipeUsageType,
    this.subRecipeMultiplier,
    this.subRecipeDisplayName,
  });
}

class StepLink {
  final String id;
  final String stepId;
  final String targetType;
  final String targetId;
  final String tokenKey;
  final String labelSnapshot;
  final String? labelOverride;

  const StepLink({
    required this.id,
    required this.stepId,
    required this.targetType,
    required this.targetId,
    required this.tokenKey,
    required this.labelSnapshot,
    this.labelOverride,
  });
}

class StepTimer {
  final String id;
  final String stepId;
  final String label;
  final int durationSeconds;
  final bool autoStart;
  final String? alertSoundKey;
  final bool alertVibrate;

  const StepTimer({
    required this.id,
    required this.stepId,
    required this.label,
    required this.durationSeconds,
    required this.autoStart,
    this.alertSoundKey,
    this.alertVibrate = false,
  });
}

class RecipeStep {
  final String id;
  final String recipeId;
  final String? title;
  final String bodyText;
  final String stepType;
  final int? estimatedSeconds;
  final int displayOrder;
  final List<StepTimer> timers;
  final String? mediaId;

  const RecipeStep({
    required this.id,
    required this.recipeId,
    required this.bodyText,
    required this.stepType,
    required this.displayOrder,
    this.title,
    this.estimatedSeconds,
    this.timers = const [],
    this.mediaId,
  });
}

class MediaAsset {
  final String id;
  final String ownerType;
  final String ownerId;
  final String fileName;
  final String mimeType;
  final String relativePath;
  final int? width;
  final int? height;
  final String? createdAt;
  final String? updatedAt;

  const MediaAsset({
    required this.id,
    required this.ownerType,
    required this.ownerId,
    required this.fileName,
    required this.mimeType,
    required this.relativePath,
    this.width,
    this.height,
    this.createdAt,
    this.updatedAt,
  });
}

class RecipeDetail {
  final String id;
  final String title;
  final String? subtitle;
  final String scope;
  final String status;
  final String? author;
  final String? sourceName;
  final String? sourceUrl;
  final String? difficulty;
  final String? notes;
  final double? servings;
  final int? prepMinutes;
  final int? cookMinutes;
  final int? totalMinutes;
  final String? coverMediaId;
  /// Portable tag names (mirrors desktop `tags_json` / recipe payload `tags`).
  final List<String> tags;
  final List<RecipeEquipmentItem> equipment;
  final List<RecipeIngredientItem> ingredients;
  final List<RecipeStep> steps;
  final List<StepLink> stepLinks;

  const RecipeDetail({
    required this.id,
    required this.title,
    required this.scope,
    required this.status,
    required this.equipment,
    required this.ingredients,
    required this.steps,
    this.stepLinks = const [],
    this.tags = const <String>[],
    this.subtitle,
    this.author,
    this.sourceName,
    this.sourceUrl,
    this.difficulty,
    this.notes,
    this.servings,
    this.prepMinutes,
    this.cookMinutes,
    this.totalMinutes,
    this.coverMediaId,
  });
}

