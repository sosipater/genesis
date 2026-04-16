import "dart:convert";
import "dart:io";

import "package:path/path.dart" as p;
import "package:sqflite/sqflite.dart";
import "package:uuid/uuid.dart";

import "../db/app_database.dart";
import "../models/recipe_models.dart";
import "recipe_editor_repository_port.dart";
import "repository_ports.dart";

String _searchNormalize(String text) {
  return text.trim().toLowerCase().replaceAll(RegExp(r"\s+"), " ");
}

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
            author: row["author"] as String?,
            scope: row["scope"]! as String,
            status: row["status"]! as String,
            updatedAt: row["updated_at"] as String?,
            isFavorite: ((row["is_favorite"] as int?) ?? 0) == 1,
            lastOpenedAt: row["last_opened_at"] as String?,
            lastCookedAt: row["last_cooked_at"] as String?,
            openCount: (row["open_count"] as int?) ?? 0,
            cookCount: (row["cook_count"] as int?) ?? 0,
            coverMediaId: row["cover_media_id"] as String?,
            tags: _parseTagsJson(row["tags_json"] as String?),
          ),
        )
        .toList();
  }

  @override
  Future<List<RecipeSummary>> listLocalRecipesForSubRecipePicker({required String excludeRecipeId}) async {
    final List<RecipeSummary> all = await listRecipes();
    return all.where((RecipeSummary r) => r.scope == "local" && r.id != excludeRecipeId).toList();
  }

  Future<List<String>> listTagNamesForFilter() async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> rows = await db.query(
      "tags",
      columns: <String>["name"],
      where: "deleted_at IS NULL",
      orderBy: "name COLLATE NOCASE ASC",
    );
    return rows.map((Map<String, Object?> row) => row["name"]! as String).toList();
  }

  Future<List<RecipeSummary>> searchRecipes({
    String query = "",
    String scope = "all",
    List<String> tagsMatchAll = const <String>[],
    bool ingredientFocus = false,
  }) async {
    final List<RecipeSummary> all = await listRecipes();
    final String q = query.trim().toLowerCase();
    final String qFolded = _searchNormalize(query);
    final Set<String> requiredTags =
        tagsMatchAll.map((String t) => t.trim().toLowerCase()).where((String t) => t.isNotEmpty).toSet();

    bool scopeMatch(RecipeSummary recipe) {
      if (scope == "all") return true;
      if (scope == "forked") return false;
      if (scope == "favorites") return recipe.isFavorite;
      return recipe.scope == scope;
    }

    bool tagsMatch(RecipeSummary recipe) {
      if (requiredTags.isEmpty) return true;
      final Set<String> have = recipe.tags.map((String t) => t.trim().toLowerCase()).toSet();
      return requiredTags.every(have.contains);
    }

    final List<RecipeSummary> candidates = all.where((RecipeSummary r) => scopeMatch(r) && tagsMatch(r)).toList();
    if (candidates.isEmpty) {
      return <RecipeSummary>[];
    }

    if (q.isEmpty) {
      candidates.sort((RecipeSummary a, RecipeSummary b) => a.title.toLowerCase().compareTo(b.title.toLowerCase()));
      return candidates;
    }

    final Set<String> ids = candidates.map((RecipeSummary r) => r.id).toSet();
    final Map<String, String> catalogNames = await _catalogIdToNameMap();
    final Map<String, List<_IngredientSearchRow>> ings = await _ingredientRowsByRecipeId(ids);
    final Map<String, List<String>> equipmentByRecipe = await _equipmentNamesByRecipeId(ids);
    final Map<String, List<String>> stepBodiesByRecipe = await _stepBodiesByRecipeId(ids);

    final List<_ScoredSummary> scored = <_ScoredSummary>[];
    for (final RecipeSummary recipe in candidates) {
      final _SearchScore s = _scoreRecipeForLibrarySearch(
        recipe: recipe,
        query: q,
        queryFolded: qFolded,
        catalogNamesById: catalogNames,
        ingredients: ings[recipe.id] ?? const <_IngredientSearchRow>[],
        equipmentNames: equipmentByRecipe[recipe.id] ?? const <String>[],
        stepBodies: stepBodiesByRecipe[recipe.id] ?? const <String>[],
        ingredientFocus: ingredientFocus,
      );
      if (!s.keep) {
        continue;
      }
      final String? hint = s.hints.isEmpty ? null : s.hints.map(_hintLabel).join(" · ");
      scored.add(
        _ScoredSummary(
          RecipeSummary(
            id: recipe.id,
            title: recipe.title,
            subtitle: recipe.subtitle,
            author: recipe.author,
            scope: recipe.scope,
            status: recipe.status,
            updatedAt: recipe.updatedAt,
            isFavorite: recipe.isFavorite,
            lastOpenedAt: recipe.lastOpenedAt,
            lastCookedAt: recipe.lastCookedAt,
            openCount: recipe.openCount,
            cookCount: recipe.cookCount,
            coverMediaId: recipe.coverMediaId,
            tags: recipe.tags,
            searchMatchHint: hint,
          ),
          s.score,
        ),
      );
    }
    scored.sort((_ScoredSummary a, _ScoredSummary b) {
      final int byScore = b.score.compareTo(a.score);
      if (byScore != 0) return byScore;
      return a.summary.title.toLowerCase().compareTo(b.summary.title.toLowerCase());
    });
    return scored.map((_ScoredSummary e) => e.summary).toList();
  }

  Future<Map<String, String>> _catalogIdToNameMap() async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> rows = await db.query(
      "catalog_ingredient",
      columns: <String>["id", "name"],
      where: "deleted_at IS NULL",
    );
    return <String, String>{
      for (final Map<String, Object?> row in rows) row["id"]! as String: row["name"]! as String,
    };
  }

  Future<Map<String, List<_IngredientSearchRow>>> _ingredientRowsByRecipeId(Set<String> recipeIds) async {
    if (recipeIds.isEmpty) {
      return <String, List<_IngredientSearchRow>>{};
    }
    final Database db = await _database.database;
    final String placeholders = List<String>.filled(recipeIds.length, "?").join(",");
    final List<Map<String, Object?>> rows = await db.rawQuery(
      """
      SELECT recipe_id, raw_text, ingredient_name, catalog_ingredient_id
      FROM recipe_ingredients
      WHERE deleted_at IS NULL AND recipe_id IN ($placeholders)
      """,
      recipeIds.toList(),
    );
    final Map<String, List<_IngredientSearchRow>> out = <String, List<_IngredientSearchRow>>{};
    for (final Map<String, Object?> row in rows) {
      final String rid = row["recipe_id"]! as String;
      out.putIfAbsent(rid, () => <_IngredientSearchRow>[]).add(
            _IngredientSearchRow(
              rawText: row["raw_text"]! as String,
              ingredientName: row["ingredient_name"] as String?,
              catalogIngredientId: row["catalog_ingredient_id"] as String?,
            ),
          );
    }
    return out;
  }

  Future<Map<String, List<String>>> _equipmentNamesByRecipeId(Set<String> recipeIds) async {
    if (recipeIds.isEmpty) {
      return <String, List<String>>{};
    }
    final Database db = await _database.database;
    final String placeholders = List<String>.filled(recipeIds.length, "?").join(",");
    final List<Map<String, Object?>> rows = await db.rawQuery(
      """
      SELECT recipe_id, name FROM recipe_equipment
      WHERE deleted_at IS NULL AND recipe_id IN ($placeholders)
      """,
      recipeIds.toList(),
    );
    final Map<String, List<String>> out = <String, List<String>>{};
    for (final Map<String, Object?> row in rows) {
      final String rid = row["recipe_id"]! as String;
      out.putIfAbsent(rid, () => <String>[]).add(row["name"]! as String);
    }
    return out;
  }

  Future<Map<String, List<String>>> _stepBodiesByRecipeId(Set<String> recipeIds) async {
    if (recipeIds.isEmpty) {
      return <String, List<String>>{};
    }
    final Database db = await _database.database;
    final String placeholders = List<String>.filled(recipeIds.length, "?").join(",");
    final List<Map<String, Object?>> rows = await db.rawQuery(
      """
      SELECT recipe_id, body_text FROM recipe_steps
      WHERE deleted_at IS NULL AND recipe_id IN ($placeholders)
      """,
      recipeIds.toList(),
    );
    final Map<String, List<String>> out = <String, List<String>>{};
    for (final Map<String, Object?> row in rows) {
      final String rid = row["recipe_id"]! as String;
      out.putIfAbsent(rid, () => <String>[]).add(row["body_text"]! as String);
    }
    return out;
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
              alertVibrate: (timerRow["alert_vibrate"] as int? ?? 0) == 1,
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

    final List<String> tags = _parseTagsJson(recipeRow["tags_json"] as String?);
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
      tags: tags,
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
              globalEquipmentId: row["global_equipment_id"] as String?,
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
              catalogIngredientId: row["catalog_ingredient_id"] as String?,
              subRecipeId: row["sub_recipe_id"] as String?,
              subRecipeUsageType: row["sub_recipe_usage_type"] as String?,
              subRecipeMultiplier: (row["sub_recipe_multiplier"] as num?)?.toDouble(),
              subRecipeDisplayName: row["sub_recipe_display_name"] as String?,
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
          "tags_json": jsonEncode(recipe.tags),
          "updated_at": updatedAt,
          "deleted_at": null,
        },
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
      await _syncRecipeTags(txn, recipe.id, recipe.tags, updatedAt);
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
          "global_equipment_id": item.globalEquipmentId,
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
          "catalog_ingredient_id": item.catalogIngredientId,
          "sub_recipe_id": item.subRecipeId,
          "sub_recipe_usage_type": item.subRecipeUsageType,
          "sub_recipe_multiplier": item.subRecipeMultiplier,
          "sub_recipe_display_name": item.subRecipeDisplayName,
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
            "alert_vibrate": timer.alertVibrate ? 1 : 0,
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
            author: row["author"] as String?,
            scope: row["scope"]! as String,
            status: row["status"]! as String,
            updatedAt: row["updated_at"] as String?,
            coverMediaId: row["cover_media_id"] as String?,
            tags: _parseTagsJson(row["tags_json"] as String?),
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
            author: row["author"] as String?,
            scope: row["scope"]! as String,
            status: row["status"]! as String,
            updatedAt: row["updated_at"] as String?,
            coverMediaId: row["cover_media_id"] as String?,
            tags: _parseTagsJson(row["tags_json"] as String?),
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
            author: row["author"] as String?,
            scope: row["scope"]! as String,
            status: row["status"]! as String,
            updatedAt: row["updated_at"] as String?,
            isFavorite: ((row["is_favorite"] as int?) ?? 0) == 1,
            lastOpenedAt: row["last_opened_at"] as String?,
            lastCookedAt: row["last_cooked_at"] as String?,
            openCount: (row["open_count"] as int?) ?? 0,
            cookCount: (row["cook_count"] as int?) ?? 0,
            coverMediaId: row["cover_media_id"] as String?,
            tags: _parseTagsJson(row["tags_json"] as String?),
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
      "tags": recipe.tags,
      "equipment": recipe.equipment
          .map(
            (RecipeEquipmentItem item) => <String, dynamic>{
              "id": item.id,
              "name": item.name,
              "description": item.description,
              "notes": item.notes,
              "affiliate_url": item.affiliateUrl,
              "media_id": item.mediaId,
              "global_equipment_id": item.globalEquipmentId,
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
              "catalog_ingredient_id": item.catalogIngredientId,
              "sub_recipe_id": item.subRecipeId,
              "sub_recipe_usage_type": item.subRecipeUsageType,
              "sub_recipe_multiplier": item.subRecipeMultiplier,
              "sub_recipe_display_name": item.subRecipeDisplayName,
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
                      "alert_vibrate": timer.alertVibrate,
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

  List<String> _parseTagsJson(String? raw) {
    if (raw == null || raw.isEmpty) {
      return <String>[];
    }
    try {
      final Object? decoded = jsonDecode(raw);
      if (decoded is! List<dynamic>) {
        return <String>[];
      }
      return decoded.map((dynamic e) => e.toString()).where((String s) => s.trim().isNotEmpty).toList();
    } catch (_) {
      return <String>[];
    }
  }

  Future<void> _syncRecipeTags(Transaction txn, String recipeId, List<String> tagNames, String updatedAtUtc) async {
    final Uuid uuid = const Uuid();
    final Set<String> seen = <String>{};
    final List<String> ordered = <String>[];
    for (final String raw in tagNames) {
      final String name = raw.trim();
      if (name.isEmpty) {
        continue;
      }
      final String key = name.toLowerCase();
      if (seen.contains(key)) {
        continue;
      }
      seen.add(key);
      ordered.add(name);
    }
    await txn.delete("recipe_tags", where: "recipe_id = ?", whereArgs: <Object>[recipeId]);
    for (final String name in ordered) {
      final List<Map<String, Object?>> found = await txn.rawQuery(
        "SELECT id, deleted_at FROM tags WHERE lower(name) = lower(?) LIMIT 1",
        <Object>[name],
      );
      late final String tid;
      if (found.isEmpty) {
        tid = uuid.v4();
        await txn.insert("tags", <String, Object?>{
          "id": tid,
          "name": name,
          "color": null,
          "entity_version": 1,
          "created_at": updatedAtUtc,
          "updated_at": updatedAtUtc,
          "deleted_at": null,
        });
      } else {
        tid = found.first["id"]! as String;
        if (found.first["deleted_at"] != null) {
          await txn.rawUpdate(
            "UPDATE tags SET deleted_at = NULL, name = ?, updated_at = ?, entity_version = entity_version + 1 WHERE id = ?",
            <Object>[name, updatedAtUtc, tid],
          );
        }
      }
      await txn.insert(
        "recipe_tags",
        <String, Object?>{"recipe_id": recipeId, "tag_id": tid},
        conflictAlgorithm: ConflictAlgorithm.ignore,
      );
    }
  }

  @override
  Future<List<GlobalEquipmentSummary>> listGlobalEquipmentForPicker() async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> rows = await db.query(
      "global_equipment",
      where: "deleted_at IS NULL",
      orderBy: "name COLLATE NOCASE ASC",
    );
    return rows
        .map(
          (Map<String, Object?> row) => GlobalEquipmentSummary(
            id: row["id"]! as String,
            name: row["name"]! as String,
            notes: row["notes"] as String?,
            mediaId: row["media_id"] as String?,
          ),
        )
        .toList();
  }

  @override
  Future<String> createGlobalEquipmentRecord({required String name, String? notes}) async {
    final Database db = await _database.database;
    final String trimmed = name.trim();
    if (trimmed.isEmpty) {
      throw ArgumentError("global equipment name cannot be empty");
    }
    final String id = const Uuid().v4();
    final String now = DateTime.now().toUtc().toIso8601String();
    await db.insert("global_equipment", <String, Object?>{
      "id": id,
      "name": trimmed,
      "notes": notes,
      "media_id": null,
      "entity_version": 1,
      "created_at": now,
      "updated_at": now,
      "deleted_at": null,
    });
    return id;
  }

  Future<List<Map<String, dynamic>>> listGlobalEquipmentChangesSince(String? sinceCursor) async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> rows = await db.rawQuery(
      """
      SELECT id, name, notes, media_id, entity_version, created_at, updated_at, deleted_at
      FROM global_equipment
      WHERE (? IS NULL OR updated_at > ?)
      ORDER BY updated_at ASC
      """,
      <Object?>[sinceCursor, sinceCursor],
    );
    return rows.map((Map<String, Object?> row) {
      final bool isTombstone = row["deleted_at"] != null;
      final int ev = (row["entity_version"] as int?) ?? 1;
      return <String, dynamic>{
        "entity_type": "global_equipment",
        "entity_id": row["id"]! as String,
        "op": isTombstone ? "delete" : "upsert",
        "entity_version": ev,
        "updated_at_utc": row["updated_at"]! as String,
        "source_scope": "local",
        "body": isTombstone
            ? null
            : <String, dynamic>{
                "id": row["id"]! as String,
                "name": row["name"]! as String,
                "notes": row["notes"],
                "media_id": row["media_id"],
                "entity_version": ev,
                "created_at": row["created_at"]! as String,
                "updated_at": row["updated_at"]! as String,
              },
      };
    }).toList();
  }

  Future<List<Map<String, dynamic>>> listTagChangesSince(String? sinceCursor) async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> rows = await db.rawQuery(
      """
      SELECT id, name, color, entity_version, created_at, updated_at, deleted_at
      FROM tags
      WHERE (? IS NULL OR updated_at > ?)
      ORDER BY updated_at ASC
      """,
      <Object?>[sinceCursor, sinceCursor],
    );
    return rows.map((Map<String, Object?> row) {
      final bool isTombstone = row["deleted_at"] != null;
      final int ev = (row["entity_version"] as int?) ?? 1;
      return <String, dynamic>{
        "entity_type": "tag",
        "entity_id": row["id"]! as String,
        "op": isTombstone ? "delete" : "upsert",
        "entity_version": ev,
        "updated_at_utc": row["updated_at"]! as String,
        "source_scope": "local",
        "body": isTombstone
            ? null
            : <String, dynamic>{
                "id": row["id"]! as String,
                "name": row["name"]! as String,
                "color": row["color"],
                "entity_version": ev,
                "created_at": row["created_at"]! as String,
                "updated_at": row["updated_at"]! as String,
              },
      };
    }).toList();
  }

  Future<void> upsertGlobalEquipmentFromSync(Map<String, dynamic> body, String updatedAtUtc) async {
    final Database db = await _database.database;
    await db.insert(
      "global_equipment",
      <String, Object?>{
        "id": body["id"] as String,
        "name": body["name"] as String,
        "notes": body["notes"] as String?,
        "media_id": body["media_id"] as String?,
        "entity_version": (body["entity_version"] as num?)?.toInt() ?? 1,
        "created_at": (body["created_at"] as String?) ?? updatedAtUtc,
        "updated_at": updatedAtUtc,
        "deleted_at": null,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<void> tombstoneGlobalEquipment(String id, String updatedAtUtc) async {
    final Database db = await _database.database;
    await db.update(
      "global_equipment",
      <String, Object?>{"deleted_at": updatedAtUtc, "updated_at": updatedAtUtc},
      where: "id = ?",
      whereArgs: <Object>[id],
    );
  }

  Future<void> upsertTagFromSync(Map<String, dynamic> body, String updatedAtUtc) async {
    final Database db = await _database.database;
    await db.insert(
      "tags",
      <String, Object?>{
        "id": body["id"] as String,
        "name": body["name"] as String,
        "color": body["color"] as String?,
        "entity_version": (body["entity_version"] as num?)?.toInt() ?? 1,
        "created_at": (body["created_at"] as String?) ?? updatedAtUtc,
        "updated_at": updatedAtUtc,
        "deleted_at": null,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<void> tombstoneTag(String id, String updatedAtUtc) async {
    final Database db = await _database.database;
    await db.update(
      "tags",
      <String, Object?>{"deleted_at": updatedAtUtc, "updated_at": updatedAtUtc},
      where: "id = ?",
      whereArgs: <Object>[id],
    );
  }

  static String _normalizeCatalogName(String name) {
    return name.trim().toLowerCase().replaceAll(RegExp(r"\s+"), " ");
  }

  @override
  Future<List<CatalogIngredientSummary>> listCatalogIngredientsForPicker() async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> rows = await db.query(
      "catalog_ingredient",
      where: "deleted_at IS NULL",
      orderBy: "name COLLATE NOCASE ASC",
    );
    return rows
        .map(
          (Map<String, Object?> row) => CatalogIngredientSummary(
            id: row["id"]! as String,
            name: row["name"]! as String,
            notes: row["notes"] as String?,
          ),
        )
        .toList();
  }

  @override
  Future<List<CatalogIngredientSummary>> searchCatalogIngredients(String query, {int limit = 20}) async {
    final String needle = _normalizeCatalogName(query);
    if (needle.isEmpty) {
      return const <CatalogIngredientSummary>[];
    }
    final Database db = await _database.database;
    final String like = "%$needle%";
    final List<Map<String, Object?>> rows = await db.rawQuery(
      """
      SELECT id, name, notes FROM catalog_ingredient
      WHERE deleted_at IS NULL AND normalized_name LIKE ?
      ORDER BY name COLLATE NOCASE ASC
      LIMIT ?
      """,
      <Object>[like, limit],
    );
    return rows
        .map(
          (Map<String, Object?> row) => CatalogIngredientSummary(
            id: row["id"]! as String,
            name: row["name"]! as String,
            notes: row["notes"] as String?,
          ),
        )
        .toList();
  }

  @override
  Future<String> createCatalogIngredientRecord({required String name, String? notes}) async {
    final Database db = await _database.database;
    final String trimmed = name.trim();
    if (trimmed.isEmpty) {
      throw ArgumentError("catalog ingredient name cannot be empty");
    }
    final String id = const Uuid().v4();
    final String now = DateTime.now().toUtc().toIso8601String();
    final String norm = _normalizeCatalogName(trimmed);
    await db.insert("catalog_ingredient", <String, Object?>{
      "id": id,
      "name": trimmed,
      "normalized_name": norm,
      "notes": notes,
      "entity_version": 1,
      "created_at": now,
      "updated_at": now,
      "deleted_at": null,
    });
    return id;
  }

  Future<List<Map<String, dynamic>>> listCatalogIngredientChangesSince(String? sinceCursor) async {
    final Database db = await _database.database;
    final List<Map<String, Object?>> rows = await db.rawQuery(
      """
      SELECT id, name, normalized_name, notes, entity_version, created_at, updated_at, deleted_at
      FROM catalog_ingredient
      WHERE (? IS NULL OR updated_at > ?)
      ORDER BY updated_at ASC
      """,
      <Object?>[sinceCursor, sinceCursor],
    );
    return rows.map((Map<String, Object?> row) {
      final bool isTombstone = row["deleted_at"] != null;
      final int ev = (row["entity_version"] as int?) ?? 1;
      return <String, dynamic>{
        "entity_type": "catalog_ingredient",
        "entity_id": row["id"]! as String,
        "op": isTombstone ? "delete" : "upsert",
        "entity_version": ev,
        "updated_at_utc": row["updated_at"]! as String,
        "source_scope": "local",
        "body": isTombstone
            ? null
            : <String, dynamic>{
                "id": row["id"]! as String,
                "name": row["name"]! as String,
                "normalized_name": row["normalized_name"]! as String,
                "notes": row["notes"],
                "entity_version": ev,
                "created_at": row["created_at"]! as String,
                "updated_at": row["updated_at"]! as String,
              },
      };
    }).toList();
  }

  Future<void> upsertCatalogIngredientFromSync(Map<String, dynamic> body, String updatedAtUtc) async {
    final Database db = await _database.database;
    final String name = body["name"] as String;
    final String normalized = (body["normalized_name"] as String?) ?? _normalizeCatalogName(name);
    await db.insert(
      "catalog_ingredient",
      <String, Object?>{
        "id": body["id"] as String,
        "name": name,
        "normalized_name": normalized,
        "notes": body["notes"] as String?,
        "entity_version": (body["entity_version"] as num?)?.toInt() ?? 1,
        "created_at": (body["created_at"] as String?) ?? updatedAtUtc,
        "updated_at": updatedAtUtc,
        "deleted_at": null,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<void> tombstoneCatalogIngredient(String id, String updatedAtUtc) async {
    final Database db = await _database.database;
    await db.update(
      "catalog_ingredient",
      <String, Object?>{"deleted_at": updatedAtUtc, "updated_at": updatedAtUtc},
      where: "id = ?",
      whereArgs: <Object>[id],
    );
  }
}

class _IngredientSearchRow {
  final String rawText;
  final String? ingredientName;
  final String? catalogIngredientId;

  const _IngredientSearchRow({
    required this.rawText,
    this.ingredientName,
    this.catalogIngredientId,
  });
}

class _SearchScore {
  final bool keep;
  final int score;
  final int ingredientScore;
  final List<String> hints;

  const _SearchScore({
    required this.keep,
    required this.score,
    required this.ingredientScore,
    required this.hints,
  });
}

class _ScoredSummary {
  final RecipeSummary summary;
  final int score;

  const _ScoredSummary(this.summary, this.score);
}

_SearchScore _scoreRecipeForLibrarySearch({
  required RecipeSummary recipe,
  required String query,
  required String queryFolded,
  required Map<String, String> catalogNamesById,
  required List<_IngredientSearchRow> ingredients,
  required List<String> equipmentNames,
  required List<String> stepBodies,
  required bool ingredientFocus,
}) {
  int score = 0;
  int ingScore = 0;
  final Set<String> hintSet = <String>{};
  final String title = recipe.title.toLowerCase();
  if (title.contains(query)) {
    score += 50;
  }
  final String? sub = recipe.subtitle?.toLowerCase();
  if (sub != null && sub.contains(query)) {
    score += 25;
    hintSet.add("subtitle");
  }
  final String? auth = recipe.author?.toLowerCase();
  if (auth != null && auth.contains(query)) {
    score += 15;
    hintSet.add("author");
  }
  for (final String tag in recipe.tags) {
    final String t = tag.trim().toLowerCase();
    if (t.contains(query) || (queryFolded.isNotEmpty && _searchNormalize(tag).contains(queryFolded))) {
      score += 24;
      hintSet.add("tag");
    }
  }
  for (final _IngredientSearchRow ing in ingredients) {
    final String raw = ing.rawText.toLowerCase();
    if (raw.contains(query) || (queryFolded.isNotEmpty && _searchNormalize(ing.rawText).contains(queryFolded))) {
      score += 20;
      ingScore += 20;
      hintSet.add("ingredient");
    }
    final String? iname = ing.ingredientName?.toLowerCase();
    if (iname != null &&
        (iname.contains(query) ||
            (queryFolded.isNotEmpty && _searchNormalize(ing.ingredientName!).contains(queryFolded)))) {
      score += 15;
      ingScore += 15;
      hintSet.add("ingredient");
    }
    final String? cid = ing.catalogIngredientId;
    if (cid != null) {
      final String? cname = catalogNamesById[cid];
      if (cname != null) {
        final String cn = cname.toLowerCase();
        if (cn.contains(query) || (queryFolded.isNotEmpty && _searchNormalize(cname).contains(queryFolded))) {
          score += 22;
          ingScore += 22;
          hintSet.add("catalog");
        }
      }
    }
  }
  for (final String name in equipmentNames) {
    if (name.toLowerCase().contains(query)) {
      score += 15;
      hintSet.add("equipment");
    }
  }
  for (final String body in stepBodies) {
    if (body.toLowerCase().contains(query)) {
      score += 10;
      hintSet.add("step");
    }
  }
  if (ingredientFocus && ingScore == 0) {
    return const _SearchScore(keep: false, score: 0, ingredientScore: 0, hints: <String>[]);
  }
  if (score == 0) {
    return _SearchScore(keep: false, score: 0, ingredientScore: ingScore, hints: const <String>[]);
  }
  final List<String> sortedHints = hintSet.toList()..sort();
  return _SearchScore(keep: true, score: score, ingredientScore: ingScore, hints: sortedHints);
}

String _hintLabel(String key) {
  switch (key) {
    case "subtitle":
      return "Subtitle";
    case "author":
      return "Author";
    case "tag":
      return "Tag";
    case "ingredient":
      return "Ingredient";
    case "catalog":
      return "Catalog item";
    case "equipment":
      return "Equipment";
    case "step":
      return "Step";
    default:
      return key;
  }
}
