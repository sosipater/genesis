import "package:flutter/foundation.dart";

import "../../data/models/recipe_models.dart";
import "../../data/repositories/recipe_repository.dart";

class LibraryController extends ChangeNotifier {
  final RecipeRepository _repository;
  final Map<String, String?> _coverPathCache = <String, String?>{};

  LibraryController(this._repository);

  List<RecipeSummary> recipes = <RecipeSummary>[];
  List<CollectionSummary> collections = <CollectionSummary>[];
  bool loading = false;
  String? error;
  String query = "";
  String scope = "all";
  String mode = "library"; // library | working_set | collection | favorites | recent_opened | recent_cooked
  String? selectedCollectionId;

  Future<void> load() async {
    loading = true;
    error = null;
    notifyListeners();
    try {
      collections = await _repository.listCollections();
      if (mode == "working_set") {
        recipes = await _repository.listWorkingSetRecipes();
      } else if (mode == "favorites") {
        recipes = await _repository.searchRecipes(query: query, scope: "favorites");
      } else if (mode == "recent_opened") {
        recipes = await _repository.listRecentOpenedRecipes();
      } else if (mode == "recent_cooked") {
        final List<RecipeSummary> all = await _repository.searchRecipes(query: "", scope: "all");
        all.sort((RecipeSummary a, RecipeSummary b) {
          final String av = a.lastCookedAt ?? "";
          final String bv = b.lastCookedAt ?? "";
          return bv.compareTo(av);
        });
        recipes = all.where((RecipeSummary item) => item.lastCookedAt != null).toList();
      } else if (mode == "collection" && selectedCollectionId != null) {
        recipes = await _repository.listCollectionRecipes(selectedCollectionId!);
      } else {
        recipes = await _repository.searchRecipes(query: query, scope: scope);
      }
    } catch (e) {
      error = e.toString();
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<void> setSearchQuery(String value) async {
    query = value;
    mode = "library";
    await load();
  }

  Future<void> setScope(String value) async {
    scope = value;
    mode = "library";
    await load();
  }

  Future<void> showWorkingSet() async {
    mode = "working_set";
    await load();
  }

  Future<void> showLibrary() async {
    mode = "library";
    await load();
  }

  Future<void> showFavorites() async {
    mode = "favorites";
    await load();
  }

  Future<void> showRecentOpened() async {
    mode = "recent_opened";
    await load();
  }

  Future<void> showRecentCooked() async {
    mode = "recent_cooked";
    await load();
  }

  Future<void> showCollection(String collectionId) async {
    selectedCollectionId = collectionId;
    mode = "collection";
    await load();
  }

  Future<void> addToWorkingSet(String recipeId) async {
    await _repository.addToWorkingSet(recipeId, DateTime.now().toUtc().toIso8601String());
    await load();
  }

  Future<void> removeFromWorkingSet(String recipeId) async {
    await _repository.removeFromWorkingSet(recipeId, DateTime.now().toUtc().toIso8601String());
    await load();
  }

  Future<String?> resolveCoverPath(String recipeId, String mediaId) async {
    final String cacheKey = "$recipeId::$mediaId";
    if (_coverPathCache.containsKey(cacheKey)) {
      return _coverPathCache[cacheKey];
    }
    final String? path = await _repository.resolveMediaFilePath(mediaId);
    _coverPathCache[cacheKey] = path;
    return path;
  }
}

