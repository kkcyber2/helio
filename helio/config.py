"""Configuration model and pricing.

A configurator is a product-modelling problem wearing a 3D hat. The part that
customers and lawyers care about is the price: it must be derived from the
configuration, auditable, and impossible to spoof from the client.

Every rule here is a pure function so it can be tested without a browser or a
database.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP


class ConfigError(ValueError):
    """The requested configuration is not buildable."""

    def __init__(self, message: str, field: str | None = None) -> None:
        self.field = field
        super().__init__(message)


# ------------------------------------------------------------------ the catalogue
@dataclass(frozen=True)
class Option:
    id: str
    label: str
    price: Decimal
    # Hex colours drive the 3D materials and the swatches from one source.
    colour: str = ""
    # Incompatible option ids. Kept symmetric by validation.
    excludes: tuple[str, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class Group:
    id: str
    label: str
    options: tuple[Option, ...]
    required: bool = True


def D(x: str | int) -> Decimal:
    return Decimal(str(x))


CATALOGUE: tuple[Group, ...] = (
    Group(
        "shell",
        "Shell",
        (
            Option("shell.alu", "Anodised aluminium", D("0"), "#b9bec4"),
            Option("shell.brass", "Brushed brass", D("140"), "#c9a227"),
            Option("shell.slate", "Slate composite", D("85"), "#3a3d42"),
            Option("shell.copper", "Living copper", D("190"), "#a85a3a",
                   note="Patina develops with use; not a defect."),
        ),
    ),
    Group(
        "face",
        "Dial",
        (
            Option("face.parchment", "Parchment", D("0"), "#e8e2d4"),
            Option("face.graphite", "Graphite", D("0"), "#2b2d31"),
            Option("face.sunburst", "Sunburst blue", D("60"), "#29465f"),
        ),
    ),
    Group(
        "strap",
        "Strap",
        (
            Option("strap.leather", "Vegetable-tanned leather", D("0"), "#6b4a2f",
                   excludes=("case.titanium",)),
            Option("strap.rubber", "Vulcanised rubber", D("40"), "#1d1f22"),
            Option("strap.steel", "Milanese steel", D("120"), "#c3c8cd"),
        ),
    ),
    Group(
        "case",
        "Case size",
        (
            Option("case.38", "38 mm", D("0")),
            Option("case.40", "40 mm", D("0")),
            Option("case.titanium", "42 mm titanium", D("310"),
                   excludes=("strap.leather",),
                   note="Titanium needs a rubber or steel strap: leather wears the lug."),
        ),
    ),
    Group(
        "engraving",
        "Caseback engraving",
        (
            Option("engraving.none", "None", D("0")),
            Option("engraving.text", "Text, up to 40 characters", D("35")),
        ),
        required=False,
    ),
)

BY_ID = {o.id: o for g in CATALOGUE for o in g.options}


def group_by_id(gid: str) -> Group:
    for g in CATALOGUE:
        if g.id == gid:
            return g
    raise ConfigError(f"unknown group {gid!r}", gid)


# ------------------------------------------------------------------- validation
def validate(selection: dict[str, str]) -> dict[str, str]:
    """Return a normalised selection or raise.

    The client never sends prices; it sends option ids, and this is the only
    place a price is decided.
    """
    if not isinstance(selection, dict):
        raise ConfigError("selection must be an object")

    out: dict[str, str] = {}
    for group in CATALOGUE:
        chosen = selection.get(group.id)
        if chosen is None:
            if group.required:
                raise ConfigError(f"{group.label} is required", group.id)
            # Optional groups default to their first option, which must be the
            # "none" variant -- enforced below by convention.
            out[group.id] = group.options[0].id
            continue
        if not isinstance(chosen, str):
            raise ConfigError(f"{group.label} must be a single option id", group.id)
        valid = {o.id for o in group.options}
        if chosen not in valid:
            raise ConfigError(
                f"{chosen!r} is not a valid {group.label.lower()} option", group.id
            )
        out[group.id] = chosen

    # Compatibility, checked in both directions so a bad catalogue is caught too.
    for gid, oid in out.items():
        opt = BY_ID[oid]
        for other_gid, other_oid in out.items():
            if other_gid == gid:
                continue
            if other_oid in opt.excludes:
                raise ConfigError(
                    f"{opt.label} is not available with {BY_ID[other_oid].label}",
                    other_gid,
                )
            other = BY_ID[other_oid]
            if oid in other.excludes:
                raise ConfigError(
                    f"{other.label} is not available with {opt.label}",
                    gid,
                )
    return out


# ---------------------------------------------------------------------- pricing
@dataclass
class Quote:
    base: Decimal
    lines: list[tuple[str, Decimal]] = field(default_factory=list)
    subtotal: Decimal = D("0")
    vat: Decimal = D("0")
    total: Decimal = D("0")

    def as_dict(self) -> dict:
        return {
            "base": str(self.base),
            "lines": [{"label": label, "amount": str(amount)} for label, amount in self.lines],
            "subtotal": str(self.subtotal),
            "vat": str(self.vat),
            "total": str(self.total),
        }


BASE_PRICE = D("480")
VAT_RATE = D("0.20")


def _money(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def quote(selection: dict[str, str], vat_rate: Decimal = VAT_RATE) -> Quote:
    """Price a validated selection. Premiums are additive and shown per line."""
    clean = validate(selection)
    q = Quote(base=BASE_PRICE)
    for gid in (g.id for g in CATALOGUE):
        opt = BY_ID[clean[gid]]
        if opt.price > 0:
            q.lines.append((opt.label, opt.price))
        q.subtotal += opt.price
    q.subtotal = _money(BASE_PRICE + q.subtotal)
    q.vat = _money(q.subtotal * vat_rate)
    q.total = _money(q.subtotal + q.vat)
    return q


# ------------------------------------------------------------------ engraving
ENGRAVING_LIMIT = 40
# Ordinary typographic punctuation belongs on an engraved caseback. Anything left
# out of this set is refused rather than stripped, so the customer never receives
# a different inscription from the one they approved.
ALLOWED_ENGRAVING = set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    " .,'-&·°—–:()/+"
)


def engrave(text: str) -> str:
    """Validate engraving text.

    Rejects control characters and anything outside the allowed set, because this
    string goes into a manufacturing order and an unexpected glyph is a remake.
    """
    if not isinstance(text, str):
        raise ConfigError("engraving must be text", "engraving")
    text = text.strip()
    if len(text) > ENGRAVING_LIMIT:
        raise ConfigError(f"engraving is limited to {ENGRAVING_LIMIT} characters", "engraving")
    bad = sorted({c for c in text if c not in ALLOWED_ENGRAVING})
    if bad:
        raise ConfigError(
            "engraving cannot contain " + ", ".join(repr(c) for c in bad), "engraving"
        )
    return text


# ------------------------------------------------------------------ cart logic
@dataclass
class CartLine:
    sku: str
    selection: dict[str, str]
    engraving: str = ""
    qty: int = 1

    def quote(self) -> Quote:
        return quote(self.selection)


MAX_QTY = 5


def add_line(lines: list[CartLine], new: CartLine) -> list[CartLine]:
    """Merge identical configurations, enforce the per-line cap.

    Two lines are identical only if the *whole* configuration matches, engraving
    included -- otherwise a personalised watch silently absorbs a plain one.
    """
    if not 1 <= new.qty <= MAX_QTY:
        raise ConfigError(f"quantity must be between 1 and {MAX_QTY}", "qty")
    validate(new.selection)
    if new.engraving:
        new.engraving = engrave(new.engraving)
    # The engraving surcharge belongs to the configuration, not the cart, so make
    # sure the selection actually carries it. Otherwise a caller could pass text
    # with the "none" option and get engraving for free.
    if new.engraving and new.selection.get("engraving") == "engraving.none":
        raise ConfigError("engraving text requires the engraving option", "engraving")

    out: list[CartLine] = []
    merged = False
    for line in lines:
        if (
            not merged
            and line.sku == new.sku
            and line.selection == new.selection
            and line.engraving == new.engraving
        ):
            total = line.qty + new.qty
            if total > MAX_QTY:
                raise ConfigError(
                    f"no more than {MAX_QTY} of one configuration per order", "qty"
                )
            out.append(CartLine(line.sku, line.selection, line.engraving, total))
            merged = True
        else:
            out.append(line)
    if not merged:
        out.append(new)
    return out


def cart_total(lines: list[CartLine]) -> Quote:
    base = D("0")
    subtotal = D("0")
    for line in lines:
        q = line.quote()          # already includes the engraving line, if any
        base += q.base * line.qty
        subtotal += q.subtotal * line.qty
    result = Quote(base=_money(base), subtotal=_money(subtotal))
    result.vat = _money(subtotal * VAT_RATE)
    result.total = _money(subtotal + result.vat)
    return result
