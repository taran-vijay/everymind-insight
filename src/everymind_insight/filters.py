"""Versioned, explicit row exclusions. Raw values remain on the local server."""
import hashlib
import json
import math
from datetime import date
from typing import Literal

import pandas as pd
from pydantic import Field, model_validator

from .schemas import SchemaModel
from .subgroups import county_groups

SKILL_LABELS = {"identify_crises": "identify challenges and crises", "describe_988": "describe 988", "know_when_to_use_988": "know when to use 988"}
FIELD_LABELS = {
    "duration_seconds": "Completion time in seconds", "recommend_score": "Recommendation score (0–10)",
    "calling_score": "Calling likelihood (0–10)", "training_date": "Training date",
    "presenter_engaged": "Presenter engagement (1–5)", "presenter_knew_subject": "Presenter knowledge (1–5)",
    "presenter_organized": "Training organization (1–5)",
    **{f"{skill}_{timing}": f"{label.capitalize()} — {'recalled before' if timing == 'before' else 'current'} (1–5)"
       for skill, label in SKILL_LABELS.items() for timing in ("before", "after")},
    **{f"{skill}_change": f"{label.capitalize()} — current minus recalled before (−4 to +4)" for skill, label in SKILL_LABELS.items()},
}
OPTION_LABELS = {
    "exact_duplicates": "Exact duplicate responses (all fields except ID)",
    "speeders": "Finished in under the chosen number of seconds", "long_duration": "Took longer than the chosen number of seconds",
    "straightliners": "Same answer on all six objective questions", "large_drops": "A drop of four points from before to after",
    "invalid_training_date": "Missing or invalid training date", "invalid_timestamps": "Timestamps that do not make sense",
}
OptionID = Literal["exact_duplicates", "speeders", "long_duration", "straightliners", "large_drops", "invalid_training_date", "invalid_timestamps"]


class NumericRule(SchemaModel):
    field: str = Field(max_length=60)
    operator: Literal["below", "above", "between", "outside", "equals", "missing"]
    value: float | str | None = None
    values: list[float | str] | None = Field(default=None, max_length=2)

    @model_validator(mode="before")
    @classmethod
    def reject_boolean_values(cls, data):
        if isinstance(data, dict) and (isinstance(data.get("value"), bool) or any(isinstance(v, bool) for v in data.get("values") or [])):
            raise ValueError("Rule values must be numbers or ISO dates, not true/false.")
        return data

    @model_validator(mode="after")
    def check_rule(self):
        if self.field not in FIELD_LABELS:
            raise ValueError("Choose a supported numeric field or training_date.")
        if self.value is not None and self.values is not None:
            raise ValueError("Supply value or values, not both.")
        items = self.operands
        required = 0 if self.operator == "missing" else 2 if self.operator in {"between", "outside"} else 1
        if len(items) != required:
            raise ValueError(f"{self.operator} requires {required} value(s).")
        if self.field == "training_date":
            for item in items:
                if not isinstance(item, str) or date.fromisoformat(item).isoformat() != item:
                    raise ValueError("Use training dates in YYYY-MM-DD format.")
        else:
            for item in items:
                if not isinstance(item, (int, float)) or not math.isfinite(item):
                    raise ValueError("Use finite numeric values for score and duration rules.")
        if required == 2 and items[0] > items[1]:
            raise ValueError("The lower boundary must not exceed the upper boundary.")
        return self

    @property
    def operands(self):
        return self.values if self.values is not None else ([] if self.value is None else [self.value])


class CategoryExclusions(SchemaModel):
    county: list[str] = Field(default_factory=list, max_length=30)
    role: list[str] = Field(default_factory=list, max_length=30)
    language: list[str] = Field(default_factory=list, max_length=30)
    training_month: list[str] = Field(default_factory=list, max_length=120)


class FilterSpec(SchemaModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    exclusions: list[OptionID] = Field(default_factory=list, max_length=7)
    numeric_rules: list[NumericRule] = Field(default_factory=list, max_length=30)
    rule_logic: Literal["any", "all"] = "any"
    categorical_exclusions: CategoryExclusions = Field(default_factory=CategoryExclusions)
    speed_seconds: float = Field(default=30, gt=0, le=604800)
    long_seconds: float = Field(default=7200, gt=0, le=31536000)

    @model_validator(mode="before")
    @classmethod
    def reject_boolean_thresholds(cls, data):
        if isinstance(data, dict) and any(isinstance(data.get(field), bool) for field in ('speed_seconds', 'long_seconds')):
            raise ValueError("Duration thresholds must be positive numbers, not true/false.")
        return data

    @property
    def active(self):
        return bool(self.exclusions or self.numeric_rules or any(self.categorical_exclusions.model_dump().values()))

    def canonical(self):
        payload = self.model_dump(mode="json")
        payload["exclusions"] = sorted(set(payload["exclusions"]))
        payload["numeric_rules"] = sorted(payload["numeric_rules"], key=lambda x: json.dumps(x, sort_keys=True))
        payload["categorical_exclusions"] = {k: sorted(set(v)) for k, v in payload["categorical_exclusions"].items()}
        return payload

    @property
    def spec_hash(self):
        return hashlib.sha256(json.dumps(self.canonical(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def numeric_values(frame, field):
    if field.endswith("_change"):
        skill = field.removesuffix("_change")
        return frame[skill + "_after"] - frame[skill + "_before"]
    return frame[field]


def categories(frame):
    known_roles = {"Student", "Other", "Caregiver/parent", "School staff member", "Multiple roles"}
    return {
        "county": county_groups(frame.county),
        "role": frame.role_groups.map(lambda values: tuple(v if v in known_roles else "Unknown role" for v in values) or ("Missing role",)),
        "language": frame.language.where(frame.language.isin(["English", "Spanish"]), "Unknown language").fillna("Missing language"),
        "training_month": frame.training_date.dt.strftime("%Y-%m").fillna("Missing training month"),
    }


def match_rule(frame, rule):
    values = numeric_values(frame, rule.field)
    if rule.operator == "missing":
        return values.isna()
    operands = [pd.Timestamp(v) for v in rule.operands] if rule.field == "training_date" else rule.operands
    if rule.operator == "below": mask = values.lt(operands[0])
    elif rule.operator == "above": mask = values.gt(operands[0])
    elif rule.operator == "equals": mask = values.eq(operands[0])
    elif rule.operator == "between": mask = values.ge(operands[0]) & values.le(operands[1])
    else: mask = values.lt(operands[0]) | values.gt(operands[1])
    return mask.fillna(False).astype(bool)


def selection(frame, spec):
    """Options/category selections are unioned; any/all applies to numeric rules."""
    raw_columns = [c for c in frame if c.endswith("_raw") and c != "id_raw"]
    option_masks = {
        "exact_duplicates": frame['_response_group'].duplicated(keep='first') if '_response_group' in frame else frame[raw_columns].duplicated(keep="first"),
        "speeders": frame.duration_seconds.lt(spec.speed_seconds),
        "long_duration": frame.duration_seconds.gt(spec.long_seconds),
        "straightliners": frame.is_straightliner,
        "large_drops": frame.is_large_reversal,
        "invalid_training_date": frame.training_date.isna(),
        "invalid_timestamps": frame.is_invalid_timestamp | frame.is_impossible_timestamp | frame.start_time.isna() | frame.completion_time.isna(),
    }
    removed = pd.Series(False, index=frame.index)
    for option in spec.exclusions: removed |= option_masks[option].fillna(False)
    rules = [match_rule(frame, rule) for rule in spec.numeric_rules]
    if rules:
        table = pd.concat(rules, axis=1)
        removed |= table.any(axis=1) if spec.rule_logic == "any" else table.all(axis=1)
    for field, values in spec.categorical_exclusions.model_dump().items():
        series = categories(frame)[field]
        allowed = set(v for row in series for v in row) if field == "role" else set(series)
        if set(values) - allowed:
            raise ValueError(f"Choose available {field} categories from the field list.")
        removed |= series.map(lambda row: bool(set(row) & set(values))) if field == "role" else series.isin(values)
    return ~removed.fillna(False).astype(bool), option_masks, rules


def describe_spec(spec):
    labels = []
    for option in spec.canonical()["exclusions"]:
        if option == "speeders": labels.append(f"finished in under {spec.speed_seconds:g} seconds")
        elif option == "long_duration": labels.append(f"took longer than {spec.long_seconds:g} seconds")
        else: labels.append(OPTION_LABELS[option].lower())
    operators = {"below": "is below", "above": "is above", "equals": "equals", "between": "is between (inclusive)", "outside": "is outside", "missing": "is missing"}
    ordered_rules = sorted(spec.numeric_rules, key=lambda r: json.dumps(r.model_dump(mode='json'), sort_keys=True))
    numeric = [f"{FIELD_LABELS[r.field]} {operators[r.operator]} {' and '.join(str(v) for v in r.operands)}".strip() for r in ordered_rules]
    if numeric: labels.append(f"{'any' if spec.rule_logic == 'any' else 'all'} numeric rule(s): " + "; ".join(numeric))
    for field, values in spec.categorical_exclusions.model_dump().items():
        if values: labels.append(f"{field.replace('_', ' ')}: {', '.join(sorted(set(values)))}")
    return labels
