# Helio

A 3D watch configurator where the price is derived on the server and cannot be
spoofed from the browser.

Most 3D configurators are a rendering demo with a price label bolted on. Helio
treats the hard part as the *commerce* — a configuration is a small constraint
problem, and the price is a server-side consequence of it, not a number the
client sends back.

## What it does

- **Live 3D preview.** Shell, dial, strap and case are assembled in Three.js and
  recolour from the same catalogue data that drives the pricing, so a swatch and
  a material can never disagree.
- **Server-derived pricing.** The client sends option *ids* only. `POST /api/quote`
  validates them against the catalogue and returns the itemised total. A tampered
  payload is refused, not quietly repriced.
- **Real refusals.** Titanium needs a rubber or steel strap because leather wears
  the lug. The API says so by name rather than failing silently.
- **Engraving that fails loudly.** Text is validated against an allow-list of
  typographic characters. An emoji is rejected, not stripped — silently dropping
  a glyph would ship a different inscription than the customer approved.
- **Cart that respects personalisation.** Two watches merge only when the entire
  configuration matches, engraving included, so a personalised piece never
  absorbs a plain one.

## Running it

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python3 -m helio.server          # http://127.0.0.1:8140
```

Standard library only at runtime — no framework, no build step, no CDN. The
Three.js bundle is vendored in `static/vendor/`.

## Tests

```bash
python3 -m pytest -q             # 35 passed
```

The suite covers the pricing model, the exclusion matrix in both directions, the
engraving allow-list, cart merging and the quantity cap. Several tests exist
specifically to pin refusals: `test_engraving_text_without_the_paid_option_is_refused`
guards against a free-engraving hole that shipped in an earlier revision.

## Layout

```
helio/config.py    catalogue, validation, pricing, cart  (pure functions)
helio/server.py    HTTP API + static serving
static/            UI, Three.js scene, vendored three.min.js
tests/             pytest
```

## Licence

MIT © Konain Sultan Khan (KK)
