import "../models/recipe_models.dart";

abstract class RecipeReadRepositoryPort {
  Future<RecipeDetail?> getRecipeById(String recipeId);
  Future<void> markRecipeOpened(String recipeId, String openedAtUtc);
}

