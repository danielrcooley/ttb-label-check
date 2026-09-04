"""Compare application data with OCR lines and produce checks, a warning report and a verdict.

Pure function: no I/O, deterministic for the same inputs.
"""

from __future__ import annotations

import re
from dataclasses import replace
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
from .normalize import company_forms, fold, fold_company
from .parsers import (
    Alcohol,
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


def _as_printed(check: Check, lines: list[OcrLine]) -> list[OcrLine]:
    """The original lines behind a check made on rewritten copies of them, in the candidate's own
    order, each line once: what the evidence and the "found" text should show."""
    found: list[OcrLine] = []
    for ev in check.evidence:
        for ln in lines:
            if ln.image_index == ev.image_index and ln.box == ev.box and not any(ln is f for f in found):
                found.append(ln)
                break
    check.evidence = [Evidence(image_index=ln.image_index, box=ln.box, text=ln.text) for ln in found]
    if found:
        check.found = " ".join(ln.text for ln in found)
    return found


def _origin_check(expected: str, lines: list[OcrLine], s: Settings) -> Check:
    """Country of origin: 'USA' in the application matches 'Product of USA' on the label."""
    stripped = [ln.model_copy(update={"text": _ORIGIN_PREFIX.sub("", ln.text)}) for ln in lines]
    check = _text_check("country_of_origin", expected, stripped, s, rule="27 CFR 5.69 / 4.35 / 7.69; 19 CFR 134")
    if check.evidence:
        # restore the full line text in the evidence and the 'found' value for display
        found_lines = _as_printed(check, lines)
        if found_lines and check.status is Status.match and check.found != expected:
            check.note = f"Label says '{check.found}'."
    return check


def bottler_check(expected: str, lines: list[OcrLine], s: Settings) -> Check:
    """Name and address as registered vs as printed. Labels abbreviate and prefix ("Brewed by
    GREEN CHEEK BEER CO." for "Green Cheek Beer Company"); the registry spells out. Neither the
    prefix nor an omitted corporate form is a difference in who bottled it, so both sides are folded
    with ``fold_company`` before the ordinary fuzzy match; evidence and the found text stay as
    printed. Two different forms ("LLC" against "Inc.") name two different legal entities: that
    match goes to Needs review with both forms in the note."""
    folded = [ln.model_copy(update={"text": fold_company(ln.text)}) for ln in lines]
    check = _text_check("bottler", fold_company(expected), folded, s, rule="27 CFR 5.66 / 4.35 / 7.66")
    check.expected = expected
    if check.evidence:
        found_lines = _as_printed(check, lines)
        if found_lines and check.status is Status.match:
            want, got = company_forms(expected), company_forms(check.found or "")
            if want and got and not (want <= got or got <= want):
                check.status = Status.needs_review
                check.note = (
                    f"Same name, but the corporate form differs: the application says "
                    f"{', '.join(sorted(want))}, the label says {', '.join(sorted(got))}. Confirm on the image."
                )
            elif fold(check.found or "") != fold(expected):
                check.note = f"Label says '{check.found}'."
    return check


def _alcohol_check(app: ApplicationFields, lines: list[OcrLine], s: Settings) -> Check:
    required, why = alcohol_statement_required(app.beverage_type, app.class_type)
    expected = parse_alcohol(app.alcohol_content, allow_bare=True) if app.alcohol_content else None
    # Parse every line. Explicit percent statements are compared with each other and proofs with each
    # other (a label may not contradict itself). A proof on its own line ("(90 Proof)") is the second
    # half of a wrapped statement: it is joined to the percent, not treated as a competing percent.
    candidates: list[tuple[Alcohol, OcrLine]] = []
    for ln in lines:
        got = parse_alcohol(ln.text)
        if got:
            candidates.append((got, ln))
    found: Alcohol | None = None
    ev: list[Evidence] = []
    distinct = sorted({round(a.percent, 1) for a, _ in candidates if a.percent is not None and not a.derived})
    proofs = sorted({a.proof for a, _ in candidates if a.proof is not None})
    if candidates:
        explicit = [(a, ln) for a, ln in candidates if not a.derived] or candidates
        chosen = next(((a, ln) for a, ln in explicit if expected and alcohol_matches(expected, a)), explicit[0])
        found, _line = chosen
        if found.proof is None and proofs:
            found = replace(found, proof=proofs[0])
        ev = [Evidence(image_index=ln.image_index, box=ln.box, text=ln.text) for _, ln in candidates]
    if found is None:  # a statement split mid-phrase across lines ("Alc." / "45% by vol.")
        found = parse_alcohol(" ".join(ln.text for ln in lines))
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
            return Check(status=st, note="No alcohol statement in the application or on the label. " + why, **base)
        if required:
            return Check(
                status=Status.needs_review,
                note=f"The application gives no alcohol content, but one is required and the label states "
                f"{found.percent}%. Confirm the application. " + why,
                **base,
            )
        return Check(
            status=Status.info,
            note=f"Application gives no alcohol content; the label states {found.percent}%. " + why,
            **base,
        )
    if found is None:
        return Check(
            status=Status.not_found, note="No alcohol content statement could be read on the label. " + why, **base
        )
    if len(distinct) > 1:
        stated = ", ".join(f"{v:g}%" for v in distinct)
        return Check(
            status=Status.mismatch,
            score=0.0,
            note=f"The label images state different alcohol contents ({stated}); the application says "
            f"{expected.percent:g}%. A label may not contradict itself.",
            **base,
        )
    if len(proofs) > 1:
        stated = ", ".join(f"{p:g}" for p in proofs)
        return Check(
            status=Status.mismatch,
            score=0.0,
            note=f"The label images state different proofs ({stated}); the application says "
            f"{expected.percent:g}%. A label may not contradict itself.",
            **base,
        )
    if alcohol_matches(expected, found):
        note = f"Both state {found.percent}% alcohol by volume."
        if expected.proof is not None and found.proof is not None and abs(expected.proof - found.proof) > 0.2:
            return Check(
                status=Status.mismatch,
                score=0.0,
                note=f"Percentages agree but proof differs: application {expected.proof:g}, label {found.proof:g}.",
                **base,
            )
        if found.consistent is False:
            note += f" The label's proof ({found.proof:g}) does not equal twice the percentage. Confirm on the image."
            return Check(status=Status.needs_review, score=100.0, note=note, **base)
        return Check(status=Status.match, score=100.0, note=note, **base)
    return Check(
        status=Status.mismatch,
        score=0.0,
        note=f"Application states {expected.percent}%; the label reads {found.percent}%.",
        **base,
    )


def _net_contents_check(app: ApplicationFields, lines: list[OcrLine], s: Settings) -> tuple[Check, Check | None]:
    base: dict[str, Any] = {
        "id": "net_contents",
        "label": _LABELS["net_contents"],
        "expected": app.net_contents or None,
        "rule": "27 CFR 5.70 / 4.37 / 7.70",
    }
    if not app.net_contents:
        # The application gives no value (the COLA form itself carries none). Show what the label
        # says and leave the confirmation to the agent: Needs review, never Ready on its own (D-040).
        read = next(((ln, v) for ln in lines for v in parse_volumes(ln.text)), None)
        if read is None:
            return Check(
                status=Status.needs_review,
                note="The application gives no net contents and none was read from the label. Check the image.",
                **base,
            ), None
        ln, vol = read
        return Check(
            status=Status.needs_review,
            found=vol.raw,
            evidence=[Evidence(image_index=ln.image_index, box=ln.box, text=ln.text)],
            note=f"The application gives no net contents. The label reads {vol.raw} ({vol.ml:g} mL); confirm it.",
            **base,
        ), None
    expected = parse_volumes(app.net_contents)
    if not expected:
        return Check(
            status=Status.needs_review,
            note="Could not interpret the application's net contents value; compare it with the label by eye.",
            **base,
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
    # Only these may be "not checked" and still allow Ready: the application may omit them, and then
    # there is nothing to compare. Any other check that could not be completed blocks Ready.
    may_be_unchecked = {"bottler", "country_of_origin"}
    statuses = [(c.id, c.status) for c in checks if c.id != "standard_of_fill"]
    issues = [c for c in checks if c.status in hard]
    reviews = [c for c in checks if c.status in soft]
    if warning.assessment == "not_required":
        pass
    elif warning.assessment in ("absent", "wording"):
        issues.append(Check(id="warning", label="Government warning", status=Status.mismatch))
    elif warning.assessment == "noise" or warning.anchor_caps is Status.needs_review:
        reviews.append(Check(id="warning", label="Government warning", status=Status.needs_review))
    if issues:
        names = ", ".join(c.label.lower() for c in issues)
        also = ", ".join(c.label.lower() for c in reviews if c.id not in {i.id for i in issues})
        tail = f" Also confirm: {also}." if also else ""
        return Verdict.issues_found, f"Issues found: {names}.{tail} The agent should review before any decision."
    if reviews:
        names = ", ".join(c.label.lower() for c in reviews)
        return Verdict.needs_review, f"Everything else matches; please confirm: {names}."
    complete = all(
        st in {Status.match, Status.info} or (st is Status.not_checked and cid in may_be_unchecked)
        for cid, st in statuses
    )
    if complete and warning.assessment == "not_required":
        return Verdict.ready_for_approval, (
            "All checks match; no health warning statement is required below 0.5% alcohol. "
            "Ready for the agent's approval."
        )
    if complete and warning.exact:
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
        checks.append(bottler_check(app.bottler, lines, s))
    else:
        checks.append(
            Check(
                id="bottler",
                label=_LABELS["bottler"],
                status=Status.not_checked,
                note="Not compared: the application did not provide the bottler's name and address.",
                rule="27 CFR 5.66 / 4.35 / 7.66",
            )
        )
    if app.country_of_origin:
        checks.append(_origin_check(app.country_of_origin, lines, s))
    elif app.imported:
        checks.append(
            Check(
                id="country_of_origin",
                label=_LABELS["country_of_origin"],
                status=Status.needs_review,
                note="Marked as imported but the application gives no country of origin to compare. "
                "Imports must state the country of origin: confirm it on the label and in the application.",
                rule="19 CFR 134",
            )
        )
    else:
        checks.append(
            Check(
                id="country_of_origin",
                label=_LABELS["country_of_origin"],
                status=Status.not_checked,
                note="Not compared: the application did not provide a country of origin (required for imports).",
                rule="19 CFR 134",
            )
        )
    if fill:
        checks.append(fill)
    warning = build_report(lines, mismatch_similarity=s.warning_mismatch_similarity)
    stated = parse_alcohol(app.alcohol_content, allow_bare=True) if app.alcohol_content else None
    if stated and stated.percent is not None and stated.percent < 0.5:
        warning = warning.model_copy(
            update={
                "assessment": "not_required",
                "notes": [
                    f"The application states {stated.percent:g}% alcohol. The health warning statement is required "
                    "only for beverages of 0.5% alcohol or more (27 CFR 16.10), so its absence is not a finding."
                ]
                + ([] if not warning.present else ["A warning statement is present anyway."]),
            }
        )
    verdict, summary = _verdict(checks, warning, images, s)
    return CompareResult(verdict=verdict, checks=checks, warning=warning, summary=summary)
