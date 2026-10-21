from pricing.config import Config, load_config, save_config


def test_paths_derive_from_root(tmp_path):
    config = Config(root=tmp_path, costing_workbook=None)
    assert config.data_dir == tmp_path / "data"
    assert config.catalog_path == tmp_path / "data" / "catalog.json"
    assert config.aliases_path == tmp_path / "data" / "aliases.json"
    assert config.profiles_dir == tmp_path / "data" / "profiles"
    assert config.runs_dir == tmp_path / "data" / "runs"


def test_config_roundtrips(tmp_path, rate_sheet):
    save_config(Config(root=tmp_path, costing_workbook=rate_sheet))
    assert load_config(tmp_path).costing_workbook == rate_sheet


def test_missing_config_is_not_an_error(tmp_path):
    assert load_config(tmp_path).costing_workbook is None


def test_load_config_with_corrupted_json_does_not_raise(tmp_path):
    """load_config must survive invalid JSON and not raise."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "config.json").write_text("{not valid json!!", encoding="utf-8")
    config = load_config(tmp_path)
    assert config.costing_workbook is None
    assert config.config_error is not None
    assert "couldn't be read" in config.config_error.lower()


def test_load_config_with_json_list_does_not_raise(tmp_path):
    """load_config must survive JSON that is a list (not a dict) and not raise."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "config.json").write_text("[1,2,3]", encoding="utf-8")
    config = load_config(tmp_path)
    assert config.costing_workbook is None
    assert config.config_error is not None


def test_load_config_with_json_string_does_not_raise(tmp_path):
    """load_config must survive JSON that is a string (not a dict) and not raise."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "config.json").write_text('"just a string"', encoding="utf-8")
    config = load_config(tmp_path)
    assert config.costing_workbook is None
    assert config.config_error is not None


def test_config_error_field_defaults_to_none():
    """Config.config_error should default to None for normal configs."""
    config = Config(root="/tmp", costing_workbook=None)
    assert config.config_error is None


def test_load_config_roundtrip_with_none_workbook(tmp_path):
    """save_config/load_config round-trip with costing_workbook=None."""
    config1 = Config(root=tmp_path, costing_workbook=None)
    save_config(config1)
    config2 = load_config(tmp_path)
    assert config2.costing_workbook is None
    assert config2.config_error is None
