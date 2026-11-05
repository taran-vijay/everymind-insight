from pathlib import Path

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--survey-workbook",
        type=Path,
        help="Local path to the private reference workbook for verification.",
    )


@pytest.fixture
def survey_workbook(request: pytest.FixtureRequest) -> Path:
    path = request.config.getoption("--survey-workbook")
    if path is None:
        pytest.skip("Reference workbook checks require --survey-workbook.")
    if not path.is_file():
        pytest.fail("The reference workbook supplied to --survey-workbook was not found.")
    return path
