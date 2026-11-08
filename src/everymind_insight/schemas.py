"""Typed metric ledger and versioned aggregate report contract."""

from math import isclose
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


NonnegativeInt = Annotated[int, Field(ge=0)]
HashDigest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
MetricUnit = Literal[
    "count", "proportion", "percentage_point", "ordinal_point", "ratio", "p_value", "statistic", "rank",
]


class SchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ConfidenceInterval(SchemaModel):
    lower: float
    upper: float
    level: float = Field(gt=0, lt=1)
    method: str

    @model_validator(mode="after")
    def validate_bounds(self) -> "ConfidenceInterval":
        if self.lower > self.upper:
            raise ValueError("Confidence interval lower bound exceeds its upper bound")
        return self


class Provenance(SchemaModel):
    input_hash: HashDigest
    config_hash: HashDigest
    method: str
    population: str
    parameters: dict[str, str | int | float | bool] = Field(default_factory=dict)


class MetricReference(SchemaModel):
    metric_id: str
    dimensions: dict[str, str] = Field(default_factory=dict)

    def key(self) -> tuple[str, tuple[tuple[str, str], ...]]:
        return self.metric_id, tuple(sorted(self.dimensions.items()))


class Metric(MetricReference):
    value: int | float | None
    numerator: int | float | None = None
    denominator: int | float | None = None
    ci: ConfidenceInterval | None = None
    n: NonnegativeInt | None
    suppressed: bool = False
    reason: str | None = None
    definition: str
    unit: MetricUnit
    provenance: Provenance

    @model_validator(mode="after")
    def validate_release_state(self) -> "Metric":
        if self.value is None and (not self.reason or not self.reason.strip()):
            raise ValueError("Unavailable or suppressed metrics require a reason")
        if self.suppressed and any(
            value is not None for value in (self.value, self.numerator, self.denominator, self.ci, self.n)
        ):
            raise ValueError("Suppressed metrics must omit numeric fields")
        if self.unit == "count" and self.value is not None and (self.value < 0 or self.value != int(self.value)):
            raise ValueError("Counts must be nonnegative whole numbers")
        if self.unit == "p_value" and self.value is not None and not 0 <= self.value <= 1:
            raise ValueError("P-values must be between zero and one")
        if self.unit in ("proportion", "percentage_point") and self.value is not None:
            if self.numerator is None or self.denominator is None or self.denominator <= 0:
                raise ValueError("Released shares and percentage-point changes require their calculation base")
            if self.unit == "proportion" and not 0 <= self.numerator <= self.denominator:
                raise ValueError("A proportion numerator must be within its denominator")
            scale = 100 if self.unit == "percentage_point" else 1
            if not isclose(self.value, scale * self.numerator / self.denominator, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError("The displayed metric must reconcile to its numerator and denominator")
        return self


class Caveat(SchemaModel):
    id: str
    label: str
    explanation: str


class Finding(SchemaModel):
    id: str
    observation: str
    interpretation: str
    action: str
    confidence: Literal["low", "moderate", "high"]
    caveat_ids: list[str] = Field(default_factory=list)
    metric_refs: list[MetricReference] = Field(default_factory=list)


class ThemeSummary(SchemaModel):
    id: str
    label: str
    method: Literal["codebook", "embedding"]
    prevalence: list[MetricReference] = Field(default_factory=list)


class ThemeQuestion(SchemaModel):
    question_id: str
    label: str
    answered: MetricReference
    themes: list[ThemeSummary] = Field(default_factory=list)
    diagnostics: list[MetricReference] = Field(default_factory=list)


class ThemeData(SchemaModel):
    status: Literal["available", "unavailable"]
    questions: list[ThemeQuestion] = Field(default_factory=list)


class PublicQualityReport(SchemaModel):
    metrics: list[MetricReference] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SuppressionPolicy(SchemaModel):
    minimum_n: int = Field(default=10, ge=1)
    complementary: bool = True
    scope: Literal["within_table"] = "within_table"


class ReleaseMetadata(SchemaModel):
    policy_version: Literal["1.0.0"] = "1.0.0"
    software_version: str
    python_version: str
    library_versions: dict[str, str]
    codebook_version: str
    codebook_hash: HashDigest
    recommendation_status: Literal["automated_draft_for_staff_review"] = "automated_draft_for_staff_review"


class FilterProvenance(SchemaModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    spec: dict
    spec_hash: HashDigest
    input_count: NonnegativeInt
    included_count: NonnegativeInt
    removed_count: NonnegativeInt
    description: list[str]
    banner: str

    @model_validator(mode="after")
    def validate_filter(self):
        from .filters import FilterSpec, describe_spec
        spec = FilterSpec.model_validate(self.spec)
        if self.spec_hash != spec.spec_hash or self.description != describe_spec(spec):
            raise ValueError("Filter provenance does not match its specification.")
        if self.input_count != self.included_count + self.removed_count or self.included_count < 10:
            raise ValueError("Filter response counts do not reconcile or are too small.")
        if 0 < self.removed_count < 10:
            raise ValueError("A small excluded complement must not be exported.")
        expected = f"Filtered view: {'; '.join(self.description)}. {self.included_count:,} of {self.input_count:,} responses included. Not the full-sample result."
        if self.banner != expected: raise ValueError("Filtered-view banner does not match its provenance.")
        return self


class ReportBundle(SchemaModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    generated_at: AwareDatetime
    input_hash: HashDigest
    data_kind: Literal["survey", "synthetic"]
    metrics: list[Metric]
    findings: list[Finding]
    theme_data: ThemeData
    quality_report: PublicQualityReport
    suppression_policy: SuppressionPolicy
    definitions: dict[str, str]
    caveats: list[Caveat]
    release_metadata: ReleaseMetadata | None = None
    filter_provenance: FilterProvenance | None = None

    @model_validator(mode="after")
    def validate_references(self) -> "ReportBundle":
        metric_keys = {metric.key() for metric in self.metrics}
        if len(metric_keys) != len(self.metrics):
            raise ValueError("Report ledger contains duplicate metric keys")
        if any(metric.provenance.input_hash != self.input_hash for metric in self.metrics):
            raise ValueError("Report ledger input hash does not match the bundle")
        references = list(self.quality_report.metrics)
        caveat_ids = {caveat.id for caveat in self.caveats}
        for finding in self.findings:
            references.extend(finding.metric_refs)
            if set(finding.caveat_ids) - caveat_ids:
                raise ValueError(f"Finding {finding.id!r} references an unknown caveat")
        for question in self.theme_data.questions:
            references.append(question.answered)
            references.extend(question.diagnostics)
            for theme in question.themes:
                references.extend(theme.prevalence)
        if any(reference.key() not in metric_keys for reference in references):
            raise ValueError("Report section references a metric absent from the ledger")
        return self
