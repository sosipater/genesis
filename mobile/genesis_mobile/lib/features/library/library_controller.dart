import "package:flutter/foundation.dart";

import "../../data/models/recipe_models.dart";
import "../../data/repositories/recipe_repository.dart";

class LibraryController extends ChangeNotifier {
  final RecipeRepository _repository;
  final Map<String, String?> _coverPathCache = <String, String?>{};

  LibraryController(this._repository);

  List<RecipeSummary> recipes = <RecipeSummary>[];
  List<CollectionSummary> collections = <CollectionSummary>[];
  List<String> availableTags = <String>[];
  List<String> selectedTagFilters = <String>[];
  bool ingredientFocus = false;
  bool loading = false;
  String? error;
  String query = "";
  String scope = "all";
  String mode = "library"; // library | working_set | collection | favorites | recent_opened | recent_cooked
  String? selectedCollectionId;

  bool _recipeHasAllSelectedTags(RecipeSummary recipe) {
    if (selectedTagFilters.isEmpty) {
      return true;
    }
    final Set<String> have = recipe.tags.map((String t) => t.trim().toLowerCase()).toSet();
    for (final String raw in selectedTagFilters) {
      final String t = raw.trim().toLowerCase();
      if (t.isEmpty) {
        continue;
      }
      if (!have.contains(t)) {
        return false;
      }
    }
    return true;
  }

  List<RecipeSummary> _applyTagSubset(List<RecipeSummary> input) {
    if (selectedTagFilters.isEmpty) {
      return input;
    }
    return input.where(_recipeHasAllSelectedTags).toList();
  }

  Future<void> load() async {
    loading = true;
    error = null;
    notifyListeners();
    try {
      collections = await _repository.listCollections();
      availableTags = await _repository.listTagNamesForFilter();
      if (mode == "working_set") {
        recipes = _applyTagSubset(await _repository.listWorkingSetRecipes());
      } else if (mode == "favorites") {
        recipes = await _repository.searchRecipes(
          query: query,
          scope: "favorites",
          tagsMatchAll: selectedTagFilters,
          ingredientFocus: ingredientFocus,
        );
      } else if (mode == "recent_opened") {
        recipes = _applyTagSubset(await _repository.listRecentOpenedRecipes());
      } else if (mode == "recent_cooked") {
        final List<RecipeSummary> all = await _repository.searchRecipes(
          query: "",
          scope: "all",
          tagsMatchAll: selectedTagFilters,
          ingredientFocus: false,
        );
        all.sort((RecipeSummary a, RecipeSummary b) {
          final String av = a.lastCookedAt ?? "";
          final String bv = b.lastCookedAt ?? "";
          return bv.compareTo(av);
        });
        recipes = all.where((RecipeSummary item) => item.lastCookedAt != null).toList();
      } else if (mode == "collection" && selectedCollectionId != null) {
        recipes = _applyTagSubset(await _repository.listCollectionRecipes(selectedCollectionId!));
      } else {
        recipes = await _repository.searchRecipes(
          query: query,
          scope: scope,
          tagsMatchAll: selectedTagFilters,
          ingredientFocus: ingredientFocus,
        );
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

  Future<void> toggleTagFilter(String tag) async {
    final String t = tag.trim();
    if (t.isEmpty) {
      return;
    }
    String canonical = t;
    for (final String a in availableTags) {
      if (a.toLowerCase() == t.toLowerCase()) {
        canonical = a;
        break;
      }
    }
    final List<String> next = List<String>.from(selectedTagFilters);
    final int idx = next.indexWhere((String x) => x.toLowerCase() == canonical.toLowerCase());
    if (idx >= 0) {
      next.removeAt(idx);
    } else {
      next.add(canonical);
    }
    selectedTagFilters = next;
    notifyListeners();
    await load();
  }

  Future<void> setIngredientFocus(bool value) async {
    ingredientFocus = value;
    mode = "library";
    notifyListeners();
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

