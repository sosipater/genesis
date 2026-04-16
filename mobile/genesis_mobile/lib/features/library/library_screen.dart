import "dart:async";
import "dart:io";

import "package:flutter/material.dart";

import "../../data/models/recipe_models.dart";
import "library_controller.dart";

class LibraryScreen extends StatefulWidget {
  final LibraryController controller;
  final void Function(String recipeId) onOpenRecipe;
  final VoidCallback onCreateRecipe;
  final void Function(String recipeId) onEditRecipe;
  final VoidCallback? onOpenSync;

  const LibraryScreen({
    super.key,
    required this.controller,
    required this.onOpenRecipe,
    required this.onCreateRecipe,
    required this.onEditRecipe,
    this.onOpenSync,
  });

  @override
  State<LibraryScreen> createState() => _LibraryScreenState();
}

class _LibraryScreenState extends State<LibraryScreen> {
  final TextEditingController _searchController = TextEditingController();
  Timer? _searchDebounce;

  @override
  void initState() {
    super.initState();
    widget.controller.addListener(_onChanged);
    widget.controller.load();
  }

  @override
  void dispose() {
    _searchDebounce?.cancel();
    widget.controller.removeListener(_onChanged);
    _searchController.dispose();
    super.dispose();
  }

  void _scheduleSearch(String value) {
    _searchDebounce?.cancel();
    _searchDebounce = Timer(const Duration(milliseconds: 380), () {
      widget.controller.setSearchQuery(value);
    });
  }

  String _listSubtitle(RecipeSummary recipe) {
    final String base = (recipe.subtitle != null && recipe.subtitle!.trim().isNotEmpty)
        ? recipe.subtitle!
        : recipe.status;
    if (recipe.searchMatchHint != null && recipe.searchMatchHint!.trim().isNotEmpty) {
      return "$base · ${recipe.searchMatchHint}";
    }
    return base;
  }

  void _onChanged() {
    if (mounted) {
      setState(() {});
    }
  }

  @override
  Widget build(BuildContext context) {
    if (widget.controller.loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (widget.controller.error != null) {
      return Center(child: Text("Error: ${widget.controller.error}"));
    }
    return Column(
      children: <Widget>[
        Padding(
          padding: const EdgeInsets.all(8),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              TextField(
                controller: _searchController,
                decoration: const InputDecoration(
                  labelText: "Search recipes",
                  hintText: "Title, ingredients, tags, steps…",
                  border: OutlineInputBorder(),
                ),
                onChanged: _scheduleSearch,
                onSubmitted: widget.controller.setSearchQuery,
              ),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text("Ingredient-focused"),
                subtitle: const Text("Query must match an ingredient or catalog name", style: TextStyle(fontSize: 12)),
                value: widget.controller.ingredientFocus,
                onChanged: (bool v) => widget.controller.setIngredientFocus(v),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: <Widget>[
                  DropdownButton<String>(
                    value: widget.controller.scope,
                    items: const <DropdownMenuItem<String>>[
                      DropdownMenuItem<String>(value: "all", child: Text("All")),
                      DropdownMenuItem<String>(value: "local", child: Text("Local")),
                      DropdownMenuItem<String>(value: "bundled", child: Text("Bundled")),
                      DropdownMenuItem<String>(value: "favorites", child: Text("Favorites")),
                    ],
                    onChanged: (String? value) {
                      if (value != null) {
                        widget.controller.setScope(value);
                      }
                    },
                  ),
                  FilledButton.icon(
                    onPressed: widget.onCreateRecipe,
                    icon: const Icon(Icons.add),
                    label: const Text("New"),
                  ),
                ],
              ),
              if (widget.controller.availableTags.isNotEmpty) ...<Widget>[
                const SizedBox(height: 4),
                Align(
                  alignment: Alignment.centerLeft,
                  child: Text("Tags (all selected)", style: Theme.of(context).textTheme.labelMedium),
                ),
                const SizedBox(height: 4),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: widget.controller.availableTags.map((String name) {
                    final bool on = widget.controller.selectedTagFilters.any(
                      (String x) => x.toLowerCase() == name.toLowerCase(),
                    );
                    return FilterChip(
                      label: Text(name),
                      selected: on,
                      onSelected: (_) => widget.controller.toggleTagFilter(name),
                    );
                  }).toList(),
                ),
              ],
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8),
          child: Wrap(
            spacing: 8,
            runSpacing: 8,
            children: <Widget>[
              FilledButton.tonal(
                onPressed: widget.controller.showLibrary,
                child: const Text("Library"),
              ),
              FilledButton.tonal(
                onPressed: widget.controller.showWorkingSet,
                child: const Text("Working Set"),
              ),
              FilledButton.tonal(
                onPressed: widget.controller.showFavorites,
                child: const Text("Favorites"),
              ),
              FilledButton.tonal(
                onPressed: widget.controller.showRecentOpened,
                child: const Text("Recent Opened"),
              ),
              FilledButton.tonal(
                onPressed: widget.controller.showRecentCooked,
                child: const Text("Recent Cooked"),
              ),
            ],
          ),
        ),
        if (widget.controller.collections.isNotEmpty)
          SizedBox(
            height: 56,
            child: ListView(
              scrollDirection: Axis.horizontal,
              children: widget.controller.collections
                  .map(
                    (CollectionSummary collection) => Padding(
                      padding: const EdgeInsets.all(6),
                      child: ActionChip(
                        label: Text("${collection.name} (${collection.recipeCount})"),
                        onPressed: () => widget.controller.showCollection(collection.id),
                      ),
                    ),
                  )
                  .toList(),
            ),
          ),
        Expanded(
          child: widget.controller.recipes.isEmpty
              ? Center(
                  child: Card(
                    margin: const EdgeInsets.all(24),
                    child: Padding(
                      padding: const EdgeInsets.all(20),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: <Widget>[
                          Text("No recipes here yet", style: Theme.of(context).textTheme.titleMedium),
                          const SizedBox(height: 8),
                          const Text("Create one on this device or pull recipes from your computer."),
                          const SizedBox(height: 16),
                          FilledButton(onPressed: widget.onCreateRecipe, child: const Text("Create recipe")),
                          if (widget.onOpenSync != null) ...<Widget>[
                            const SizedBox(height: 8),
                            OutlinedButton(onPressed: widget.onOpenSync, child: const Text("Sync from desktop")),
                          ],
                        ],
                      ),
                    ),
                  ),
                )
              : ListView.separated(
                  itemCount: widget.controller.recipes.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (BuildContext context, int index) {
                    final RecipeSummary recipe = widget.controller.recipes[index];
                    final bool bundled = recipe.scope == "bundled";
                    return ListTile(
                      leading: _buildCoverLeading(recipe),
                      title: Text(recipe.title),
                      subtitle: Text(_listSubtitle(recipe)),
                      trailing: Wrap(
                        spacing: 8,
                        children: <Widget>[
                          Chip(
                            label: Text(bundled ? "BUNDLED" : "LOCAL"),
                            backgroundColor: bundled ? Colors.blueGrey.shade800 : Colors.green.shade800,
                          ),
                          if (recipe.isFavorite) const Chip(label: Text("FAV")),
                          IconButton(
                            icon: const Icon(Icons.playlist_add),
                            tooltip: "Add to working set",
                            onPressed: () => widget.controller.addToWorkingSet(recipe.id),
                          ),
                          IconButton(
                            icon: const Icon(Icons.playlist_remove),
                            tooltip: "Remove from working set",
                            onPressed: () => widget.controller.removeFromWorkingSet(recipe.id),
                          ),
                        ],
                      ),
                      onTap: () => widget.onOpenRecipe(recipe.id),
                      onLongPress: () => widget.onEditRecipe(recipe.id),
                    );
                  },
                ),
        ),
      ],
    );
  }

  Widget? _buildCoverLeading(RecipeSummary recipe) {
    if (recipe.coverMediaId == null) {
      return null;
    }
    return FutureBuilder<String?>(
      future: widget.controller.resolveCoverPath(recipe.id, recipe.coverMediaId!),
      builder: (BuildContext context, AsyncSnapshot<String?> snapshot) {
        if (snapshot.hasData && snapshot.data != null) {
          return ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: Image.file(
              File(snapshot.data!),
              width: 44,
              height: 44,
              fit: BoxFit.cover,
            ),
          );
        }
        return const Icon(Icons.image);
      },
    );
  }
}

