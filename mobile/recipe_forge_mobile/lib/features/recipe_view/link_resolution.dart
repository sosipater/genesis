import "../../data/models/recipe_models.dart";

class ResolvedStepSegment {
  final String text;
  final bool isLink;
  final StepLink? link;

  const ResolvedStepSegment({
    required this.text,
    required this.isLink,
    this.link,
  });
}

class LinkResolutionResult {
  final List<ResolvedStepSegment> segments;

  const LinkResolutionResult(this.segments);
}

LinkResolutionResult resolveStepTextSegments(RecipeDetail recipe, RecipeStep step) {
  final RegExp tokenRegExp = RegExp(r"\[\[(ingredient|equipment):([^\]]+)\]\]");
  final Iterable<Match> matches = tokenRegExp.allMatches(step.bodyText);
  int cursor = 0;
  final List<ResolvedStepSegment> segments = <ResolvedStepSegment>[];
  for (final Match match in matches) {
    if (match.start > cursor) {
      segments.add(
        ResolvedStepSegment(
          text: step.bodyText.substring(cursor, match.start),
          isLink: false,
        ),
      );
    }
    final String targetType = match.group(1)!;
    final String tokenKey = match.group(2)!;
    StepLink? link;
    for (final StepLink candidate in recipe.stepLinks) {
      if (candidate.stepId == step.id &&
          candidate.targetType == targetType &&
          candidate.tokenKey == tokenKey) {
        link = candidate;
        break;
      }
    }

    final String fallback = link?.labelOverride ?? link?.labelSnapshot ?? tokenKey;
    segments.add(
      ResolvedStepSegment(
        text: fallback,
        isLink: true,
        link: link,
      ),
    );
    cursor = match.end;
  }
  if (cursor < step.bodyText.length) {
    segments.add(
      ResolvedStepSegment(
        text: step.bodyText.substring(cursor),
        isLink: false,
      ),
    );
  }
  if (segments.isEmpty) {
    segments.add(ResolvedStepSegment(text: step.bodyText, isLink: false));
  }
  return LinkResolutionResult(segments);
}

RecipeIngredientItem? findIngredientById(RecipeDetail recipe, String id) {
  for (final RecipeIngredientItem ingredient in recipe.ingredients) {
    if (ingredient.id == id) {
      return ingredient;
    }
  }
  return null;
}

RecipeEquipmentItem? findEquipmentById(RecipeDetail recipe, String id) {
  for (final RecipeEquipmentItem equipment in recipe.equipment) {
    if (equipment.id == id) {
      return equipment;
    }
  }
  return null;
}

