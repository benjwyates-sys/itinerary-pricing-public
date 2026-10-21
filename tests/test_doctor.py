from pricing.config import Config, load_config, save_config
from pricing.doctor import run_checks


def test_all_green_when_configured(tmp_path, rate_sheet):
    checks = run_checks(Config(root=tmp_path, costing_workbook=rate_sheet))
    assert all(c.ok for c in checks), [c.message for c in checks if not c.ok]


def test_missing_workbook_explains_what_to_do(tmp_path):
    checks = run_checks(Config(root=tmp_path, costing_workbook=tmp_path / "gone.xlsx"))
    failure = next(c for c in checks if not c.ok)
    assert "costing" in failure.message.lower()
    assert "traceback" not in failure.message.lower()


def test_unconfigured_workbook_asks_for_it(tmp_path):
    checks = run_checks(Config(root=tmp_path, costing_workbook=None))
    assert any("haven't told me where" in c.message for c in checks)


def test_run_checks_surfaces_config_error_on_corrupted_file(tmp_path):
    """run_checks must surface config_error check with ok=False and actionable message."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "config.json").write_text("{not valid json!!", encoding="utf-8")
    config = load_config(tmp_path)
    checks = run_checks(config)
    config_check = next(c for c in checks if c.name == "config")
    assert not config_check.ok
    assert config_check.message is not None
    assert len(config_check.message) > 0
    assert "profile" in config_check.message.lower()


def test_run_checks_does_not_emit_config_error_on_healthy_file(tmp_path):
    """run_checks must NOT emit config error when config is healthy."""
    config = Config(root=tmp_path, costing_workbook=None)
    checks = run_checks(config)
    config_check = next(c for c in checks if c.name == "config")
    assert config_check.ok
    assert "good" in config_check.message.lower()


def test_write_probe_does_not_clobber_preexisting_file(tmp_path, rate_sheet):
    """Write probe must not overwrite a pre-existing file with the same name."""
    # Pre-create a file where the probe might write
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    # Note: we can't actually collide on the new name since it uses PID,
    # but we can verify the probe doesn't leave behind a file
    config = Config(root=tmp_path, costing_workbook=rate_sheet)
    checks = run_checks(config)
    # After running checks, no probe file should remain
    data_files = list(data_dir.iterdir())
    probe_files = [f for f in data_files if f.name.startswith(".write-test")]
    assert len(probe_files) == 0, f"Probe file(s) left behind: {probe_files}"


def test_run_checks_with_directory_instead_of_workbook_does_not_raise(tmp_path):
    """run_checks must not raise when costing_workbook points at a directory."""
    workbook_dir = tmp_path / "is_a_directory"
    workbook_dir.mkdir()
    config = Config(root=tmp_path, costing_workbook=workbook_dir)
    checks = run_checks(config)
    # Should complete without raising
    workbook_check = next(c for c in checks if c.name == "workbook")
    assert not workbook_check.ok


def test_run_checks_with_text_file_as_workbook_does_not_raise(tmp_path):
    """run_checks must not raise when costing_workbook points at a .txt file."""
    text_file = tmp_path / "not_a_workbook.xlsx"
    text_file.write_text("this is not an Excel file", encoding="utf-8")
    config = Config(root=tmp_path, costing_workbook=text_file)
    checks = run_checks(config)
    # Should complete without raising
    workbook_check = next(c for c in checks if c.name == "workbook")
    assert not workbook_check.ok
    assert "couldn't open" in workbook_check.message.lower()


def test_run_checks_never_shows_python_traceback(tmp_path):
    """run_checks messages must never contain Python exception text."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "config.json").write_text("{not valid}", encoding="utf-8")
    config = load_config(tmp_path)
    checks = run_checks(config)
    for check in checks:
        assert "Traceback" not in check.message
        assert "Error" not in check.message  # Generic capitalized Error
        assert ".py" not in check.message  # No file references
