from pathlib import Path

import pytest

from tests.fixtures import build


@pytest.fixture
def rate_sheet(tmp_path: Path) -> Path:
    return build.build_rate_sheet(tmp_path / "Costing_2026.xlsx")


@pytest.fixture
def wide_rate_sheet(tmp_path: Path) -> Path:
    return build.build_wide_rate_sheet(tmp_path / "Costing_Wide.xlsx")


@pytest.fixture
def stacked_rate_sheet(tmp_path: Path) -> Path:
    return build.build_stacked_rate_sheet(tmp_path / "Costing_Stacked.xlsx")


@pytest.fixture
def nasty_sheet(tmp_path: Path) -> Path:
    return build.build_nasty_sheet(tmp_path / "Nasty.xlsx")


@pytest.fixture
def multiheader_sheet(tmp_path: Path) -> Path:
    return build.build_multiheader_sheet(tmp_path / "Costing_Multiheader.xlsx")


@pytest.fixture
def itinerary(tmp_path: Path) -> Path:
    return build.build_itinerary(tmp_path / "Trip_Smith.xlsx")


@pytest.fixture
def day_grouped_itinerary(tmp_path: Path) -> Path:
    return build.build_day_grouped_itinerary(tmp_path / "Trip_Jones.xlsx")


@pytest.fixture
def minimal_itinerary(tmp_path: Path) -> Path:
    return build.build_minimal_itinerary(tmp_path / "Trip_Minimal.xlsx")


@pytest.fixture
def wide_itinerary(tmp_path: Path) -> Path:
    return build.build_wide_itinerary(tmp_path / "Trip_Brown.xlsx")


@pytest.fixture
def formula_sheet(tmp_path: Path) -> Path:
    return build.build_formula_sheet(tmp_path / "Formula.xlsx")


@pytest.fixture
def branded_itinerary(tmp_path: Path) -> Path:
    return build.build_branded_itinerary(tmp_path / "Trip_Branded.xlsx")
