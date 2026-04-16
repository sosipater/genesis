import "package:flutter_test/flutter_test.dart";
import "package:recipe_forge_mobile/data/sync/sync_service.dart";

void main() {
  test("maps sync recipe body into recipe detail", () {
    final Map<String, dynamic> body = <String, dynamic>{
      "id": "recipe-1",
      "scope": "local",
      "title": "Pasta",
      "status": "draft",
      "source_name": "Grandma",
      "source_url": "https://example.com",
      "difficulty": "easy",
      "prep_minutes": 10,
      "cook_minutes": 20,
      "total_minutes": 30,
      "cover_media_id": "media-cover-1",
      "equipment": <Map<String, dynamic>>[
        <String, dynamic>{
          "id": "eq-1",
          "name": "Pot",
          "description": null,
          "media_id": "media-eq-1",
          "is_required": true,
          "display_order": 0,
        },
      ],
      "ingredients": <Map<String, dynamic>>[
        <String, dynamic>{
          "id": "ing-1",
          "raw_text": "salt",
          "quantity_value": null,
          "unit": null,
          "ingredient_name": "salt",
          "media_id": "media-ing-1",
          "is_optional": false,
          "display_order": 0,
        },
      ],
      "steps": <Map<String, dynamic>>[
        <String, dynamic>{
          "id": "st-1",
          "title": "Boil",
          "body_text": "Boil water",
          "step_type": "instruction",
          "estimated_seconds": 60,
          "media_id": "media-step-1",
          "display_order": 0,
          "timers": <Map<String, dynamic>>[
            <String, dynamic>{
              "id": "tm-1",
              "label": "Boil",
              "duration_seconds": 60,
              "auto_start": false,
              "alert_sound_key": "ding",
            },
          ],
        },
      ],
    };

    final recipe = syncBodyToRecipeDetail(body);
    expect(recipe.title, "Pasta");
    expect(recipe.equipment.first.name, "Pot");
    expect(recipe.ingredients.first.rawText, "salt");
    expect(recipe.steps.first.timers.first.durationSeconds, 60);
    expect(recipe.steps.first.timers.first.alertSoundKey, "ding");
    expect(recipe.sourceName, "Grandma");
    expect(recipe.totalMinutes, 30);
    expect(recipe.coverMediaId, "media-cover-1");
    expect(recipe.steps.first.mediaId, "media-step-1");
  });
}

