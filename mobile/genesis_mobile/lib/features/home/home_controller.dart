import "package:flutter/foundation.dart";

import "../../data/repositories/recipe_repository.dart";
import "home_service.dart";

class HomeController extends ChangeNotifier {
  final RecipeRepository _repository;
  final HomeService _service;

  bool loading = false;
  String? error;
  HomeSnapshot? snapshot;

  HomeController(this._repository, this._service);

  Future<void> load() async {
    loading = true;
    error = null;
    notifyListeners();
    try {
      snapshot = await _service.loadSnapshot();
    } catch (e) {
      error = e.toString();
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<void> markCookedFromHome(String recipeId) async {
    await _repository.markRecipeCooked(recipeId, DateTime.now().toUtc().toIso8601String());
    await load();
  }
}
