from desktop.app.viewmodels.editor_state import EditorState


def test_editor_state_dirty_and_save_flags() -> None:
    state = EditorState()
    assert state.can_save is False

    state.open_recipe("r1", "local", is_read_only=False)
    assert state.can_save is False
    state.mark_dirty()
    assert state.can_save is True
    state.mark_clean()
    assert state.can_save is False

    state.open_recipe("r2", "bundled", is_read_only=True)
    state.mark_dirty()
    assert state.is_dirty is False
    assert state.can_save is False

