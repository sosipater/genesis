import "dart:async";

import "package:flutter/foundation.dart";

import "../../data/models/recipe_models.dart";

class ActiveTimerState {
  final String timerId;
  final String recipeId;
  final String stepId;
  final String label;
  final int durationSeconds;
  final int remainingSeconds;
  final bool isRunning;

  const ActiveTimerState({
    required this.timerId,
    required this.recipeId,
    required this.stepId,
    required this.label,
    required this.durationSeconds,
    required this.remainingSeconds,
    required this.isRunning,
  });

  ActiveTimerState copyWith({
    int? remainingSeconds,
    bool? isRunning,
  }) {
    return ActiveTimerState(
      timerId: timerId,
      recipeId: recipeId,
      stepId: stepId,
      label: label,
      durationSeconds: durationSeconds,
      remainingSeconds: remainingSeconds ?? this.remainingSeconds,
      isRunning: isRunning ?? this.isRunning,
    );
  }
}

class TimerRuntimeController extends ChangeNotifier {
  Timer? _ticker;
  final Map<String, ActiveTimerState> _timersById = <String, ActiveTimerState>{};
  void Function(ActiveTimerState state)? onTimerCompleted;

  List<ActiveTimerState> get activeTimers => _timersById.values.toList()
    ..sort((ActiveTimerState a, ActiveTimerState b) => a.label.compareTo(b.label));

  ActiveTimerState? getTimer(String timerId) => _timersById[timerId];

  void startTimer(StepTimer timer, {required String recipeId}) {
    _timersById[timer.id] = ActiveTimerState(
      timerId: timer.id,
      recipeId: recipeId,
      stepId: timer.stepId,
      label: timer.label,
      durationSeconds: timer.durationSeconds,
      remainingSeconds: timer.durationSeconds,
      isRunning: true,
    );
    _ensureTicker();
    notifyListeners();
  }

  void pauseTimer(String timerId) {
    final ActiveTimerState? timer = _timersById[timerId];
    if (timer == null) {
      return;
    }
    _timersById[timerId] = timer.copyWith(isRunning: false);
    notifyListeners();
  }

  void resumeTimer(String timerId) {
    final ActiveTimerState? timer = _timersById[timerId];
    if (timer == null || timer.remainingSeconds <= 0) {
      return;
    }
    _timersById[timerId] = timer.copyWith(isRunning: true);
    _ensureTicker();
    notifyListeners();
  }

  void cancelTimer(String timerId) {
    _timersById.remove(timerId);
    _cleanupTickerIfIdle();
    notifyListeners();
  }

  void _ensureTicker() {
    _ticker ??= Timer.periodic(const Duration(seconds: 1), (_) {
      bool changed = false;
      final List<String> toRemove = <String>[];
      for (final MapEntry<String, ActiveTimerState> entry in _timersById.entries) {
        final ActiveTimerState state = entry.value;
        if (!state.isRunning) {
          continue;
        }
        final int nextRemaining = state.remainingSeconds - 1;
        if (nextRemaining <= 0) {
          toRemove.add(entry.key);
          changed = true;
          continue;
        }
        _timersById[entry.key] = state.copyWith(remainingSeconds: nextRemaining, isRunning: true);
        changed = true;
      }
      for (final String id in toRemove) {
        final ActiveTimerState? completed = _timersById.remove(id);
        if (completed != null) {
          onTimerCompleted?.call(completed);
        }
      }
      if (changed) {
        notifyListeners();
      }
      _cleanupTickerIfIdle();
    });
  }

  void _cleanupTickerIfIdle() {
    final bool hasRunning = _timersById.values.any((ActiveTimerState state) => state.isRunning);
    if (!hasRunning) {
      _ticker?.cancel();
      _ticker = null;
    }
  }

  @override
  void dispose() {
    _ticker?.cancel();
    _ticker = null;
    super.dispose();
  }
}

