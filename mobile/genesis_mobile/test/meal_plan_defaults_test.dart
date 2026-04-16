import "package:flutter_test/flutter_test.dart";
import "package:genesis_mobile/features/meal_plan/meal_plan_defaults.dart";

void main() {
  test("default slot is dinner and appears first in picker order", () {
    expect(kDefaultMealSlot, "dinner");
    expect(kMealSlotsOrderedForPicker.first, "dinner");
    expect(kMealSlotsOrderedForPicker, contains("custom"));
  });

  test("mealSlotPickerLabel title-cases standard slots", () {
    expect(mealSlotPickerLabel("dinner"), "Dinner");
    expect(mealSlotPickerLabel("custom"), "Custom");
  });
}
