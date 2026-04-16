import "package:uuid/uuid.dart";

import "../../config/app_config.dart";
import "../models/recipe_models.dart";
import "../models/sync_models.dart";
import "../repositories/recipe_repository.dart";
import "../repositories/sync_meta_repository.dart";
import "sync_api_client.dart";

class SyncService {
  final SyncApiClient _apiClient;
  final RecipeRepository _recipeRepository;
  final SyncMetaRepository _syncMetaRepository;
  final String _deviceId;
  final String _sessionId;
  final Uuid _uuid;

  SyncService(
    this._apiClient,
    this._recipeRepository,
    this._syncMetaRepository, {
    required String deviceId,
    required String sessionId,
    Uuid? uuid,
  })  : _deviceId = deviceId,
        _sessionId = sessionId,
        _uuid = uuid ?? const Uuid();

  Future<SyncStatus> testConnection(String host) async {
    try {
      final Map<String, dynamic> response = await _apiClient.health(host);
      final String message = "Connected: ${response["status"]}";
      await _syncMetaRepository.setLastStatus(message);
      return SyncStatus(success: true, message: message);
    } catch (error) {
      final String message = "Connection failed: $error";
      await _syncMetaRepository.setLastStatus(message);
      return SyncStatus(success: false, message: message);
    }
  }

  Future<SyncStatus> runSync(String host) async {
    try {
      final String now = DateTime.now().toUtc().toIso8601String();
      final String? cursor = await _syncMetaRepository.getCursor();
      final List<Map<String, dynamic>> localRecipeChanges = await _recipeRepository.listRecipeChangesSince(cursor);
      final List<Map<String, dynamic>> localMealPlanChanges = await _recipeRepository.listMealPlanChangesSince(cursor);
      final List<Map<String, dynamic>> localMealPlanItemChanges = await _recipeRepository.listMealPlanItemChangesSince(cursor);
      final List<Map<String, dynamic>> localMediaAssetChanges = await _recipeRepository.listMediaAssetChangesSince(cursor);
      final List<Map<String, dynamic>> localUserStateChanges = await _recipeRepository.listRecipeUserStateChangesSince(cursor);
      final List<Map<String, dynamic>> localChanges = <Map<String, dynamic>>[
        ...localRecipeChanges,
        ...localMealPlanChanges,
        ...localMealPlanItemChanges,
        ...localMediaAssetChanges,
        ...localUserStateChanges,
      ];
      final SyncEnvelope pushEnvelope = SyncEnvelope(
        syncProtocolVersion: kAppConfig.syncProtocolVersion,
        requestId: _uuid.v4(),
        sessionId: _sessionId,
        deviceId: _deviceId,
        sentAtUtc: now,
        payload: <String, dynamic>{
          "since_cursor": cursor,
          "next_cursor": null,
          "changes": localChanges,
        },
      );
      await _apiClient.push(host, pushEnvelope);

      final SyncEnvelope pullEnvelope = SyncEnvelope(
        syncProtocolVersion: kAppConfig.syncProtocolVersion,
        requestId: _uuid.v4(),
        sessionId: _sessionId,
        deviceId: _deviceId,
        sentAtUtc: now,
        payload: <String, dynamic>{
          "since_cursor": cursor,
          "next_cursor": null,
          "changes": <Map<String, dynamic>>[],
        },
      );
      final SyncEnvelope pullResult = await _apiClient.pull(host, pullEnvelope);
      final List<dynamic> changes = (pullResult.payload["changes"] as List?) ?? <dynamic>[];
      int conflicts = 0;
      for (final dynamic rawChange in changes) {
        final Map<String, dynamic> change = (rawChange as Map).cast<String, dynamic>();
        final String entityType = change["entity_type"] as String;
        final String op = change["op"] as String;
        if (op == "delete") {
          continue;
        }
        final Map<String, dynamic>? body = (change["body"] as Map?)?.cast<String, dynamic>();
        if (entityType == "recipe") {
          if (body == null) {
            continue;
          }
          final RecipeDetail detail = syncBodyToRecipeDetail(body);
          await _recipeRepository.upsertRecipeGraph(detail, updatedAt: change["updated_at_utc"] as String);
          continue;
        }
        if (entityType == "collection") {
          if (op == "delete") {
            await _recipeRepository.deleteCollection(change["entity_id"] as String, change["updated_at_utc"] as String);
          } else if (body != null) {
            await _recipeRepository.upsertCollection(
              id: body["id"] as String,
              name: body["name"] as String,
              updatedAtUtc: change["updated_at_utc"] as String,
            );
          }
          continue;
        }
        if (entityType == "collection_item") {
          if (op == "delete") {
            await _recipeRepository.deleteCollectionItem(change["entity_id"] as String, change["updated_at_utc"] as String);
          } else if (body != null) {
            await _recipeRepository.upsertCollectionItem(
              id: body["id"] as String,
              collectionId: body["collection_id"] as String,
              recipeId: body["recipe_id"] as String,
              updatedAtUtc: change["updated_at_utc"] as String,
            );
          }
          continue;
        }
        if (entityType == "meal_plan") {
          if (op == "delete") {
            await _recipeRepository.deleteMealPlan(change["entity_id"] as String, change["updated_at_utc"] as String);
          } else if (body != null) {
            await _recipeRepository.createMealPlan(
              id: body["id"] as String,
              name: body["name"] as String,
              startDate: body["start_date"] as String?,
              endDate: body["end_date"] as String?,
              notes: body["notes"] as String?,
              updatedAtUtc: change["updated_at_utc"] as String,
            );
          }
          continue;
        }
        if (entityType == "meal_plan_item") {
          if (op == "delete") {
            await _recipeRepository.removeMealPlanItem(change["entity_id"] as String, change["updated_at_utc"] as String);
          } else if (body != null) {
            await _recipeRepository.addMealPlanItem(
              id: body["id"] as String,
              mealPlanId: body["meal_plan_id"] as String,
              recipeId: body["recipe_id"] as String,
              servingsOverride: (body["servings_override"] as num?)?.toDouble(),
              notes: body["notes"] as String?,
              plannedDate: body["planned_date"] as String?,
              mealSlot: body["meal_slot"] as String?,
              slotLabel: body["slot_label"] as String?,
              sortOrder: (body["sort_order"] as num?)?.toInt() ?? 0,
              reminderEnabled: (body["reminder_enabled"] as bool?) ?? false,
              preReminderMinutes: (body["pre_reminder_minutes"] as num?)?.toInt(),
              startCookingPrompt: (body["start_cooking_prompt"] as bool?) ?? false,
              updatedAtUtc: change["updated_at_utc"] as String,
            );
          }
          continue;
        }
        if (entityType == "grocery_list") {
          if (op == "delete") {
            await _recipeRepository.deleteGroceryList(change["entity_id"] as String, change["updated_at_utc"] as String);
          } else if (body != null) {
            await _recipeRepository.createGroceryList(
              id: body["id"] as String,
              mealPlanId: body["meal_plan_id"] as String?,
              name: body["name"] as String,
              generatedAtUtc: body["generated_at"] as String? ?? change["updated_at_utc"] as String,
            );
          }
          continue;
        }
        if (entityType == "grocery_list_item") {
          if (op == "delete") {
            await _recipeRepository.deleteGroceryListItem(change["entity_id"] as String, change["updated_at_utc"] as String);
          } else if (body != null) {
            await _recipeRepository.upsertGroceryListItem(
              id: body["id"] as String,
              groceryListId: body["grocery_list_id"] as String,
              name: body["name"] as String,
              quantityValue: (body["quantity_value"] as num?)?.toDouble(),
              unit: body["unit"] as String?,
              checked: body["checked"] as bool? ?? false,
              sourceRecipeIds: ((body["source_recipe_ids"] as List?) ?? const <dynamic>[])
                  .map((dynamic value) => value as String)
                  .toList(),
              sourceType: (body["source_type"] as String?) ?? "generated",
              generatedGroupKey: body["generated_group_key"] as String?,
              wasUserModified: body["was_user_modified"] as bool? ?? false,
              sortOrder: (body["sort_order"] as num?)?.toInt() ?? 0,
              updatedAtUtc: change["updated_at_utc"] as String,
            );
          }
          continue;
        }
        if (entityType == "recipe_user_state") {
          if (op == "delete") {
            await _recipeRepository.deleteRecipeUserState(change["entity_id"] as String, change["updated_at_utc"] as String);
          } else if (body != null) {
            await _recipeRepository.upsertRecipeUserState(
              recipeId: body["recipe_id"] as String,
              isFavorite: ((body["is_favorite"] is bool)
                      ? body["is_favorite"] as bool
                      : ((body["is_favorite"] as num?)?.toInt() ?? 0) == 1),
              lastOpenedAt: body["last_opened_at"] as String?,
              lastCookedAt: body["last_cooked_at"] as String?,
              openCount: (body["open_count"] as num?)?.toInt() ?? 0,
              cookCount: (body["cook_count"] as num?)?.toInt() ?? 0,
              updatedAtUtc: change["updated_at_utc"] as String,
            );
          }
          continue;
        }
        if (entityType == "media_asset") {
          if (op == "delete") {
            await _recipeRepository.deleteMediaAsset(change["entity_id"] as String, change["updated_at_utc"] as String);
          } else if (body != null) {
            await _recipeRepository.upsertMediaAsset(
              MediaAsset(
                id: body["id"] as String,
                ownerType: body["owner_type"] as String,
                ownerId: body["owner_id"] as String,
                fileName: body["file_name"] as String,
                mimeType: body["mime_type"] as String,
                relativePath: body["relative_path"] as String,
                width: (body["width"] as num?)?.toInt(),
                height: (body["height"] as num?)?.toInt(),
              ),
              updatedAtUtc: change["updated_at_utc"] as String,
            );
          }
        }
      }

      final String? nextCursor = pullResult.payload["next_cursor"] as String?;
      if (nextCursor != null) {
        await _syncMetaRepository.setCursor(nextCursor);
      }
      await _syncMetaRepository.setLastStatus(
        "Sync complete: ${changes.length} changes",
        syncedAtUtc: now,
      );
      return SyncStatus(
        success: true,
        message: "Sync complete",
        lastSyncAtUtc: now,
        appliedChanges: changes.length,
        conflicts: conflicts,
      );
    } catch (error) {
      final String message = "Sync failed: $error";
      await _syncMetaRepository.setLastStatus(message);
      return SyncStatus(success: false, message: message);
    }
  }

}

RecipeDetail syncBodyToRecipeDetail(Map<String, dynamic> body) {
  final List<RecipeEquipmentItem> equipment = ((body["equipment"] as List?) ?? const <dynamic>[])
        .map((dynamic raw) {
      final Map<String, dynamic> item = (raw as Map).cast<String, dynamic>();
      return RecipeEquipmentItem(
        id: item["id"] as String,
        recipeId: body["id"] as String,
        name: item["name"] as String,
        description: item["description"] as String?,
        notes: item["notes"] as String?,
        affiliateUrl: item["affiliate_url"] as String?,
        mediaId: item["media_id"] as String?,
        isRequired: item["is_required"] as bool,
        displayOrder: item["display_order"] as int,
      );
    }).toList();
  final List<RecipeIngredientItem> ingredients = ((body["ingredients"] as List?) ?? const <dynamic>[])
        .map((dynamic raw) {
      final Map<String, dynamic> item = (raw as Map).cast<String, dynamic>();
      return RecipeIngredientItem(
        id: item["id"] as String,
        recipeId: body["id"] as String,
        rawText: item["raw_text"] as String,
        quantityValue: (item["quantity_value"] as num?)?.toDouble(),
        unit: item["unit"] as String?,
        ingredientName: item["ingredient_name"] as String?,
        substitutions: item["substitutions"] as String?,
        preparationNotes: item["preparation_notes"] as String?,
        mediaId: item["media_id"] as String?,
        isOptional: item["is_optional"] as bool,
        displayOrder: item["display_order"] as int,
      );
    }).toList();
  final List<StepLink> stepLinks = ((body["step_links"] as List?) ?? const <dynamic>[]).map((dynamic raw) {
    final Map<String, dynamic> link = (raw as Map).cast<String, dynamic>();
    return StepLink(
      id: link["id"] as String,
      stepId: link["step_id"] as String,
      targetType: link["target_type"] as String,
      targetId: link["target_id"] as String,
      tokenKey: link["token_key"] as String,
      labelSnapshot: link["label_snapshot"] as String,
      labelOverride: link["label_override"] as String?,
    );
  }).toList();

  final List<RecipeStep> steps = ((body["steps"] as List?) ?? const <dynamic>[]).map((dynamic raw) {
      final Map<String, dynamic> step = (raw as Map).cast<String, dynamic>();
      final List<StepTimer> timers = ((step["timers"] as List?) ?? const <dynamic>[]).map((dynamic timerRaw) {
        final Map<String, dynamic> timer = (timerRaw as Map).cast<String, dynamic>();
        return StepTimer(
          id: timer["id"] as String,
          stepId: step["id"] as String,
          label: timer["label"] as String,
          durationSeconds: timer["duration_seconds"] as int,
          autoStart: timer["auto_start"] as bool,
          alertSoundKey: timer["alert_sound_key"] as String?,
        );
      }).toList();
      return RecipeStep(
        id: step["id"] as String,
        recipeId: body["id"] as String,
        title: step["title"] as String?,
        bodyText: step["body_text"] as String,
        stepType: step["step_type"] as String,
        estimatedSeconds: step["estimated_seconds"] as int?,
        mediaId: step["media_id"] as String?,
        displayOrder: step["display_order"] as int,
        timers: timers,
      );
    }).toList();

  return RecipeDetail(
      id: body["id"] as String,
      title: body["title"] as String,
      subtitle: body["subtitle"] as String?,
      scope: (body["scope"] as String?) ?? "local",
      status: body["status"] as String,
      author: body["author"] as String?,
      sourceName: body["source_name"] as String?,
      sourceUrl: body["source_url"] as String?,
      difficulty: body["difficulty"] as String?,
      notes: body["notes"] as String?,
      servings: (body["servings"] as num?)?.toDouble(),
      prepMinutes: body["prep_minutes"] as int?,
      cookMinutes: body["cook_minutes"] as int?,
      totalMinutes: body["total_minutes"] as int?,
      coverMediaId: body["cover_media_id"] as String?,
      equipment: equipment,
      ingredients: ingredients,
      steps: steps,
      stepLinks: stepLinks,
  );
}

