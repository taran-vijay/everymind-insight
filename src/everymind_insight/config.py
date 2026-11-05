"""Validated Phase 1 settings and bundled survey registry."""

from importlib.resources import files
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


PRESENTER_ITEMS = ("presenter_engaged", "presenter_knew_subject", "presenter_organized")
SCORE_ITEMS = ("recommend_score", "calling_score")
COMMENT_ITEMS = ("valuable_comment", "improve_comment")
OBJECTIVE_SKILLS = ("identify_crises", "describe_988", "know_when_to_use_988")
OBJECTIVE_ITEMS = {
    f"{skill}_{timing}": (skill, timing)
    for skill in OBJECTIVE_SKILLS
    for timing in ("before", "after")
}
REQUIRED_QUESTION_IDS = {
    "id", "start_time", "completion_time", "language", "roles", "training_date", "county",
    *PRESENTER_ITEMS, *SCORE_ITEMS, *COMMENT_ITEMS, *OBJECTIVE_ITEMS,
}


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QuestionSpec(Settings):
    header: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    fuzzy: bool = True
    objective_skill: str | None = None
    objective_timing: Literal["before", "after"] | None = None


class SurveyRegistry(Settings):
    sheet: str = "Survey Data"
    fuzzy_threshold: float = Field(default=86, ge=0, le=100)
    fuzzy_margin: float = Field(default=5, ge=0, le=100)
    questions: dict[str, QuestionSpec]

    @model_validator(mode="after")
    def validate_objective_pairs(self) -> "SurveyRegistry":
        missing = REQUIRED_QUESTION_IDS - self.questions.keys()
        if missing:
            raise ValueError(f"Missing canonical question IDs in the registry: {', '.join(sorted(missing))}")
        for question_id, question in self.questions.items():
            if (question.objective_skill, question.objective_timing) != OBJECTIVE_ITEMS.get(question_id, (None, None)):
                raise ValueError(f"Objective metadata does not match {question_id}")
        return self


RolePolicy = Literal["every", "multiple"]
LikertScore = Literal[1, 2, 3, 4, 5]


class NormalizationConfig(Settings):
    likert_aliases: dict[str, LikertScore]
    presenter_likert_aliases: dict[str, LikertScore]
    presenter_sensitivity_label: str = "Satisfied"
    county_aliases: dict[str, str]
    role_aliases: dict[str, str]
    language_aliases: dict[str, str]
    date_formats: list[str]
    timestamp_formats: list[str]
    role_policy: RolePolicy = "every"
    county_suggestion_threshold: float = Field(default=75, ge=0, le=100)

    @model_validator(mode="after")
    def validate_presenter_sensitivity(self) -> "NormalizationConfig":
        label = self.presenter_sensitivity_label.casefold()
        matches = [score for raw, score in self.presenter_likert_aliases.items() if raw.casefold() == label]
        if matches != [4]:
            raise ValueError("The presenter sensitivity label must map to 4 in presenter_likert_aliases")
        return self


class QualityConfig(Settings):
    speeder_seconds: int = Field(default=30, gt=0)
    min_duration_seconds: int = Field(default=1, ge=0)
    max_duration_seconds: int = Field(default=7200, gt=0)
    large_reversal_min_drop: int = Field(default=4, ge=1, le=4)

    @model_validator(mode="after")
    def validate_duration_thresholds(self) -> "QualityConfig":
        if not self.min_duration_seconds <= self.speeder_seconds <= self.max_duration_seconds:
            raise ValueError("Duration thresholds must be ordered minimum, speeder, maximum")
        return self


class Phase3Config(Settings):
    minimum_n: int = Field(default=10, ge=1)
    minimum_clusters: int = Field(default=8, ge=2)
    dominance_threshold: float = Field(default=0.8, gt=0.5, le=1)
    seed: int = Field(default=988, ge=0)
    bootstrap_resamples: int = Field(default=2000, ge=1)
    shuffles: int = Field(default=2000, ge=1)


class AppConfig(Settings):
    registry: SurveyRegistry
    normalization: NormalizationConfig
    quality: QualityConfig
    phase3: Phase3Config = Field(default_factory=Phase3Config)


def load_config(config_dir: Path | None = None) -> AppConfig:
    """Load the bundled YAML, using same-named files in an optional override directory."""
    defaults = files("everymind_insight").joinpath("defaults")
    documents = {
        "registry": "survey_registry.yaml",
        "normalization": "normalization.yaml",
        "quality": "quality.yaml",
        "phase3": "phase3.yaml",
    }
    values = {}
    for key, filename in documents.items():
        override = config_dir / filename if config_dir is not None else None
        source = override if override is not None and override.exists() else defaults.joinpath(filename)
        values[key] = yaml.safe_load(source.read_text(encoding="utf-8"))
    return AppConfig.model_validate(values)
