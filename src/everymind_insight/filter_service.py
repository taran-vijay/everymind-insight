"""Local in-memory report recomputation and guarded aggregate previews/exports."""
import csv
import io
import json
from collections import OrderedDict
from datetime import datetime, timezone
from threading import RLock

import numpy as np
import pandas as pd

from .filters import FIELD_LABELS, OPTION_LABELS, FilterSpec, categories, describe_spec, numeric_values, selection
from .release import release_metrics, small, validate_release
from .reporting import build_report, draft_findings, prepare_report
from .schemas import FilterProvenance
from .suppression import suppress_metric


def safe_count(n):
    return None if 0 < n < 10 else int(n)


def count_label(n):
    return "fewer than 10" if 0 < n < 10 else f"{n:,}"


def histogram(values, is_date=False):
    """Merge small bins, including their ranges, rather than publish tiny bars."""
    if is_date:
        clean = values.dropna().astype('int64').to_numpy() / 86400000000000
    else: clean = values.dropna().to_numpy(dtype=float)
    if len(clean) < 10: return []
    counts, edges = np.histogram(clean, bins=min(8, max(1, len(np.unique(clean)))))
    bins = [{"lower": float(edges[i]), "upper": float(edges[i+1]), "count": int(count)} for i, count in enumerate(counts)]
    while len(bins) > 1:
        index = next((i for i,b in enumerate(bins) if b['count'] < 10), None)
        if index is None: break
        neighbor = index - 1 if index == len(bins)-1 else index + 1
        lo, hi = sorted([index, neighbor])
        bins[lo:hi+1] = [{"lower": bins[lo]['lower'], "upper": bins[hi]['upper'], "count": bins[lo]['count'] + bins[hi]['count']}]
    if is_date:
        for b in bins:
            for edge in ('lower','upper'): b[edge] = pd.to_datetime(b[edge], unit='D').date().isoformat()
    return bins


class FilterService:
    def __init__(self, source, **kwargs):
        self.prepared = prepare_report(source, **kwargs)
        self.frame = self.prepared.quality.frame.loc[lambda f: f.is_usable_id].copy()
        self.input_hash = self.prepared.incoming.audit['input_hash']
        self.total = len(self.frame)
        if self.total < 10: raise ValueError("At least 10 usable responses are required.")
        self.generated_at = datetime.now(timezone.utc)
        self.cache = OrderedDict()
        self.released = []
        self.lock = RLock()

    def fields(self):
        fields = []
        for field, label in FIELD_LABELS.items():
            series = numeric_values(self.frame, field)
            missing = int(series.isna().sum())
            # A complete histogram plus the source total would expose 1–9 missing answers.
            bins = [] if small(missing,10) else histogram(series, field == 'training_date')
            low = high = None
            if series.notna().sum() >= 10:
                low, high = series.min(), series.max()
                if field == 'training_date': low,high = low.date().isoformat(),high.date().isoformat()
                else: low,high = float(low),float(high)
            fields.append({"id": field, "label": label, "type": "date" if field == 'training_date' else "number",
                           "min": low, "max": high,
                           "histogram": bins, "missing": safe_count(missing)})
        groups = {}
        for field, series in categories(self.frame).items():
            counts = series.explode().value_counts() if field == 'role' else series.value_counts()
            safe = {str(k): int(v) for k,v in counts.items() if v >= 10 and not small(self.total-v, 10)}
            # Do not release a lone complement of withheld categories.
            if field != 'role' and len(safe) < len(counts) and safe:
                safe.pop(min(safe, key=safe.get))
            groups[field] = [{"id": key, "count": value} for key,value in sorted(safe.items())]
        return {"available": True, "input_hash": self.input_hash, "total": self.total, "fields": fields,
                "categories": groups, "options": [{"id": k,"label":v} for k,v in OPTION_LABELS.items()],
                "note": "Counts refer to usable response IDs. Small categories and histogram bins are withheld or merged. Role selections can overlap."}

    def _selection(self, spec):
        # Only safe category labels offered to the browser may be selected or exported.
        available = self.fields()['categories']
        for field, values in spec.categorical_exclusions.model_dump().items():
            if set(values) - {v['id'] for v in available[field]}:
                raise ValueError(f"Choose a released {field} category; small categories are withheld.")
        return selection(self.frame, spec)

    def _reason(self, keep):
        kept, removed = int(keep.sum()), int((~keep).sum())
        if kept < 10: return "This selection leaves fewer than 10 responses. Broaden the selection to open a report."
        if 0 < removed < 10: return "This selection removes fewer than 10 responses. Included counts and results are withheld to protect that small complement."
        for prior in self.released:
            if 0 < int((prior != keep).sum()) < 10:
                return "This selection differs from an already opened view by fewer than 10 responses. Results are withheld to prevent comparison from revealing a small group."
        return None

    def report(self, spec):
        with self.lock:
            key = (self.input_hash, spec.spec_hash)
            keep, _, _ = self._selection(spec)
            reason = self._reason(keep)
            if reason: raise ValueError(reason)
            if key in self.cache:
                self.cache.move_to_end(key)
                return self.cache[key].model_copy(deep=True)
            bundle, _ = build_report(prepared=self.prepared, filters=spec, public_only=True)
            bundle.generated_at = self.generated_at
            if spec.active:
                baseline = self.report(FilterSpec())
                bases = {m.key():m for m in baseline.metrics}
                protected = []
                for metric in bundle.metrics:
                    base = bases.get(metric.key())
                    hide = False
                    if base and not base.suppressed and not metric.suppressed:
                        for field in ('n','numerator','denominator'):
                            a,b = getattr(base,field),getattr(metric,field)
                            if a is not None and b is not None and small(abs(a-b),10): hide = True
                        if metric.unit == 'proportion' and base.numerator is not None and metric.numerator is not None:
                            hide |= small(abs((base.denominator-base.numerator)-(metric.denominator-metric.numerator)),10)
                    protected.append(suppress_metric(metric, 'filter_comparison_protection') if hide else metric)
                bundle.metrics = release_metrics(protected, minimum=bundle.suppression_policy.minimum_n)
                bundle.findings = draft_findings(bundle.metrics)
                descriptions = describe_spec(spec)
                kept, removed = int(keep.sum()), int((~keep).sum())
                banner = f"Filtered view: {'; '.join(descriptions)}. {kept:,} of {self.total:,} responses included. Not the full-sample result."
                bundle.filter_provenance = FilterProvenance(spec=spec.canonical(), spec_hash=spec.spec_hash,
                    input_count=self.total, included_count=kept, removed_count=removed, description=descriptions, banner=banner)
            validate_release(bundle)
            self.cache[key] = bundle.model_copy(deep=True)
            while len(self.cache) > 16: self.cache.popitem(last=False)
            return bundle.model_copy(deep=True)

    def preview(self, spec):
        with self.lock:
            keep, options, rules = self._selection(spec)
            kept, removed = int(keep.sum()), int((~keep).sum())
            reason = self._reason(keep)
            option_counts = {k: (None if small(self.total-int(v.sum()),10) else safe_count(int(v.sum()))) for k,v in options.items()}
            selected = [options[k] for k in set(spec.exclusions)] + rules
            # Marginal counts + union must not expose a small overlap or contribution.
            if selected:
                signatures = pd.concat(selected, axis=1, ignore_index=True).fillna(False).astype(int)
                if any(0 < v < 10 for v in signatures.value_counts()):
                    option_counts = {k:None for k in option_counts}
                    rules_public = [None for r in rules]
                else: rules_public = [safe_count(int(r.sum())) for r in rules]
            else: rules_public = []
            result = {"input_hash":self.input_hash,"total":self.total,"kept":None if reason else kept,
                      "removed":None if reason else removed,"removed_label":count_label(removed) if removed < 10 else ("Withheld" if reason else count_label(removed)),
                      "can_apply": not bool(reason),"message":reason or "Options can overlap. The removed total counts each response once.",
                      "option_counts":option_counts,"rule_counts":rules_public,"headlines":[]}
            if reason: return result
            baseline, filtered = self.report(FilterSpec()), self.report(spec)
            lookup = {m.key():m for m in baseline.metrics}
            for m in filtered.metrics:
                if m.metric_id in {'agree_before','agree_after'} and m.dimensions.get('cohort')=='all_responses':
                    base = lookup[m.key()]
                    # Counts only, with the same guards as the final report.
                    result['headlines'].append({"skill":m.dimensions['skill'],"measure":m.metric_id,
                        "before": None if base.suppressed or m.suppressed else base.numerator,
                        "after": None if m.suppressed else m.numerator,
                        "base_before": None if base.suppressed or m.suppressed else base.denominator,
                        "base_after": None if m.suppressed else m.denominator})
            return result

    def open_report(self, spec):
        with self.lock:
            bundle = self.report(spec)
            keep, _, _ = self._selection(spec)
            if not any(keep.equals(mask) for mask in self.released): self.released.append(keep.copy())
            return bundle


def export_report(bundle, format):
    """Aggregate exports only. Never export source rows, comments or identifiers."""
    if format == 'json': return bundle.model_dump_json(indent=2).encode()
    provenance = bundle.filter_provenance
    total = next((m.value for m in bundle.metrics if m.metric_id == 'usable_responses' and not m.suppressed), None)
    meta = {"filter_spec_json":json.dumps(provenance.spec if provenance else FilterSpec().canonical(),sort_keys=True),
            "filter_spec_hash": provenance.spec_hash if provenance else FilterSpec().spec_hash,
            "filter_banner": provenance.banner if provenance else "Full-sample result: no responses removed by data options.",
            "input_hash":bundle.input_hash,
            "input_count":provenance.input_count if provenance else total,
            "included_count":provenance.included_count if provenance else total,
            "removed_count":provenance.removed_count if provenance else 0}
    rows = [{**m.model_dump(exclude={'provenance','ci'}), 'dimensions':json.dumps(m.dimensions,sort_keys=True), **meta} for m in bundle.metrics]
    if format == 'csv':
        output = io.StringIO(newline='')
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
        return output.getvalue().encode('utf-8-sig')
    if format == 'parquet':
        output = io.BytesIO(); pd.DataFrame(rows).to_parquet(output,index=False)
        return output.getvalue()
    raise ValueError("Choose json, csv, or parquet.")
