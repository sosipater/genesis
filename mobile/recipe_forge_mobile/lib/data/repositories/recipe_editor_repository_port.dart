import "../models/recipe_models.dart";

abstract class RecipeEditorRepositoryPort {
  Future<RecipeDetail?> getRecipeById(String recipeId);
  Future<void> upsertRecipeGraph(RecipeDetail recipe, {required String updatedAt});
}
