import "package:flutter_test/flutter_test.dart";
import "package:recipe_forge_mobile/data/models/recipe_models.dart";
import "package:recipe_forge_mobile/features/recipe_view/timer_runtime_controller.dart";

void main() {
  test("timer start pause resume cancel lifecycle", () async {
    final controller = TimerRuntimeController();
    const StepTimer timer = StepTimer(
      id: "t1",
      stepId: "s1",
      label: "Boil",
      durationSeconds: 3,
      autoStart: false,
    );

    controller.startTimer(timer, recipeId: "recipe-1");
    expect(controller.getTimer("t1"), isNotNull);
    await Future<void>.delayed(const Duration(milliseconds: 1100));
    final afterTick = controller.getTimer("t1");
    expect(afterTick, isNotNull);
    expect(afterTick!.remainingSeconds, lessThan(3));

    controller.pauseTimer("t1");
    final pausedRemaining = controller.getTimer("t1")!.remainingSeconds;
    await Future<void>.delayed(const Duration(milliseconds: 1100));
    expect(controller.getTimer("t1")!.remainingSeconds, pausedRemaining);

    controller.resumeTimer("t1");
    await Future<void>.delayed(const Duration(milliseconds: 1100));
    expect(controller.getTimer("t1")!.remainingSeconds, lessThan(pausedRemaining));

    controller.cancelTimer("t1");
    expect(controller.getTimer("t1"), isNull);
    controller.dispose();
  });

  test("invokes completion callback when timer ends", () async {
    final controller = TimerRuntimeController();
    const StepTimer timer = StepTimer(
      id: "t2",
      stepId: "s2",
      label: "Rest",
      durationSeconds: 1,
      autoStart: false,
    );
    ActiveTimerState? completed;
    controller.onTimerCompleted = (ActiveTimerState state) {
      completed = state;
    };
    controller.startTimer(timer, recipeId: "recipe-2");
    await Future<void>.delayed(const Duration(milliseconds: 1200));
    expect(completed, isNotNull);
    expect(completed!.timerId, "t2");
    expect(completed!.recipeId, "recipe-2");
    expect(controller.getTimer("t2"), isNull);
    controller.dispose();
  });
}

