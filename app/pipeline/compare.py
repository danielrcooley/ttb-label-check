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

from .countries import country_named
from .match import best_span, status_for
from .normalize import company_forms, fold, fold_company, has_responsibility_prefix, split_registered_party
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
    if check.status in (Status.mismatch, Status.not_found):
        # A hard issue needs positive evidence: an origin statement on the label naming ANOTHER
        # COUNTRY. A statement that names no country the tool knows ("Bottled in Napa, CA"), or a
        # country not read anywhere, is a heuristic miss and goes to the person (D-041, D-045).
        want = country_named(expected)
        origin_lines = [ln for ln in lines if _ORIGIN_PREFIX.match(ln.text)]
        named = [(ln, country_named(_ORIGIN_PREFIX.sub("", ln.text))) for ln in origin_lines]
        same = next((ln for ln, c in named if c and c == want), None)
        # A Mismatch needs a country NAMED on the line. A U.S. state or a state code ("Napa, CA")
        # counts as the United States for a match against a domestic application, not as evidence
        # against an import: a wine bottled in California can still be a product of Italy (review 009)
        strict = [(ln, country_named(_ORIGIN_PREFIX.sub("", ln.text), states=False)) for ln in origin_lines]
        other = next(((ln, c) for ln, c in strict if c and c != want), None)
        if same is not None:
            check.status = Status.match
            check.found = same.text
            check.score = 100.0
            check.evidence = [Evidence(image_index=same.image_index, box=same.box, text=same.text)]
            check.note = f"Label says '{same.text}'."
        elif other is not None and want == "United States" and other[1] == "Georgia":
            # Georgia is a state and a country. Against a domestic application a bare "Georgia"
            # is most likely the state (the registry's origin for domestic products is the state):
            # a question for the person, not an issue (seen in the real tally, D-045).
            ln = other[0]
            check.status = Status.needs_review
            check.found = ln.text
            check.evidence = [Evidence(image_index=ln.image_index, box=ln.box, text=ln.text)]
            check.note = (
                f"The label's origin statement reads '{ln.text}'. Georgia is a U.S. state as well as a country; "
                f"the application says '{expected}'. Confirm on the image."
            )
        elif other is not None and want is not None:
            ln, country = other
            check.status = Status.mismatch
            check.found = ln.text
            check.evidence = [Evidence(image_index=ln.image_index, box=ln.box, text=ln.text)]
            check.note = (
                f"The label's origin statement reads '{ln.text}' ({country}); the application says '{expected}'."
            )
        elif origin_lines:
            ln = origin_lines[0]
            check.status = Status.needs_review
            check.found = ln.text
            check.evidence = [Evidence(image_index=ln.image_index, box=ln.box, text=ln.text)]
            check.note = (
                f"The label's origin line reads '{ln.text}', which the tool cannot match to a country; "
                f"the application says '{expected}'. Confirm on the image."
            )
        else:
            check.status = Status.needs_review
            check.note = (
                f"No origin statement naming '{expected}' was read. Imports must state the country of origin; "
                "check the image."
            )
    return check


_BOTTLER_RULE = "27 CFR 5.66 / 4.35 / 7.66"
_STATUS_RANK = {Status.match: 0, Status.needs_review: 1, Status.mismatch: 2, Status.not_found: 3}


def _near(lines: list[OcrLine], found: list[OcrLine], before: int = 2, after: int = 3) -> list[OcrLine]:
    """The found lines and their neighbours in reading order on the same image: the responsibility
    block, where a label prints the bottler's city and state. Not the whole label, where a state
    name is also an appellation or a marketing line (review 007)."""
    idx = [i for i, ln in enumerate(lines) if any(ln is f for f in found)]
    if not idx:
        return list(found)
    images = {ln.image_index for ln in found}
    lo, hi = max(0, min(idx) - before), min(len(lines), max(idx) + after + 1)
    return [ln for ln in lines[lo:hi] if ln.image_index in images]


def _address_on_label(
    city: str | None, state_forms: tuple[str, ...], near: list[OcrLine], everywhere: list[OcrLine]
) -> bool:
    """Whether the registered city and state were read as the bottler's address: either both within
    the responsibility block (``near``), or together on one line anywhere on the label ("Costa Mesa,
    CA" is an address line wherever it is printed, often on the other side of the package). A bare
    state name far from the name is not enough: on a wine label it is the appellation."""
    if not city or not state_forms:
        return False

    def has_state(t: str) -> bool:
        return any(re.search(rf"\b{re.escape(form)}\b", t) for form in state_forms)

    if any(fold(city) in t and has_state(t) for t in (fold(ln.text) for ln in everywhere)):
        return True
    texts = [fold(ln.text) for ln in near]
    return any(fold(city) in t for t in texts) and any(has_state(t) for t in texts)


def bottler_check(expected: str, lines: list[OcrLine], s: Settings) -> Check:
    """Name and address as registered vs as printed (D-041). The registered line may be the brief's
    short form ("Bottled by Old Tom Distillery, Bardstown, Kentucky") or COLAs' item 8 (trade name,
    legal name, street, city, state, ZIP, and sometimes the name used on the label). Labels print a
    responsibility phrase, one of those names, often abbreviated, and a city and state. So: the
    whole line and each registered name are tried, folded ("Brewed by", corporate forms); the best
    read wins; the city and state corroborate. Name and address read: Match. Name only: Needs review.
    A different name on the label's own "bottled by" line, or nothing resembling the name: Needs
    review with the reason, because the applicant and the lawful bottler may differ ("bottled for")
    and an unread line is a heuristic miss, not a proven defect. Two different corporate forms
    ("LLC" against "Inc.") on the same name: Needs review with both forms."""
    folded = [ln.model_copy(update={"text": fold_company(ln.text)}) for ln in lines]
    party = split_registered_party(expected)
    best: Check | None = None
    for cand in (expected, *party.names):
        c = _text_check("bottler", fold_company(cand), folded, s, rule=_BOTTLER_RULE)
        folded_name = fold_company(cand)
        if (
            c.status is Status.needs_review
            and c.found
            and folded_name
            and re.search(rf"(?<![a-z0-9]){re.escape(folded_name)}(?![a-z0-9])", fold_company(c.found))
        ):
            # The name is printed whole inside a longer line, with its address after it: that is how
            # labels print it ("VINTED & BOTTLED BY: RIVER ROAD FAMILY VINEYARDS AND WINERY, SEBASTOPOL, CA").
            c.status = Status.match
            c.note = "The registered name appears in full on the label's bottler line."
        if best is None or (_STATUS_RANK[c.status], -(c.score or 0)) < (_STATUS_RANK[best.status], -(best.score or 0)):
            best = c
    check = best if best is not None else _text_check("bottler", fold_company(expected), folded, s, rule=_BOTTLER_RULE)
    check.expected = expected
    found_lines = _as_printed(check, lines) if check.evidence else []
    if check.status is Status.match and found_lines:
        want, got = company_forms(expected), company_forms(check.found or "")
        if want and got and not (want <= got or got <= want):
            check.status = Status.needs_review
            check.note = (
                f"Same name, but the corporate form differs: the application says "
                f"{', '.join(sorted(want))}, the label says {', '.join(sorted(got))}. Confirm on the image."
            )
        elif (
            party.city
            and party.state
            and not _address_on_label(party.city, party.state_forms(), _near(lines, found_lines), lines)
        ):
            check.status = Status.needs_review
            check.note = (
                f"The name matches ('{check.found}'), but the registered city and state ({party.city}, "
                f"{party.state}) were not read next to it. Confirm the address on the image."
            )
        elif fold(check.found or "") != fold(expected):
            check.note = f"Label says '{check.found}'."
        return check
    if check.status in (Status.mismatch, Status.not_found):
        responsibility = [ln for ln in lines if has_responsibility_prefix(ln.text)]
        name = party.names[0] if party.names else expected
        if responsibility:
            ln = responsibility[0]
            check.status = Status.needs_review
            check.found = ln.text
            check.evidence = [Evidence(image_index=ln.image_index, box=ln.box, text=ln.text)]
            check.note = (
                f"The label's bottler line reads '{ln.text}', which does not resemble the application's "
                f"'{name}'. That is lawful when the product is bottled for the applicant by another permittee, "
                "and an issue otherwise. Confirm on the image."
            )
        else:
            check.status = Status.needs_review
            check.note = (
                f"No line resembling the registered name ('{name}') was read. A bottler statement is required "
                "on the label and is often in small print. Check the image."
            )
    return check


def _alcohol_check(app: ApplicationFields, lines: list[OcrLine], s: Settings) -> Check:
    required, why = alcohol_statement_required(app.beverage_type, app.class_type)
    expected = parse_alcohol(app.alcohol_content, allow_bare=True) if app.alcohol_content else None
    given_but_unreadable = bool(app.alcohol_content and app.alcohol_content.strip()) and expected is None
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
    if given_but_unreadable:
        # A value the application gives but the tool cannot read as a percentage or a proof is not
        # "no value": it must never pass as Info on its way to Ready (review 009)
        stated = f"; the label states {found.percent:g}%" if found and found.percent is not None else ""
        return Check(
            status=Status.needs_review,
            note=f"The application's alcohol content ('{app.alcohol_content}') could not be read as a "
            f"percentage or a proof{stated}. Compare it with the label by eye. " + why,
            **base,
        )
    if expected is None and len(distinct) > 1:
        stated = ", ".join(f"{v:g}%" for v in distinct)
        return Check(
            status=Status.needs_review,
            note=f"The application gives no alcohol content and the label images state different values "
            f"({stated}). Confirm which is right. " + why,
            **base,
        )
    if expected is None:
        if found is None:
            if required:  # nothing read is a heuristic miss, not a proven defect (D-041)
                return Check(
                    status=Status.needs_review,
                    note="An alcohol statement is required for this class, but none was given in the application "
                    "or read on the label. Inspect the label image. " + why,
                    **base,
                )
            return Check(
                status=Status.info, note="No alcohol statement in the application or on the label. " + why, **base
            )
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
            status=Status.needs_review,
            note=f"The application states {expected.percent:g}%, but no alcohol statement could be read on the "
            "label; it is often in small print. Inspect the image. " + why,
            **base,
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
        # An unread statement is a heuristic miss, not a proven defect (the same rule as an unread
        # alcohol statement, D-041): Needs review with the reason, never an issue on its own.
        return Check(
            status=Status.needs_review,
            note=(
                f"No net contents statement was read on the label; the application states {app.net_contents}. "
                "It is required on every label and is often in small print. Check the image."
            ),
            **base,
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


def _class_check(expected: str, lines: list[OcrLine], s: Settings) -> Check:
    """Class/type: the application's description against the designation the label prints. The
    two legitimately differ in wording (a varietal name for a table wine; "Kentucky Straight Bourbon
    Whiskey" for the class "straight bourbon whisky"), and the tool has no table of permitted
    designations, so a difference is never a proven defect: Match when the text agrees, otherwise
    Needs review with the closest text (D-041)."""
    check = _text_check("class_type", expected, lines, s, rule="27 CFR 5.63 / 4.34 / 7.63")
    if check.status in (Status.mismatch, Status.not_found):
        if check.status is Status.not_found:
            # Below the mismatch threshold the "closest" span is unrelated text that happens to
            # share a word ("...this wine showcase..."); showing it would mislead. Show nothing.
            check.found, check.evidence, check.score = None, [], None
        lead = (
            f"The closest text on the label ('{check.found}') differs from the application's class description."
            if check.found
            else "Nothing on the label resembles the application's class description."
        )
        check.status = Status.needs_review
        check.note = (
            lead + " Labels carry the designation the regulations permit for the class, so the wording may "
            "differ legitimately. Confirm the designation on the image."
        )
    return check


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
    elif warning.assessment == "noise" or Status.needs_review in (warning.anchor_caps, warning.anchor_bold):
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
        _class_check(app.class_type, lines, s),
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
    warning = build_report(
        lines,
        mismatch_similarity=s.warning_mismatch_similarity,
        heading_min_ratio=s.type_weight_heading_min_ratio,
        same_max_ratio=s.type_weight_same_max_ratio,
    )
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
