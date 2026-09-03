"""Compare application data with OCR lines and produce checks, a warning report and a verdict.

Pure function: no I/O, deterministic for the same inputs.
"""

from __future__ import annotations

import re
from typing import Any

from app.config import Settings
from app.schemas import (
    ApplicationFields,
    BeverageType,
    Check,
    CompareResult,
    Evidence,
    ImageInfo,
    OcrLine,
    Status,
    Verdict,
    WarningReport,
)

from .match import best_span, status_for
from .parsers import (
    alcohol_matches,
    alcohol_statement_required,
    fill_rule,
    is_standard_fill,
    parse_alcohol,
    parse_volumes,
    volumes_match,
)
from .warning import build_report

_LABELS = {
    "brand_name": "Brand name",
    "class_type": "Class / type designation",
    "alcohol_content": "Alcohol content",
    "net_contents": "Net contents",
    "bottler": "Name and address of bottler / producer",
    "country_of_origin": "Country of origin",
}


_ORIGIN_PREFIX = re.compile(
    r"^\s*(?:product of|produce of|made in|produced in|distilled in|bottled in|imported from|country of origin:?)\s+",
    re.I,
)


def _text_check(check_id: str, expected: str, lines: list[OcrLine], s: Settings, *, rule: str | None = None) -> Check:
    cand = best_span(expected, lines)
    status, note = status_for(
        cand, expected, review_at=s.match_review_threshold, mismatch_at=s.match_mismatch_threshold
    )
    return Check(
        id=check_id,
        label=_LABELS[check_id],
        status=status,
        expected=expected,
        found=cand.text if cand else None,
        score=float(cand.score) if cand else None,
        note=note,
        rule=rule,
        evidence=cand.evidence if cand else [],
    )


def _origin_check(expected: str, lines: list[OcrLine], s: Settings) -> Check:
    """Country of origin: 'USA' in the application matches 'Product of USA' on the label."""
    stripped = [ln.model_copy(update={"text": _ORIGIN_PREFIX.sub("", ln.text)}) for ln in lines]
    check = _text_check("country_of_origin", expected, stripped, s, rule="27 CFR 5.69 / 4.35 / 7.69; 19 CFR 134")
    if check.evidence:
        original = {id(ln): ln for ln in stripped}
        # restore the full line text in the evidence and the 'found' value for display
        found_lines = [
            ln for ln in lines if any(ln.box == ev.box and ln.image_index == ev.image_index for ev in check.evidence)
        ]
        check.evidence = [Evidence(image_index=ln.image_index, box=ln.box, text=ln.text) for ln in found_lines]
        if found_lines:
            check.found = " ".join(ln.text for ln in found_lines)
            if check.status is Status.match and check.found != expected:
                check.note = f"Label says '{check.found}'."
        del original
    return check


def _alcohol_check(app: ApplicationFields, lines: list[OcrLine], s: Settings) -> Check:
    required, why = alcohol_statement_required(app.beverage_type, app.class_type)
    expected = parse_alcohol(app.alcohol_content, allow_bare=True) if app.alcohol_content else None
    # Read every line; keep the first line whose text parses, with its evidence.
    found = None
    ev: list[Evidence] = []
    for ln in lines:
        got = parse_alcohol(ln.text)
        if got:
            found, ev = got, [Evidence(image_index=ln.image_index, box=ln.box, text=ln.text)]
            break
    if found is None:  # statements sometimes wrap ("45% Alc./Vol." / "(90 Proof)")
        got = parse_alcohol(" ".join(ln.text for ln in lines))
        if got:
            found = got
    base: dict[str, Any] = {
        "id": "alcohol_content",
        "label": _LABELS["alcohol_content"],
        "expected": app.alcohol_content,
        "found": found.raw if found and ev else (f"{found.percent}%" if found else None),
        "evidence": ev,
        "rule": "27 CFR 5.65 / 4.36 / 7.65",
    }
    if expected is None:
        if found is None:
            st = Status.not_found if required else Status.info
            return Check(status=st, note=("No alcohol statement in the application or on the label. " + why), **base)
        return Check(
            status=Status.info,
            score=None,
            note=f"Application gives no alcohol content; the label states {found.percent}%. " + why,
            **base,
        )
    if found is None:
        return Check(
            status=Status.not_found, note="No alcohol content statement could be read on the label. " + why, **base
        )
    if alcohol_matches(expected, found):
        note = f"Both state {found.percent}% alcohol by volume."
        if found.consistent is False:
            note += f" The label's proof ({found.proof}) does not equal twice the percentage. Confirm on the image."
            return Check(status=Status.needs_review, score=100.0, note=note, **base)
        return Check(status=Status.match, score=100.0, note=note, **base)
    return Check(
        status=Status.mismatch,
        score=0.0,
        note=f"Application states {expected.percent}%; the label reads {found.percent}%.",
        **base,
    )


def _net_contents_check(app: ApplicationFields, lines: list[OcrLine], s: Settings) -> tuple[Check, Check | None]:
    expected = parse_volumes(app.net_contents)
    base: dict[str, Any] = {
        "id": "net_contents",
        "label": _LABELS["net_contents"],
        "expected": app.net_contents,
        "rule": "27 CFR 5.70 / 4.37 / 7.70",
    }
    if not expected:
        return Check(
            status=Status.not_checked, note="Could not interpret the application's net contents value.", **base
        ), None
    exp_ml = expected[0].ml
    best_line: OcrLine | None = None
    best_vol = None
    for ln in lines:
        for v in parse_volumes(ln.text):
            if volumes_match(exp_ml, v.ml, tolerance=s.net_contents_tolerance):
                best_line, best_vol = ln, v
                break
            if best_vol is None:
                best_line, best_vol = ln, v
        if best_vol and volumes_match(exp_ml, best_vol.ml, tolerance=s.net_contents_tolerance):
            break
    fill_check: Check | None = None
    std = is_standard_fill(app.beverage_type, exp_ml)
    if std is False:
        fill_check = Check(
            id="standard_of_fill",
            label="Authorized container size",
            status=Status.needs_review,
            expected=app.net_contents,
            found=None,
            note=(
                f"{exp_ml:g} mL is not on the authorized standards of fill list for "
                f"{'distilled spirits' if app.beverage_type is BeverageType.spirits else 'wine'} "
                f"(as amended January 2025). Verify before approval."
            ),
            rule=fill_rule(app.beverage_type),
        )
    if best_vol is None:
        return Check(
            status=Status.not_found, note="No net contents statement could be read on the label.", **base
        ), fill_check
    ev = [Evidence(image_index=best_line.image_index, box=best_line.box, text=best_line.text)] if best_line else []
    if volumes_match(exp_ml, best_vol.ml, tolerance=s.net_contents_tolerance):
        return Check(
            status=Status.match,
            found=best_vol.raw,
            score=100.0,
            evidence=ev,
            note=f"Both state {exp_ml:g} mL"
            + (f" ({best_vol.raw} on the label)." if best_vol.unit not in ("ml",) else "."),
            **base,
        ), fill_check
    return Check(
        status=Status.mismatch,
        found=best_vol.raw,
        score=0.0,
        evidence=ev,
        note=f"Application states {exp_ml:g} mL; the label reads {best_vol.raw} ({best_vol.ml:g} mL).",
        **base,
    ), fill_check


def _verdict(checks: list[Check], warning: WarningReport, images: list[ImageInfo], s: Settings) -> tuple[Verdict, str]:
    if images and all(not im.quality.readable for im in images):
        return Verdict.unreadable, "None of the images could be read reliably. Request clearer label images."
    hard = {Status.mismatch, Status.not_found}
    soft = {Status.needs_review}
    statuses = [c.status for c in checks if c.id != "standard_of_fill"]
    issues = [c for c in checks if c.status in hard]
    reviews = [c for c in checks if c.status in soft]
    if warning.assessment in ("absent", "wording"):
        issues.append(Check(id="warning", label="Government warning", status=Status.mismatch))
    elif warning.assessment in ("case", "noise") or warning.anchor_caps is Status.needs_review:
        reviews.append(Check(id="warning", label="Government warning", status=Status.needs_review))
    if issues:
        names = ", ".join(c.label.lower() for c in issues)
        also = ", ".join(c.label.lower() for c in reviews if c.id not in {i.id for i in issues})
        tail = f" Also confirm: {also}." if also else ""
        return Verdict.issues_found, f"Issues found: {names}.{tail} The agent should review before any decision."
    if reviews:
        names = ", ".join(c.label.lower() for c in reviews)
        return Verdict.needs_review, f"Everything else matches; please confirm: {names}."
    if all(st in {Status.match, Status.info} for st in statuses) and warning.exact:
        return Verdict.ready_for_approval, "All checks match and the warning is exact. Ready for the agent's approval."
    return Verdict.needs_review, "Some checks could not be completed. Review the items marked."


def compare(app: ApplicationFields, lines: list[OcrLine], images: list[ImageInfo], s: Settings) -> CompareResult:
    checks: list[Check] = [
        _text_check("brand_name", app.brand_name, lines, s, rule="27 CFR 5.64 / 4.33 / 7.64"),
        _text_check("class_type", app.class_type, lines, s, rule="27 CFR 5.63 / 4.34 / 7.63"),
        _alcohol_check(app, lines, s),
    ]
    net, fill = _net_contents_check(app, lines, s)
    checks.append(net)
    if app.bottler:
        checks.append(_text_check("bottler", app.bottler, lines, s, rule="27 CFR 5.66 / 4.35 / 7.66"))
    if app.country_of_origin:
        checks.append(_origin_check(app.country_of_origin, lines, s))
    elif app.imported:
        checks.append(
            Check(
                id="country_of_origin",
                label=_LABELS["country_of_origin"],
                status=Status.not_checked,
                note="Marked as imported but the application gives no country of origin to compare. "
                "Imports must state the country of origin.",
                rule="19 CFR 134",
            )
        )
    if fill:
        checks.append(fill)
    warning = build_report(
        lines, review_similarity=s.warning_review_similarity, mismatch_similarity=s.warning_mismatch_similarity
    )
    verdict, summary = _verdict(checks, warning, images, s)
    return CompareResult(verdict=verdict, checks=checks, warning=warning, summary=summary)
