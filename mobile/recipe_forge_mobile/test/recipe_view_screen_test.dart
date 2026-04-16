import "package:flutter/material.dart";
import "package:flutter_test/flutter_test.dart";
import "package:recipe_forge_mobile/data/models/recipe_models.dart";
import "package:recipe_forge_mobile/data/repositories/repository_ports.dart";
import "package:recipe_forge_mobile/features/recipe_view/recipe_view_controller.dart";
import "package:recipe_forge_mobile/features/recipe_view/recipe_view_screen.dart";
import "package:recipe_forge_mobile/features/recipe_view/timer_runtime_controller.dart";

class _FakeRecipeRepository implements RecipeReadRepositoryPort {
  final RecipeDetail recipe;

  _FakeRecipeRepository(this.recipe);

  @override
  Future<RecipeDetail?> getRecipeById(String id) async => recipe;

  @override
  Future<void> markRecipeOpened(String recipeId, String openedAtUtc) async {}
}

void main() {
  testWidgets("recipe view shows section tabs", (WidgetTester tester) async {
    const RecipeDetail detail = RecipeDetail(
      id: "r1",
      title: "Test Recipe",
      scope: "local",
      status: "draft",
      equipment: <RecipeEquipmentItem>[
        RecipeEquipmentItem(id: "e1", recipeId: "r1", name: "Pot", isRequired: true, displayOrder: 0),
      ],
      ingredients: <RecipeIngredientItem>[
        RecipeIngredientItem(id: "i1", recipeId: "r1", rawText: "2 tsp salt", isOptional: false, displayOrder: 0),
      ],
      steps: <RecipeStep>[
        RecipeStep(
          id: "s1",
          recipeId: "r1",
          bodyText: "Do [[ingredient:salt]] thing",
          stepType: "instruction",
          displayOrder: 0,
          timers: <StepTimer>[
            StepTimer(id: "t1", stepId: "s1", label: "Wait", durationSeconds: 60, autoStart: false),
          ],
        ),
      ],
      stepLinks: <StepLink>[
        StepLink(
          id: "l1",
          stepId: "s1",
          targetType: "ingredient",
          targetId: "i1",
          tokenKey: "salt",
          labelSnapshot: "salt",
        ),
      ],
    );

    final controller = RecipeViewController(_FakeRecipeRepository(detail));
    final timerController = TimerRuntimeController();
    await tester.pumpWidget(
      MaterialApp(
        home: RecipeViewScreen(
          recipeId: "r1",
          controller: controller,
          timerRuntimeController: timerController,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text("Equipment"), findsOneWidget);
    expect(find.text("Ingredients"), findsOneWidget);
    expect(find.text("Steps"), findsOneWidget);
    expect(find.textContaining("Start Wait"), findsOneWidget);

    await tester.tap(find.text("salt"));
    await tester.pumpAndSettle();
    expect(find.text("2 tsp salt"), findsOneWidget);
    timerController.dispose();
  });
}

