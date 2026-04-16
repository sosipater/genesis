import "../models/recipe_models.dart";

abstract class RecipeEditorRepositoryPort {
  Future<RecipeDetail?> getRecipeById(String recipeId);
  Future<void> upsertRecipeGraph(RecipeDetail recipe, {required String updatedAt});
  Future<List<GlobalEquipmentSummary>> listGlobalEquipmentForPicker();
  Future<String> createGlobalEquipmentRecord({required String name, String? notes});
  Future<List<CatalogIngredientSummary>> listCatalogIngredientsForPicker();
  Future<List<CatalogIngredientSummary>> searchCatalogIngredients(String query, {int limit = 20});
  Future<String> createCatalogIngredientRecord({required String name, String? notes});
  Future<List<RecipeSummary>> listLocalRecipesForSubRecipePicker({required String excludeRecipeId});
}
