// Defaults and ordering for low-friction meal planning UX.

const String kDefaultMealSlot = "dinner";

/// Dinner first — most common quick-schedule case.
const List<String> kMealSlotsOrderedForPicker = <String>[
  "dinner",
  "lunch",
  "breakfast",
  "snack",
  "custom",
];

String mealSlotPickerLabel(String slot) {
  if (slot == "custom") {
    return "Custom";
  }
  if (slot.isEmpty) {
    return slot;
  }
  return "${slot[0].toUpperCase()}${slot.substring(1)}";
}
