"""Pricing and configuration rules. The refusals matter more than the totals."""
from __future__ import annotations

from decimal import Decimal

import pytest

from helio.config import (
    BY_ID,
    CATALOGUE,
    ENGRAVING_LIMIT,
    MAX_QTY,
    CartLine,
    ConfigError,
    add_line,
    cart_total,
    engrave,
    quote,
    validate,
)


def base_selection(**over):
    sel = {
        "shell": "shell.alu",
        "face": "face.parchment",
        "strap": "strap.leather",
        "case": "case.38",
        "engraving": "engraving.none",
    }
    sel.update(over)
    return sel


class TestValidate:
    def test_valid_selection_passes_through(self):
        assert validate(base_selection()) == base_selection()

    def test_missing_required_group_is_refused(self):
        sel = base_selection()
        del sel["shell"]
        with pytest.raises(ConfigError) as e:
            validate(sel)
        assert e.value.field == "shell"
        assert "required" in str(e.value)

    def test_optional_group_defaults_to_first_option(self):
        sel = base_selection()
        del sel["engraving"]
        assert validate(sel)["engraving"] == "engraving.none"

    def test_unknown_option_id_is_refused_with_the_field(self):
        with pytest.raises(ConfigError) as e:
            validate(base_selection(shell="shell.gold"))
        assert e.value.field == "shell"

    def test_option_from_another_group_is_refused(self):
        # A valid id, but not valid *here*. Catches a client that swaps two keys.
        with pytest.raises(ConfigError):
            validate(base_selection(face="strap.rubber"))

    def test_non_string_option_is_refused(self):
        with pytest.raises(ConfigError):
            validate(base_selection(shell=["shell.alu"]))

    def test_incompatible_pair_is_refused(self):
        # Titanium excludes leather.
        with pytest.raises(ConfigError) as e:
            validate(base_selection(case="case.titanium", strap="strap.leather"))
        assert "titanium" in str(e.value).lower() or "leather" in str(e.value).lower()

    def test_exclusion_is_enforced_from_either_direction(self):
        # The exclusion is declared on the *strap*, and must still fire when the
        # titanium case is the one being added last.
        a = base_selection(case="case.titanium", strap="strap.steel")
        assert validate(a)["case"] == "case.titanium"
        b = base_selection(case="case.38", strap="strap.leather")
        assert validate(b)["strap"] == "strap.leather"

    def test_catalogue_exclusions_are_symmetric(self):
        # Guards against a future edit that adds a one-way exclusion, which would
        # make the result depend on dictionary insertion order.
        for group in CATALOGUE:
            for opt in group.options:
                for other in opt.excludes:
                    assert opt.id in BY_ID[other].excludes, (
                        f"{opt.id} excludes {other} but not the reverse"
                    )

    def test_selection_is_not_mutated(self):
        sel = base_selection()
        snapshot = dict(sel)
        validate(sel)
        assert sel == snapshot


class TestQuote:
    def test_base_price_with_no_premiums(self):
        q = quote(base_selection())
        assert q.subtotal == Decimal("480.00")
        assert q.lines == []

    def test_premiums_are_itemised(self):
        q = quote(base_selection(shell="shell.brass"))
        assert ["Brushed brass", Decimal("140")] in [list(x) for x in q.lines]

    def test_vat_is_applied_to_the_subtotal(self):
        q = quote(base_selection())
        assert q.vat == Decimal("96.00")
        assert q.total == Decimal("576.00")

    def test_premiums_stack_additively(self):
        q = quote(base_selection(shell="shell.brass", face="face.sunburst", strap="strap.steel"))
        assert q.subtotal == Decimal("480.00") + 140 + 60 + 120

    def test_totals_are_exact_two_place_decimals(self):
        q = quote(base_selection(shell="shell.copper"))
        assert q.subtotal == Decimal("670.00")      # 480 base + 190 copper
        assert str(q.total) == "804.00"
        assert q.total == q.subtotal + q.vat

    def test_invalid_selection_cannot_be_quoted(self):
        with pytest.raises(ConfigError):
            quote(base_selection(shell="shell.platinum"))

    def test_quote_serialises_to_strings_not_floats(self):
        payload = quote(base_selection()).as_dict()
        assert isinstance(payload["total"], str)
        assert payload["total"] == "576.00"


class TestEngraving:
    def test_plain_text_is_accepted(self):
        assert engrave("For E. — 2026") == "For E. — 2026"

    def test_ordinary_punctuation_is_accepted(self):
        # An engraving that refuses a dash or a bracket is unusable in practice.
        for text in ("A/B 1:1", "(godparent)", "· 12° 34'"):
            assert engrave(text) == text

    def test_surrounding_whitespace_is_trimmed(self):
        assert engrave("   AK   ") == "AK"

    def test_limit_is_enforced_exactly(self):
        assert engrave("a" * ENGRAVING_LIMIT) == "a" * ENGRAVING_LIMIT
        with pytest.raises(ConfigError):
            engrave("a" * (ENGRAVING_LIMIT + 1))

    def test_control_characters_are_refused(self):
        with pytest.raises(ConfigError):
            engrave("bad\x00text")

    def test_emoji_is_refused_rather_than_silently_dropped(self):
        # Silently stripping would produce a different item than the customer saw.
        with pytest.raises(ConfigError):
            engrave("watch 🕰")

    def test_newline_is_refused(self):
        with pytest.raises(ConfigError):
            engrave("line one\nline two")

    def test_empty_is_allowed(self):
        assert engrave("") == ""


class TestCart:
    def test_two_distinct_configurations_stay_separate(self):
        a = CartLine("watch", base_selection())
        b = CartLine("watch", base_selection(shell="shell.brass"))
        assert len(add_line(add_line([], a), b)) == 2

    def test_identical_configurations_merge_quantity(self):
        a = CartLine("watch", base_selection(), qty=2)
        b = CartLine("watch", base_selection(), qty=1)
        out = add_line(add_line([], a), b)
        assert len(out) == 1 and out[0].qty == 3

    def test_engraved_and_plain_do_not_merge(self):
        # A personalised item must never absorb a plain one.
        a = CartLine("watch", base_selection(engraving="engraving.text"), engraving="AK")
        b = CartLine("watch", base_selection(engraving="engraving.text"), engraving="JD")
        out = add_line(add_line([], a), b)
        assert len(out) == 2

    def test_quantity_cap_is_enforced_per_line(self):
        a = CartLine("watch", base_selection(), qty=4)
        b = CartLine("watch", base_selection(), qty=2)
        with pytest.raises(ConfigError) as e:
            add_line(add_line([], a), b)
        assert e.value.field == "qty"

    def test_zero_quantity_is_refused(self):
        with pytest.raises(ConfigError):
            add_line([], CartLine("watch", base_selection(), qty=0))

    def test_engraving_text_without_the_paid_option_is_refused(self):
        with pytest.raises(ConfigError):
            add_line([], CartLine("watch", base_selection(), engraving="free text"))

    def test_cart_total_multiplies_unit_price_by_quantity(self):
        line = CartLine("watch", base_selection(shell="shell.brass"), qty=2)
        q = cart_total([line])
        unit = quote(base_selection(shell="shell.brass")).subtotal
        assert q.subtotal == unit * 2

    def test_engraving_is_charged_once_per_unit(self):
        sel = base_selection(engraving="engraving.text")
        line = CartLine("watch", sel, engraving="AK", qty=3)
        single = quote(sel).subtotal
        assert single == Decimal("515.00")            # 480 + 35
        assert cart_total([line]).subtotal == single * 3

    def test_empty_cart_is_zero_not_an_error(self):
        q = cart_total([])
        assert q.total == Decimal("0.00")

    def test_cart_total_matches_the_sum_of_its_lines(self):
        lines = [
            CartLine("watch", base_selection()),
            CartLine("watch", base_selection(shell="shell.copper", strap="strap.steel"), qty=2),
        ]
        q = cart_total(lines)
        expected = sum((l.quote().subtotal * l.qty for l in lines), Decimal("0"))
        assert q.subtotal == expected
