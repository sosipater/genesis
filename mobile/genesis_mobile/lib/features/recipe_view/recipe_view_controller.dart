import "package:flutter/foundation.dart";

import "../../data/models/recipe_models.dart";
import "../../data/repositories/recipe_repository.dart";
import "../../data/repositories/repository_ports.dart";

class RecipeViewController extends ChangeNotifier {
  final RecipeReadRepositoryPort _repository;
  bool isFavorite = false;
  String? coverImagePath;
  final Map<String, String> stepImagePaths = <String, String>{};

  RecipeViewController(this._repository);

  RecipeDetail? recipe;
  bool loading = false;
  String? error;

  Future<void> loadRecipe(String recipeId) async {
    loading = true;
    error = null;
    notifyListeners();
    try {
      recipe = await _repository.getRecipeById(recipeId);
      await _repository.markRecipeOpened(
        recipeId,
        DateTime.now().toUtc().toIso8601String(),
      );
      if (recipe == null) {
        error = "Recipe not found";
      } else {
        coverImagePath = null;
        stepImagePaths.clear();
        if (_repository is RecipeRepository) {
          final RecipeRepository repository = _repository;
          final List<RecipeSummary> state = await repository.searchRecipes(query: "", scope: "all");
          RecipeSummary? summary;
          for (final RecipeSummary item in state) {
            if (item.id == recipeId) {
              summary = item;
              break;
            }
          }
          isFavorite = summary?.isFavorite ?? false;
          final String? coverId = recipe!.coverMediaId;
          if (coverId != null) {
            coverImagePath = await repository.resolveMediaFilePath(coverId);
          }
          for (final RecipeStep step in recipe!.steps) {
            if (step.mediaId == null) {
              continue;
            }
            final String? path = await repository.resolveMediaFilePath(step.mediaId!);
            if (path != null) {
              stepImagePaths[step.id] = path;
            }
          }
        }
      }
    } catch (e) {
      error = e.toString();
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<void> toggleFavorite() async {
    if (recipe == null) {
      return;
    }
    isFavorite = !isFavorite;
    if (_repository is RecipeRepository) {
      final RecipeRepository repository = _repository;
      await repository.setFavorite(recipe!.id, isFavorite, DateTime.now().toUtc().toIso8601String());
    }
    notifyListeners();
  }

  Future<void> markCooked() async {
    if (recipe == null) {
      return;
    }
    if (_repository is RecipeRepository) {
      final RecipeRepository repository = _repository;
      await repository.markRecipeCooked(recipe!.id, DateTime.now().toUtc().toIso8601String());
    }
    notifyListeners();
  }
}

