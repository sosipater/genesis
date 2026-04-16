"""Map timer alert UI choices to persisted alert_sound_key values."""

from __future__ import annotations

# (label shown in UI, internal key or None for default)
SOUND_PRESET_CHOICES: list[tuple[str, str | None]] = [
    ("Default", None),
    ("Soft chime", "chime_soft"),
    ("Kitchen timer", "timer_kitchen"),
    ("Alarm", "alarm"),
    ("Silent (no sound)", "silent"),
]


def label_for_sound_key(key: str | None) -> str:
    if key is None or key == "":
        return "Default"
    for label, k in SOUND_PRESET_CHOICES:
        if k == key:
            return label
    return "Default"


def sound_key_for_label(label: str) -> str | None:
    for lbl, k in SOUND_PRESET_CHOICES:
        if lbl == label:
            return k
    return None
