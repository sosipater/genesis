import "dart:convert";
import "dart:io";

import "package:path/path.dart" as p;
import "package:sqflite/sqflite.dart";

import "../db/app_database.dart";
import "../models/recipe_models.dart";
import "recipe_editor_repository_port.dart";
import "repository_ports.dart";

class RecipeRepository implements RecipeReadRepositoryPort, RecipeEditorRepositoryPort {
  final AppDatabase _database;

  RecipeRepository(this._database);

  Future<List<RecipeSummary>> listRecipes() async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> rows = await db.rawQuery("""
      SELECT r.*, rus.is_favorite, rus.last_opened_at, rus.last_cooked_at, rus.open_count, rus.cook_count
      FROM recipes r
      LEFT JOIN recipe_user_state rus ON rus.recipe_id = r.id AND rus.deleted_at IS NULL
      WHERE r.deleted_at IS NULL
      ORDER BY r.title COLLATE NOCASE ASC
    """);
    return rows
        .map(
          (Map<String, Object?> row) => RecipeSummary(
            id: row["id"]! as String,
            title: row["title"]! as String,
            subtitle: row["subtitle"] as String?,
            scope: row["scope"]! as String,
            status: row["status"]! as String,
            updatedAt: row["updated_at"] as String?,
            isFavorite: ((row["is_favorite"] as int?) ?? 0) == 1,
            lastOpenedAt: row["last_opened_at"] as String?,
            lastCookedAt: row["last_cooked_at"] as String?,
            openCount: (row["open_count"] as int?) ?? 0,
            cookCount: (row["cook_count"] as int?) ?? 0,
            coverMediaId: row["cover_media_id"] as String?,
          ),
        )
        .toList();
  }

  Future<List<RecipeSummary>> searchRecipes({
    String query = "",
    String scope = "all",
  }) async {
    final List<RecipeSummary> all = await listRecipes();
    final String q = query.trim().toLowerCase();
    int score(RecipeSummary recipe) {
      int total = 0;
      if (q.isEmpty) {
        return 1;
      }
      if (recipe.title.toLowerCase().contains(q)) total += 50;
      if ((recipe.subtitle ?? "").toLowerCase().contains(q)) total += 20;
      return total;
    }

    bool scopeMatch(RecipeSummary recipe) {
      if (scope == "all") return true;
      if (scope == "forked") return false;
      if (scope == "favorites") return recipe.isFavorite;
      return recipe.scope == scope;
    }

    final List<RecipeSummary> filtered =
        all.where((RecipeSummary recipe) => scopeMatch(recipe) && (q.isEmpty || score(recipe) > 0)).toList();
    filtered.sort((RecipeSummary a, RecipeSummary b) {
      final int byScore = score(b).compareTo(score(a));
      if (byScore != 0) return byScore;
      return a.title.toLowerCase().compareTo(b.title.toLowerCase());
    });
    return filtered;
  }

  @override
  Future<RecipeDetail?> getRecipeById(String recipeId) async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> recipeRows = await db.query(
      "recipes",
      where: "id = ?",
      whereArgs: <Object>[recipeId],
      limit: 1,
    );
    if (recipeRows.isEmpty) {
      return null;
    }
    final Map<String, Object?> recipeRow = recipeRows.first;

    final List<Map<String, Object?>> eqRows = await db.query(
      "recipe_equipment",
      where: "recipe_id = ? AND deleted_at IS NULL",
      whereArgs: <Object>[recipeId],
      orderBy: "display_order ASC",
    );
    final List<Map<String, Object?>> ingRows = await db.query(
      "recipe_ingredients",
      where: "recipe_id = ? AND deleted_at IS NULL",
      whereArgs: <Object>[recipeId],
      orderBy: "display_order ASC",
    );
    final List<Map<String, Object?>> stepRows = await db.query(
      "recipe_steps",
      where: "recipe_id = ? AND deleted_at IS NULL",
      whereArgs: <Object>[recipeId],
      orderBy: "display_order ASC",
    );
    final List<Map<String, Object?>> stepLinkRows = await db.rawQuery(
      """
      SELECT sl.* FROM step_links sl
      JOIN recipe_steps rs ON rs.id = sl.step_id
      WHERE rs.recipe_id = ? AND sl.deleted_at IS NULL
      """,
      <Object>[recipeId],
    );

    final List<RecipeStep> steps = <RecipeStep>[];
    for (final Map<String, Object?> stepRow in stepRows) {
      final String stepId = stepRow["id"]! as String;
      final List<Map<String, Object?>> timerRows = await db.query(
        "step_timers",
        where: "step_id = ? AND deleted_at IS NULL",
        whereArgs: <Object>[stepId],
      );
      final List<StepTimer> timers = timerRows
          .map(
            (Map<String, Object?> timerRow) => StepTimer(
              id: timerRow["id"]! as String,
              stepId: stepId,
              label: timerRow["label"]! as String,
              durationSeconds: timerRow["duration_seconds"]! as int,
              autoStart: (timerRow["auto_start"]! as int) == 1,
              alertSoundKey: timerRow["alert_sound_key"] as String?,
            ),
          )
          .toList();
      steps.add(
        RecipeStep(
          id: stepId,
          recipeId: recipeId,
          title: stepRow["title"] as String?,
          bodyText: stepRow["body_text"]! as String,
          stepType: stepRow["step_type"]! as String,
          estimatedSeconds: stepRow["estimated_seconds"] as int?,
          displayOrder: stepRow["display_order"]! as int,
          timers: timers,
          mediaId: stepRow["media_id"] as String?,
        ),
      );
    }

    return RecipeDetail(
      id: recipeId,
      title: recipeRow["title"]! as String,
      subtitle: recipeRow["subtitle"] as String?,
      scope: recipeRow["scope"]! as String,
      status: recipeRow["status"]! as String,
      author: recipeRow["author"] as String?,
      sourceName: recipeRow["source_name"] as String?,
      sourceUrl: recipeRow["source_url"] as String?,
      difficulty: recipeRow["difficulty"] as String?,
      notes: recipeRow["notes"] as String?,
      servings: (recipeRow["servings"] as num?)?.toDouble(),
      prepMinutes: recipeRow["prep_minutes"] as int?,
      cookMinutes: recipeRow["cook_minutes"] as int?,
      totalMinutes: recipeRow["total_minutes"] as int?,
      coverMediaId: recipeRow["cover_media_id"] as String?,
      equipment: eqRows
          .map(
            (Map<String, Object?> row) => RecipeEquipmentItem(
              id: row["id"]! as String,
              recipeId: recipeId,
              name: row["name"]! as String,
              description: row["description"] as String?,
              notes: row["notes"] as String?,
              affiliateUrl: row["affiliate_url"] as String?,
              mediaId: row["media_id"] as String?,
              isRequired: (row["is_required"]! as int) == 1,
              displayOrder: row["display_order"]! as int,
            ),
          )
          .toList(),
      ingredients: ingRows
          .map(
            (Map<String, Object?> row) => RecipeIngredientItem(
              id: row["id"]! as String,
              recipeId: recipeId,
              rawText: row["raw_text"]! as String,
              quantityValue: (row["quantity_value"] as num?)?.toDouble(),
              unit: row["unit"] as String?,
              ingredientName: row["ingredient_name"] as String?,
              substitutions: row["substitutions"] as String?,
              preparationNotes: row["preparation_notes"] as String?,
              mediaId: row["media_id"] as String?,
              isOptional: (row["is_optional"]! as int) == 1,
              displayOrder: row["display_order"]! as int,
            ),
          )
          .toList(),
      steps: steps,
      stepLinks: stepLinkRows
          .map(
            (Map<String, Object?> row) => StepLink(
              id: row["id"]! as String,
              stepId: row["step_id"]! as String,
              targetType: row["target_type"]! as String,
              targetId: row["target_id"]! as String,
              tokenKey: row["token_key"]! as String,
              labelSnapshot: row["label_snapshot"]! as String,
              labelOverride: row["label_override"] as String?,
            ),
          )
          .toList(),
    );
  }

  @override
  Future<void> upsertRecipeGraph(RecipeDetail recipe, {required String updatedAt}) async {
    final Database db = await _database.database;
    await db.transaction((Transaction txn) async {
      await txn.insert(
        "recipes",
        <String, Object?>{
          "id": recipe.id,
          "scope": recipe.scope,
          "title": recipe.title,
          "subtitle": recipe.subtitle,
          "author": recipe.author,
          "source_name": recipe.sourceName,
          "source_url": recipe.sourceUrl,
          "difficulty": recipe.difficulty,
          "notes": recipe.notes,
          "servings": recipe.servings,
          "prep_minutes": recipe.prepMinutes,
          "cook_minutes": recipe.cookMinutes,
          "total_minutes": recipe.totalMinutes,
          "cover_media_id": recipe.coverMediaId,
          "status": recipe.status,
          "updated_at": updatedAt,
          "deleted_at": null,
        },
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
      await txn.delete("recipe_equipment", where: "recipe_id = ?", whereArgs: <Object>[recipe.id]);
      await txn.delete("recipe_ingredients", where: "recipe_id = ?", whereArgs: <Object>[recipe.id]);
      final List<String> stepIds = recipe.steps.map((RecipeStep s) => s.id).toList();
      if (stepIds.isNotEmpty) {
        final String placeholders = List<String>.filled(stepIds.length, "?").join(",");
        await txn.delete("step_timers", where: "step_id IN ($placeholders)", whereArgs: stepIds);
        await txn.delete("step_links", where: "step_id IN ($placeholders)", whereArgs: stepIds);
      }
      await txn.delete("recipe_steps", where: "recipe_id = ?", whereArgs: <Object>[recipe.id]);

      for (final RecipeEquipmentItem item in recipe.equipment) {
        await txn.insert("recipe_equipment", <String, Object?>{
          "id": item.id,
          "recipe_id": recipe.id,
          "name": item.name,
          "description": item.description,
          "notes": item.notes,
          "affiliate_url": item.affiliateUrl,
          "media_id": item.mediaId,
          "is_required": item.isRequired ? 1 : 0,
          "display_order": item.displayOrder,
        });
      }
      for (final RecipeIngredientItem item in recipe.ingredients) {
        await txn.insert("recipe_ingredients", <String, Object?>{
          "id": item.id,
          "recipe_id": recipe.id,
          "raw_text": item.rawText,
          "quantity_value": item.quantityValue,
          "unit": item.unit,
          "ingredient_name": item.ingredientName,
          "substitutions": item.substitutions,
          "preparation_notes": item.preparationNotes,
          "media_id": item.mediaId,
          "is_optional": item.isOptional ? 1 : 0,
          "display_order": item.displayOrder,
        });
      }
      for (final RecipeStep step in recipe.steps) {
        await txn.insert("recipe_steps", <String, Object?>{
          "id": step.id,
          "recipe_id": recipe.id,
          "title": step.title,
          "body_text": step.bodyText,
          "step_type": step.stepType,
          "estimated_seconds": step.estimatedSeconds,
          "media_id": step.mediaId,
          "display_order": step.displayOrder,
        });
        for (final StepTimer timer in step.timers) {
          await txn.insert("step_timers", <String, Object?>{
            "id": timer.id,
            "step_id": step.id,
            "label": timer.label,
            "duration_seconds": timer.durationSeconds,
            "auto_start": timer.autoStart ? 1 : 0,
            "alert_sound_key": timer.alertSoundKey,
          });
        }
      }
      for (final StepLink link in recipe.stepLinks) {
        await txn.insert("step_links", <String, Object?>{
          "id": link.id,
          "step_id": link.stepId,
          "target_type": link.targetType,
          "target_id": link.targetId,
          "token_key": link.tokenKey,
          "label_snapshot": link.labelSnapshot,
          "label_override": link.labelOverride,
        });
      }
    });
  }

  @override
  Future<void> markRecipeOpened(String recipeId, String openedAtUtc) async {
    final Database db = await _database.database;
    await db.insert(
      "recent_recipes",
      <String, Object?>{"recipe_id": recipeId, "opened_at": openedAtUtc},
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
    await trackRecipeOpened(recipeId, openedAtUtc);
  }

  Future<String?> getMostRecentRecipeId() async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> rows = await db.query(
      "recent_recipes",
      orderBy: "opened_at DESC",
      limit: 1,
    );
    if (rows.isEmpty) {
      return null;
    }
    return rows.first["recipe_id"]! as String;
  }

  Future<List<CollectionSummary>> listCollections() async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> rows = await db.rawQuery("""
      SELECT c.id, c.name, COUNT(ci.id) AS recipe_count
      FROM collections c
      LEFT JOIN collection_items ci ON ci.collection_id = c.id AND ci.deleted_at IS NULL
      WHERE c.deleted_at IS NULL
      GROUP BY c.id, c.name
      ORDER BY c.name COLLATE NOCASE ASC
    """);
    return rows
        .map(
          (Map<String, Object?> row) => CollectionSummary(
            id: row["id"]! as String,
            name: row["name"]! as String,
            recipeCount: row["recipe_count"]! as int,
          ),
        )
        .toList();
  }

  Future<List<RecipeSummary>> listCollectionRecipes(String collectionId) async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> rows = await db.rawQuery(
      """
      SELECT r.* FROM recipes r
      JOIN collection_items ci ON ci.recipe_id = r.id
      WHERE ci.collection_id = ? AND ci.deleted_at IS NULL AND r.deleted_at IS NULL
      ORDER BY r.title COLLATE NOCASE ASC
      """,
      <Object>[collectionId],
    );
    return rows
        .map(
          (Map<String, Object?> row) => RecipeSummary(
            id: row["id"]! as String,
            title: row["title"]! as String,
            subtitle: row["subtitle"] as String?,
            scope: row["scope"]! as String,
            status: row["status"]! as String,
            updatedAt: row["updated_at"] as String?,
            coverMediaId: row["cover_media_id"] as String?,
          ),
        )
        .toList();
  }

  Future<List<RecipeSummary>> listWorkingSetRecipes() async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> rows = await db.rawQuery("""
      SELECT r.* FROM recipes r
      JOIN working_set_items ws ON ws.recipe_id = r.id
      WHERE ws.deleted_at IS NULL AND r.deleted_at IS NULL
      ORDER BY ws.created_at DESC
    """);
    return rows
        .map(
          (Map<String, Object?> row) => RecipeSummary(
            id: row["id"]! as String,
            title: row["title"]! as String,
            subtitle: row["subtitle"] as String?,
            scope: row["scope"]! as String,
            status: row["status"]! as String,
            updatedAt: row["updated_at"] as String?,
            coverMediaId: row["cover_media_id"] as String?,
          ),
        )
        .toList();
  }

  Future<void> addToWorkingSet(String recipeId, String createdAtUtc) async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> existing =
        await db.query("working_set_items", where: "recipe_id = ?", whereArgs: <Object>[recipeId], limit: 1);
    if (existing.isNotEmpty) {
      await db.update("working_set_items", <String, Object?>{"deleted_at": null}, where: "recipe_id = ?", whereArgs: <Object>[recipeId]);
      return;
    }
    await db.insert("working_set_items", <String, Object?>{
      "id": "ws_$recipeId",
      "recipe_id": recipeId,
      "created_at": createdAtUtc,
      "deleted_at": null,
    });
  }

  Future<void> removeFromWorkingSet(String recipeId, String deletedAtUtc) async {
    final Database db = await _database.database;
    await db.update(
      "working_set_items",
      <String, Object?>{"deleted_at": deletedAtUtc},
      where: "recipe_id = ?",
      whereArgs: <Object>[recipeId],
    );
  }

  Future<void> upsertCollection({
    required String id,
    required String name,
    required String updatedAtUtc,
  }) async {
    final Database db = await _database.database;
    await db.insert(
      "collections",
      <String, Object?>{
        "id": id,
        "name": name,
        "created_at": updatedAtUtc,
        "updated_at": updatedAtUtc,
        "deleted_at": null,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<void> upsertCollectionItem({
    required String id,
    required String collectionId,
    required String recipeId,
    required String updatedAtUtc,
  }) async {
    final Database db = await _database.database;
    await db.insert(
      "collection_items",
      <String, Object?>{
        "id": id,
        "collection_id": collectionId,
        "recipe_id": recipeId,
        "created_at": updatedAtUtc,
        "deleted_at": null,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<void> deleteCollection(String id, String deletedAtUtc) async {
    final Database db = await _database.database;
    await db.update("collections", <String, Object?>{"deleted_at": deletedAtUtc}, where: "id = ?", whereArgs: <Object>[id]);
  }

  Future<void> deleteCollectionItem(String id, String deletedAtUtc) async {
    final Database db = await _database.database;
    await db.update("collection_items", <String, Object?>{"deleted_at": deletedAtUtc}, where: "id = ?", whereArgs: <Object>[id]);
  }

  Future<String> createMealPlan({
    required String id,
    required String name,
    String? startDate,
    String? endDate,
    String? notes,
    required String updatedAtUtc,
  }) async {
    final Database db = await _database.database;
    await db.insert("meal_plans", <String, Object?>{
      "id": id,
      "name": name,
      "start_date": startDate,
      "end_date": endDate,
      "notes": notes,
      "updated_at": updatedAtUtc,
      "deleted_at": null,
    }, conflictAlgorithm: ConflictAlgorithm.replace);
    return id;
  }

  Future<List<MealPlanSummary>> listMealPlans() async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> rows = await db.rawQuery("""
      SELECT mp.id, mp.name, mp.start_date, mp.end_date, COUNT(mpi.id) AS item_count
      FROM meal_plans mp
      LEFT JOIN meal_plan_items mpi ON mpi.meal_plan_id = mp.id AND mpi.deleted_at IS NULL
      WHERE mp.deleted_at IS NULL
      GROUP BY mp.id, mp.name, mp.start_date, mp.end_date
      ORDER BY mp.updated_at DESC
    """);
    return rows
        .map(
          (Map<String, Object?> row) => MealPlanSummary(
            id: row["id"]! as String,
            name: row["name"]! as String,
            startDate: row["start_date"] as String?,
            endDate: row["end_date"] as String?,
            itemCount: row["item_count"]! as int,
          ),
        )
        .toList();
  }

  Future<String> addMealPlanItem({
    required String id,
    required String mealPlanId,
    required String recipeId,
    double? servingsOverride,
    String? notes,
    String? plannedDate,
    String? mealSlot,
    String? slotLabel,
    int sortOrder = 0,
    bool reminderEnabled = false,
    int? preReminderMinutes,
    bool startCookingPrompt = false,
    required String updatedAtUtc,
  }) async {
    final Database db = await _database.database;
    await db.insert("meal_plan_items", <String, Object?>{
      "id": id,
      "meal_plan_id": mealPlanId,
      "recipe_id": recipeId,
      "servings_override": servingsOverride,
      "notes": notes,
      "planned_date": plannedDate,
      "meal_slot": mealSlot,
      "slot_label": slotLabel,
      "sort_order": sortOrder,
      "reminder_enabled": reminderEnabled ? 1 : 0,
      "pre_reminder_minutes": preReminderMinutes,
      "start_cooking_prompt": startCookingPrompt ? 1 : 0,
      "updated_at": updatedAtUtc,
      "deleted_at": null,
    }, conflictAlgorithm: ConflictAlgorithm.replace);
    return id;
  }

  Future<void> removeMealPlanItem(String id, String deletedAtUtc) async {
    final Database db = await _database.database;
    await db.update(
      "meal_plan_items",
      <String, Object?>{"deleted_at": deletedAtUtc, "updated_at": deletedAtUtc},
      where: "id = ?",
      whereArgs: <Object>[id],
    );
  }

  Future<void> deleteMealPlan(String id, String deletedAtUtc) async {
    final Database db = await _database.database;
    await db.update(
      "meal_plans",
      <String, Object?>{"deleted_at": deletedAtUtc, "updated_at": deletedAtUtc},
      where: "id = ?",
      whereArgs: <Object>[id],
    );
  }

  Future<void> restoreMealPlan(String id, String restoredAtUtc) async {
    final Database db = await _database.database;
    await db.update(
      "meal_plans",
      <String, Object?>{"deleted_at": null, "updated_at": restoredAtUtc},
      where: "id = ?",
      whereArgs: <Object>[id],
    );
  }

  Future<List<MealPlanItem>> listMealPlanItems(String mealPlanId) async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> rows = await db.query(
      "meal_plan_items",
      where: "meal_plan_id = ? AND deleted_at IS NULL",
      whereArgs: <Object>[mealPlanId],
      orderBy: "planned_date ASC, meal_slot ASC, sort_order ASC, updated_at DESC",
    );
    return rows
        .map(
          (Map<String, Object?> row) => MealPlanItem(
            id: row["id"]! as String,
            mealPlanId: row["meal_plan_id"]! as String,
            recipeId: row["recipe_id"]! as String,
            servingsOverride: (row["servings_override"] as num?)?.toDouble(),
            notes: row["notes"] as String?,
            plannedDate: row["planned_date"] as String?,
            mealSlot: row["meal_slot"] as String?,
            slotLabel: row["slot_label"] as String?,
            sortOrder: (row["sort_order"] as num?)?.toInt() ?? 0,
            reminderEnabled: ((row["reminder_enabled"] as num?)?.toInt() ?? 0) == 1,
            preReminderMinutes: (row["pre_reminder_minutes"] as num?)?.toInt(),
            startCookingPrompt: ((row["start_cooking_prompt"] as num?)?.toInt() ?? 0) == 1,
          ),
        )
        .toList();
  }

  Future<void> updateMealPlanItemSchedule({
    required String itemId,
    String? plannedDate,
    String? mealSlot,
    String? slotLabel,
    int? sortOrder,
    bool? reminderEnabled,
    int? preReminderMinutes,
    bool? startCookingPrompt,
    required String updatedAtUtc,
  }) async {
    final Database db = await _database.database;
    await db.update(
      "meal_plan_items",
      <String, Object?>{
        "planned_date": plannedDate,
        "meal_slot": mealSlot,
        "slot_label": slotLabel,
        if (sortOrder != null) "sort_order": sortOrder,
        if (reminderEnabled != null) "reminder_enabled": reminderEnabled ? 1 : 0,
        if (preReminderMinutes != null || reminderEnabled == false) "pre_reminder_minutes": preReminderMinutes,
        if (startCookingPrompt != null) "start_cooking_prompt": startCookingPrompt ? 1 : 0,
        "updated_at": updatedAtUtc,
      },
      where: "id = ?",
      whereArgs: <Object>[itemId],
    );
  }

  Future<String> createGroceryList({
    required String id,
    String? mealPlanId,
    required String name,
    required String generatedAtUtc,
  }) async {
    final Database db = await _database.database;
    await db.insert("grocery_lists", <String, Object?>{
      "id": id,
      "meal_plan_id": mealPlanId,
      "name": name,
      "generated_at": generatedAtUtc,
      "updated_at": generatedAtUtc,
      "deleted_at": null,
    }, conflictAlgorithm: ConflictAlgorithm.replace);
    return id;
  }

  Future<void> deleteGroceryList(String id, String deletedAtUtc) async {
    final Database db = await _database.database;
    await db.update(
      "grocery_lists",
      <String, Object?>{"deleted_at": deletedAtUtc, "updated_at": deletedAtUtc},
      where: "id = ?",
      whereArgs: <Object>[id],
    );
  }

  Future<void> upsertGroceryListItem({
    required String id,
    required String groceryListId,
    required String name,
    double? quantityValue,
    String? unit,
    required bool checked,
    required List<String> sourceRecipeIds,
    String sourceType = "generated",
    String? generatedGroupKey,
    bool wasUserModified = false,
    int sortOrder = 0,
    required String updatedAtUtc,
  }) async {
    final Database db = await _database.database;
    await db.insert(
      "grocery_list_items",
      <String, Object?>{
        "id": id,
        "grocery_list_id": groceryListId,
        "name": name,
        "quantity_value": quantityValue,
        "unit": unit,
        "checked": checked ? 1 : 0,
        "source_recipe_ids_json": jsonEncode(sourceRecipeIds),
        "source_type": sourceType,
        "generated_group_key": generatedGroupKey,
        "was_user_modified": wasUserModified ? 1 : 0,
        "sort_order": sortOrder,
        "updated_at": updatedAtUtc,
        "deleted_at": null,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<void> deleteGroceryListItem(String id, String deletedAtUtc) async {
    final Database db = await _database.database;
    await db.update(
      "grocery_list_items",
      <String, Object?>{"deleted_at": deletedAtUtc, "updated_at": deletedAtUtc},
      where: "id = ?",
      whereArgs: <Object>[id],
    );
  }

  Future<void> replaceGroceryListItems(String groceryListId, List<GroceryListItem> items, String updatedAtUtc) async {
    final Database db = await _database.database;
    await db.transaction((Transaction txn) async {
      await txn.delete("grocery_list_items", where: "grocery_list_id = ?", whereArgs: <Object>[groceryListId]);
      for (int idx = 0; idx < items.length; idx++) {
        final GroceryListItem item = items[idx];
        await txn.insert("grocery_list_items", <String, Object?>{
          "id": item.id,
          "grocery_list_id": groceryListId,
          "name": item.name,
          "quantity_value": item.quantityValue,
          "unit": item.unit,
          "checked": item.checked ? 1 : 0,
          "source_recipe_ids_json": jsonEncode(item.sourceRecipeIds),
          "source_type": item.sourceType,
          "generated_group_key": item.generatedGroupKey,
          "was_user_modified": item.wasUserModified ? 1 : 0,
          "sort_order": item.sortOrder == 0 ? idx : item.sortOrder,
          "updated_at": updatedAtUtc,
          "deleted_at": null,
        });
      }
      await txn.update(
        "grocery_lists",
        <String, Object?>{"updated_at": updatedAtUtc},
        where: "id = ?",
        whereArgs: <Object>[groceryListId],
      );
    });
  }

  Future<List<GroceryListSummary>> listGroceryLists() async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> rows = await db.query(
      "grocery_lists",
      where: "deleted_at IS NULL",
      orderBy: "generated_at DESC",
    );
    return rows
        .map(
          (Map<String, Object?> row) => GroceryListSummary(
            id: row["id"]! as String,
            mealPlanId: row["meal_plan_id"] as String?,
            name: row["name"]! as String,
            generatedAt: row["generated_at"]! as String,
          ),
        )
        .toList();
  }

  Future<List<GroceryListItem>> listGroceryListItems(String groceryListId) async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> rows = await db.query(
      "grocery_list_items",
      where: "grocery_list_id = ? AND deleted_at IS NULL",
      whereArgs: <Object>[groceryListId],
      orderBy: "sort_order ASC, name COLLATE NOCASE ASC",
    );
    return rows
        .map(
          (Map<String, Object?> row) => GroceryListItem(
            id: row["id"]! as String,
            groceryListId: row["grocery_list_id"]! as String,
            name: row["name"]! as String,
            quantityValue: (row["quantity_value"] as num?)?.toDouble(),
            unit: row["unit"] as String?,
            checked: (row["checked"]! as int) == 1,
            sourceRecipeIds: ((jsonDecode(row["source_recipe_ids_json"]! as String) as List<dynamic>))
                .map((dynamic value) => value as String)
                .toList(),
            sourceType: row["source_type"]! as String,
            generatedGroupKey: row["generated_group_key"] as String?,
            wasUserModified: (row["was_user_modified"]! as int) == 1,
            sortOrder: row["sort_order"]! as int,
          ),
        )
        .toList();
  }

  Future<void> toggleGroceryListItem(String itemId, bool checked, String updatedAtUtc) async {
    final Database db = await _database.database;
    await db.update(
      "grocery_list_items",
      <String, Object?>{"checked": checked ? 1 : 0, "was_user_modified": 1, "updated_at": updatedAtUtc},
      where: "id = ?",
      whereArgs: <Object>[itemId],
    );
  }

  Future<void> trackRecipeOpened(String recipeId, String updatedAtUtc) async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> rows =
        await db.query("recipe_user_state", where: "recipe_id = ?", whereArgs: <Object>[recipeId], limit: 1);
    if (rows.isEmpty) {
      await db.insert("recipe_user_state", <String, Object?>{
        "recipe_id": recipeId,
        "is_favorite": 0,
        "last_opened_at": updatedAtUtc,
        "last_cooked_at": null,
        "open_count": 1,
        "cook_count": 0,
        "pinned": 0,
        "updated_at": updatedAtUtc,
        "deleted_at": null,
      });
      return;
    }
    final Map<String, Object?> current = rows.first;
    await db.update(
      "recipe_user_state",
      <String, Object?>{
        "last_opened_at": updatedAtUtc,
        "open_count": ((current["open_count"] as int?) ?? 0) + 1,
        "updated_at": updatedAtUtc,
      },
      where: "recipe_id = ?",
      whereArgs: <Object>[recipeId],
    );
  }

  Future<void> markRecipeCooked(String recipeId, String updatedAtUtc) async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> rows =
        await db.query("recipe_user_state", where: "recipe_id = ?", whereArgs: <Object>[recipeId], limit: 1);
    if (rows.isEmpty) {
      await db.insert("recipe_user_state", <String, Object?>{
        "recipe_id": recipeId,
        "is_favorite": 0,
        "last_opened_at": null,
        "last_cooked_at": updatedAtUtc,
        "open_count": 0,
        "cook_count": 1,
        "pinned": 0,
        "updated_at": updatedAtUtc,
        "deleted_at": null,
      });
      return;
    }
    final Map<String, Object?> current = rows.first;
    await db.update(
      "recipe_user_state",
      <String, Object?>{
        "last_cooked_at": updatedAtUtc,
        "cook_count": ((current["cook_count"] as int?) ?? 0) + 1,
        "updated_at": updatedAtUtc,
      },
      where: "recipe_id = ?",
      whereArgs: <Object>[recipeId],
    );
  }

  Future<void> setFavorite(String recipeId, bool isFavorite, String updatedAtUtc) async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> rows =
        await db.query("recipe_user_state", where: "recipe_id = ?", whereArgs: <Object>[recipeId], limit: 1);
    if (rows.isEmpty) {
      await db.insert("recipe_user_state", <String, Object?>{
        "recipe_id": recipeId,
        "is_favorite": isFavorite ? 1 : 0,
        "last_opened_at": null,
        "last_cooked_at": null,
        "open_count": 0,
        "cook_count": 0,
        "pinned": 0,
        "updated_at": updatedAtUtc,
        "deleted_at": null,
      });
      return;
    }
    await db.update(
      "recipe_user_state",
      <String, Object?>{"is_favorite": isFavorite ? 1 : 0, "updated_at": updatedAtUtc},
      where: "recipe_id = ?",
      whereArgs: <Object>[recipeId],
    );
  }

  Future<List<RecipeSummary>> listRecentOpenedRecipes({int limit = 12}) async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> rows = await db.rawQuery(
      """
      SELECT r.*, rus.is_favorite, rus.last_opened_at, rus.last_cooked_at, rus.open_count, rus.cook_count
      FROM recipe_user_state rus
      JOIN recipes r ON r.id = rus.recipe_id
      WHERE rus.last_opened_at IS NOT NULL AND rus.deleted_at IS NULL AND r.deleted_at IS NULL
      ORDER BY rus.last_opened_at DESC
      LIMIT ?
      """,
      <Object>[limit],
    );
    return rows
        .map(
          (Map<String, Object?> row) => RecipeSummary(
            id: row["id"]! as String,
            title: row["title"]! as String,
            subtitle: row["subtitle"] as String?,
            scope: row["scope"]! as String,
            status: row["status"]! as String,
            updatedAt: row["updated_at"] as String?,
            isFavorite: ((row["is_favorite"] as int?) ?? 0) == 1,
            lastOpenedAt: row["last_opened_at"] as String?,
            lastCookedAt: row["last_cooked_at"] as String?,
            openCount: (row["open_count"] as int?) ?? 0,
            cookCount: (row["cook_count"] as int?) ?? 0,
            coverMediaId: row["cover_media_id"] as String?,
          ),
        )
        .toList();
  }

  Future<String> addManualGroceryItem({
    required String groceryListId,
    required String id,
    required String name,
    double? quantityValue,
    String? unit,
    required String updatedAtUtc,
  }) async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> rows = await db.rawQuery(
      "SELECT COALESCE(MAX(sort_order), -1) AS max_sort FROM grocery_list_items WHERE grocery_list_id = ? AND deleted_at IS NULL",
      <Object>[groceryListId],
    );
    final int nextSort = ((rows.first["max_sort"] as int?) ?? -1) + 1;
    await upsertGroceryListItem(
      id: id,
      groceryListId: groceryListId,
      name: name,
      quantityValue: quantityValue,
      unit: unit,
      checked: false,
      sourceRecipeIds: const <String>[],
      sourceType: "manual",
      generatedGroupKey: null,
      wasUserModified: true,
      sortOrder: nextSort,
      updatedAtUtc: updatedAtUtc,
    );
    return id;
  }

  Future<void> updateGroceryListItem({
    required String id,
    required String name,
    double? quantityValue,
    String? unit,
    required String updatedAtUtc,
  }) async {
    final Database db = await _database.database;
    await db.update(
      "grocery_list_items",
      <String, Object?>{
        "name": name,
        "quantity_value": quantityValue,
        "unit": unit,
        "was_user_modified": 1,
        "updated_at": updatedAtUtc,
      },
      where: "id = ?",
      whereArgs: <Object>[id],
    );
  }

  Future<void> reorderGroceryListItems(String groceryListId, List<String> orderedItemIds, String updatedAtUtc) async {
    final Database db = await _database.database;
    await db.transaction((Transaction txn) async {
      for (int idx = 0; idx < orderedItemIds.length; idx++) {
        await txn.update(
          "grocery_list_items",
          <String, Object?>{"sort_order": idx, "updated_at": updatedAtUtc},
          where: "id = ? AND grocery_list_id = ? AND deleted_at IS NULL",
          whereArgs: <Object>[orderedItemIds[idx], groceryListId],
        );
      }
    });
  }

  Future<void> upsertMediaAsset(MediaAsset asset, {required String updatedAtUtc}) async {
    final Database db = await _database.database;
    await db.insert(
      "media_assets",
      <String, Object?>{
        "id": asset.id,
        "owner_type": asset.ownerType,
        "owner_id": asset.ownerId,
        "file_name": asset.fileName,
        "mime_type": asset.mimeType,
        "relative_path": asset.relativePath,
        "width": asset.width,
        "height": asset.height,
        "updated_at": updatedAtUtc,
        "deleted_at": null,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<void> deleteMediaAsset(String id, String deletedAtUtc) async {
    final Database db = await _database.database;
    await db.update(
      "media_assets",
      <String, Object?>{"deleted_at": deletedAtUtc, "updated_at": deletedAtUtc},
      where: "id = ?",
      whereArgs: <Object>[id],
    );
  }

  Future<MediaAsset?> getMediaAssetById(String id) async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> rows = await db.query(
      "media_assets",
      where: "id = ? AND deleted_at IS NULL",
      whereArgs: <Object>[id],
      limit: 1,
    );
    if (rows.isEmpty) {
      return null;
    }
    final Map<String, Object?> row = rows.first;
    return MediaAsset(
      id: row["id"]! as String,
      ownerType: row["owner_type"]! as String,
      ownerId: row["owner_id"]! as String,
      fileName: row["file_name"]! as String,
      mimeType: row["mime_type"]! as String,
      relativePath: row["relative_path"]! as String,
      width: row["width"] as int?,
      height: row["height"] as int?,
      updatedAt: row["updated_at"] as String?,
    );
  }

  Future<String?> resolveMediaFilePath(String mediaAssetId) async {
    final MediaAsset? asset = await getMediaAssetById(mediaAssetId);
    if (asset == null) {
      return null;
    }
    final Database db = await _database.database;
    final String mediaRoot = p.join(p.dirname(db.path), "media");
    final String absolute = p.join(mediaRoot, asset.relativePath);
    if (!File(absolute).existsSync()) {
      return null;
    }
    return absolute;
  }

  Future<void> upsertRecipeUserState({
    required String recipeId,
    required bool isFavorite,
    String? lastOpenedAt,
    String? lastCookedAt,
    required int openCount,
    required int cookCount,
    required String updatedAtUtc,
  }) async {
    final Database db = await _database.database;
    await db.insert(
      "recipe_user_state",
      <String, Object?>{
        "recipe_id": recipeId,
        "is_favorite": isFavorite ? 1 : 0,
        "last_opened_at": lastOpenedAt,
        "last_cooked_at": lastCookedAt,
        "open_count": openCount,
        "cook_count": cookCount,
        "pinned": 0,
        "updated_at": updatedAtUtc,
        "deleted_at": null,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<void> deleteRecipeUserState(String recipeId, String deletedAtUtc) async {
    final Database db = await _database.database;
    await db.update(
      "recipe_user_state",
      <String, Object?>{"deleted_at": deletedAtUtc, "updated_at": deletedAtUtc},
      where: "recipe_id = ?",
      whereArgs: <Object>[recipeId],
    );
  }

  Future<List<Map<String, dynamic>>> listRecipeUserStateChangesSince(String? sinceCursor) async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> rows = await db.rawQuery(
      """
      SELECT recipe_id, is_favorite, last_opened_at, last_cooked_at, open_count, cook_count, pinned, updated_at, deleted_at
      FROM recipe_user_state
      WHERE (? IS NULL OR updated_at > ?)
      ORDER BY updated_at ASC
      """,
      <Object?>[sinceCursor, sinceCursor],
    );
    return rows
        .map(
          (Map<String, Object?> row) => <String, dynamic>{
            "entity_type": "recipe_user_state",
            "entity_id": row["recipe_id"] as String,
            "op": row["deleted_at"] == null ? "upsert" : "delete",
            "entity_version": 1,
            "updated_at_utc": row["updated_at"] as String,
            "source_scope": "local",
            "body": row["deleted_at"] == null
                ? <String, dynamic>{
                    "recipe_id": row["recipe_id"] as String,
                    "is_favorite": ((row["is_favorite"] as int?) ?? 0) == 1,
                    "last_opened_at": row["last_opened_at"] as String?,
                    "last_cooked_at": row["last_cooked_at"] as String?,
                    "open_count": (row["open_count"] as int?) ?? 0,
                    "cook_count": (row["cook_count"] as int?) ?? 0,
                    "pinned": ((row["pinned"] as int?) ?? 0) == 1,
                  }
                : null,
          },
        )
        .toList();
  }

  Future<List<Map<String, dynamic>>> listMealPlanChangesSince(String? sinceCursor) async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> rows = await db.rawQuery(
      """
      SELECT id, name, start_date, end_date, notes, updated_at, deleted_at
      FROM meal_plans
      WHERE (? IS NULL OR updated_at > ?)
      ORDER BY updated_at ASC
      """,
      <Object?>[sinceCursor, sinceCursor],
    );
    return rows
        .map(
          (Map<String, Object?> row) => <String, dynamic>{
            "entity_type": "meal_plan",
            "entity_id": row["id"] as String,
            "op": row["deleted_at"] == null ? "upsert" : "delete",
            "entity_version": 1,
            "updated_at_utc": row["updated_at"] as String,
            "source_scope": "local",
            "body": row["deleted_at"] == null
                ? <String, dynamic>{
                    "id": row["id"] as String,
                    "name": row["name"] as String,
                    "start_date": row["start_date"] as String?,
                    "end_date": row["end_date"] as String?,
                    "notes": row["notes"] as String?,
                  }
                : null,
          },
        )
        .toList();
  }

  Future<List<Map<String, dynamic>>> listMealPlanItemChangesSince(String? sinceCursor) async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> rows = await db.rawQuery(
      """
      SELECT id, meal_plan_id, recipe_id, servings_override, notes, planned_date, meal_slot, slot_label, sort_order,
             reminder_enabled, pre_reminder_minutes, start_cooking_prompt, updated_at, deleted_at
      FROM meal_plan_items
      WHERE (? IS NULL OR updated_at > ?)
      ORDER BY updated_at ASC
      """,
      <Object?>[sinceCursor, sinceCursor],
    );
    return rows
        .map(
          (Map<String, Object?> row) => <String, dynamic>{
            "entity_type": "meal_plan_item",
            "entity_id": row["id"] as String,
            "op": row["deleted_at"] == null ? "upsert" : "delete",
            "entity_version": 1,
            "updated_at_utc": row["updated_at"] as String,
            "source_scope": "local",
            "body": row["deleted_at"] == null
                ? <String, dynamic>{
                    "id": row["id"] as String,
                    "meal_plan_id": row["meal_plan_id"] as String,
                    "recipe_id": row["recipe_id"] as String,
                    "servings_override": (row["servings_override"] as num?)?.toDouble(),
                    "notes": row["notes"] as String?,
                    "planned_date": row["planned_date"] as String?,
                    "meal_slot": row["meal_slot"] as String?,
                    "slot_label": row["slot_label"] as String?,
                    "sort_order": (row["sort_order"] as num?)?.toInt() ?? 0,
                    "reminder_enabled": ((row["reminder_enabled"] as num?)?.toInt() ?? 0) == 1,
                    "pre_reminder_minutes": (row["pre_reminder_minutes"] as num?)?.toInt(),
                    "start_cooking_prompt": ((row["start_cooking_prompt"] as num?)?.toInt() ?? 0) == 1,
                  }
                : null,
          },
        )
        .toList();
  }

  Future<void> upsertReminderNotification(ReminderNotification reminder) async {
    final Database db = await _database.database;
    await db.insert(
      "reminder_notifications",
      <String, Object?>{
        "id": reminder.id,
        "type": reminder.type,
        "reference_type": reminder.referenceType,
        "reference_id": reminder.referenceId,
        "scheduled_time_utc": reminder.scheduledTimeUtc,
        "payload_json": reminder.payloadJson,
        "enabled": reminder.enabled ? 1 : 0,
        "updated_at": reminder.updatedAt ?? DateTime.now().toUtc().toIso8601String(),
        "deleted_at": null,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<List<ReminderNotification>> listReminderNotificationsForReference(String referenceType, String referenceId) async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> rows = await db.query(
      "reminder_notifications",
      where: "reference_type = ? AND reference_id = ? AND deleted_at IS NULL",
      whereArgs: <Object>[referenceType, referenceId],
      orderBy: "scheduled_time_utc ASC",
    );
    return rows
        .map(
          (Map<String, Object?> row) => ReminderNotification(
            id: row["id"]! as String,
            type: row["type"]! as String,
            referenceType: row["reference_type"]! as String,
            referenceId: row["reference_id"]! as String,
            scheduledTimeUtc: row["scheduled_time_utc"]! as String,
            payloadJson: row["payload_json"]! as String,
            enabled: ((row["enabled"] as num?)?.toInt() ?? 1) == 1,
            updatedAt: row["updated_at"] as String?,
          ),
        )
        .toList();
  }

  Future<void> deleteReminderNotification(String id, String deletedAtUtc) async {
    final Database db = await _database.database;
    await db.update(
      "reminder_notifications",
      <String, Object?>{"deleted_at": deletedAtUtc, "updated_at": deletedAtUtc},
      where: "id = ?",
      whereArgs: <Object>[id],
    );
  }

  Future<List<Map<String, dynamic>>> listMediaAssetChangesSince(String? sinceCursor) async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> rows = await db.rawQuery(
      """
      SELECT id, owner_type, owner_id, file_name, mime_type, relative_path, width, height, updated_at, deleted_at
      FROM media_assets
      WHERE (? IS NULL OR updated_at > ?)
      ORDER BY updated_at ASC
      """,
      <Object?>[sinceCursor, sinceCursor],
    );
    return rows
        .map(
          (Map<String, Object?> row) => <String, dynamic>{
            "entity_type": "media_asset",
            "entity_id": row["id"] as String,
            "op": row["deleted_at"] == null ? "upsert" : "delete",
            "entity_version": 1,
            "updated_at_utc": row["updated_at"] as String,
            "source_scope": "local",
            "body": row["deleted_at"] == null
                ? <String, dynamic>{
                    "id": row["id"] as String,
                    "owner_type": row["owner_type"] as String,
                    "owner_id": row["owner_id"] as String,
                    "file_name": row["file_name"] as String,
                    "mime_type": row["mime_type"] as String,
                    "relative_path": row["relative_path"] as String,
                    "width": (row["width"] as num?)?.toInt(),
                    "height": (row["height"] as num?)?.toInt(),
                  }
                : null,
          },
        )
        .toList();
  }

  Future<List<Map<String, dynamic>>> listRecipeChangesSince(String? sinceCursor) async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> rows = await db.rawQuery(
      """
      SELECT id, updated_at, deleted_at
      FROM recipes
      WHERE scope = 'local' AND (? IS NULL OR updated_at > ?)
      ORDER BY updated_at ASC
      """,
      <Object?>[sinceCursor, sinceCursor],
    );
    final List<Map<String, dynamic>> changes = <Map<String, dynamic>>[];
    for (final Map<String, Object?> row in rows) {
      final String recipeId = row["id"]! as String;
      final String updatedAt = row["updated_at"] as String? ?? DateTime.now().toUtc().toIso8601String();
      if (row["deleted_at"] != null) {
        changes.add(<String, dynamic>{
          "entity_type": "recipe",
          "entity_id": recipeId,
          "op": "delete",
          "entity_version": 1,
          "updated_at_utc": updatedAt,
          "source_scope": "local",
          "body": null,
        });
        continue;
      }
      final RecipeDetail? detail = await getRecipeById(recipeId);
      if (detail == null) {
        continue;
      }
      changes.add(<String, dynamic>{
        "entity_type": "recipe",
        "entity_id": recipeId,
        "op": "upsert",
        "entity_version": 1,
        "updated_at_utc": updatedAt,
        "source_scope": "local",
        "body": _recipeToSyncBody(detail),
      });
    }
    return changes;
  }

  Map<String, dynamic> _recipeToSyncBody(RecipeDetail recipe) {
    return <String, dynamic>{
      "id": recipe.id,
      "scope": recipe.scope,
      "title": recipe.title,
      "subtitle": recipe.subtitle,
      "author": recipe.author,
      "source_name": recipe.sourceName,
      "source_url": recipe.sourceUrl,
      "difficulty": recipe.difficulty,
      "notes": recipe.notes,
      "servings": recipe.servings,
      "prep_minutes": recipe.prepMinutes,
      "cook_minutes": recipe.cookMinutes,
      "total_minutes": recipe.totalMinutes,
      "cover_media_id": recipe.coverMediaId,
      "status": recipe.status,
      "equipment": recipe.equipment
          .map(
            (RecipeEquipmentItem item) => <String, dynamic>{
              "id": item.id,
              "name": item.name,
              "description": item.description,
              "notes": item.notes,
              "affiliate_url": item.affiliateUrl,
              "media_id": item.mediaId,
              "is_required": item.isRequired,
              "display_order": item.displayOrder,
            },
          )
          .toList(),
      "ingredients": recipe.ingredients
          .map(
            (RecipeIngredientItem item) => <String, dynamic>{
              "id": item.id,
              "raw_text": item.rawText,
              "quantity_value": item.quantityValue,
              "unit": item.unit,
              "ingredient_name": item.ingredientName,
              "substitutions": item.substitutions,
              "preparation_notes": item.preparationNotes,
              "media_id": item.mediaId,
              "is_optional": item.isOptional,
              "display_order": item.displayOrder,
            },
          )
          .toList(),
      "steps": recipe.steps
          .map(
            (RecipeStep step) => <String, dynamic>{
              "id": step.id,
              "title": step.title,
              "body_text": step.bodyText,
              "step_type": step.stepType,
              "estimated_seconds": step.estimatedSeconds,
              "media_id": step.mediaId,
              "display_order": step.displayOrder,
              "timers": step.timers
                  .map(
                    (StepTimer timer) => <String, dynamic>{
                      "id": timer.id,
                      "label": timer.label,
                      "duration_seconds": timer.durationSeconds,
                      "auto_start": timer.autoStart,
                      "alert_sound_key": timer.alertSoundKey,
                    },
                  )
                  .toList(),
            },
          )
          .toList(),
      "step_links": recipe.stepLinks
          .map(
            (StepLink link) => <String, dynamic>{
              "id": link.id,
              "step_id": link.stepId,
              "target_type": link.targetType,
              "target_id": link.targetId,
              "token_key": link.tokenKey,
              "label_snapshot": link.labelSnapshot,
              "label_override": link.labelOverride,
            },
          )
          .toList(),
    };
  }
}

