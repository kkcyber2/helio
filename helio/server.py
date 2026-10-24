"""HTTP API for the configurator. Standard library only."""
from __future__ import annotations

import hashlib
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .config import CATALOGUE, CartLine, ConfigError, cart_total, quote, validate

ROOT = Path(__file__).resolve().parent.parent / "static"


def catalogue_payload() -> dict:
    return {
        "base_price": "480.00",
        "groups": [
            {
                "id": g.id,
                "label": g.label,
                "required": g.required,
                "options": [
                    {
                        "id": o.id,
                        "label": o.label,
                        "price": str(o.price),
                        "colour": o.colour,
                        "note": o.note,
                    }
                    for o in g.options
                ],
            }
            for g in CATALOGUE
        ],
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "helio"

    def log_message(self, *args):  # keep the test output readable
        pass

    # ---------------------------------------------------------------- helpers
    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            raise ConfigError("request body is empty")
        if length > 64_000:
            raise ConfigError("request body is too large")
        try:
            data = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            raise ConfigError("request body is not valid JSON") from None
        if not isinstance(data, dict):
            raise ConfigError("request body must be an object")
        return data

    def _static(self, path: str) -> None:
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        target = (ROOT / rel).resolve()
        # Path traversal guard: the resolved file must stay inside ROOT.
        if not str(target).startswith(str(ROOT.resolve())) or not target.is_file():
            self.send_error(404)
            return
        body = target.read_bytes()
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        # A returning visitor must not run yesterday's JavaScript. Without an
        # explicit directive the browser invents its own heuristic freshness
        # window and can serve a stale bundle after a deploy.
        suffix = target.suffix.lower()
        if suffix in (".js", ".css", ".svg"):
            self.send_header("Cache-Control", "no-cache")
            self.send_header("ETag", f'"{hashlib.sha1(body).hexdigest()[:16]}"')
        else:
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _guard(self, fn):
        try:
            return fn()
        except ConfigError as exc:
            return self._json(
                {"error": str(exc), "field": exc.field}, 400
            )

    # ------------------------------------------------------------------ routes
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/catalogue":
            return self._json(catalogue_payload())
        return self._static(self.path.split("?")[0])

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/quote":
            return self._guard(self._quote)
        if self.path == "/api/cart":
            return self._guard(self._cart)
        self.send_error(404)

    def _quote(self) -> None:
        data = self._read_json()
        selection = data.get("selection")
        if not isinstance(selection, dict):
            raise ConfigError("selection is required", "selection")
        q = quote(selection)
        return self._json({"ok": True, "selection": validate(selection), "quote": q.as_dict()})

    def _cart(self) -> None:
        data = self._read_json()
        raw = data.get("lines")
        if not isinstance(raw, list):
            raise ConfigError("lines must be a list", "lines")
        if len(raw) > 50:
            raise ConfigError("too many lines", "lines")

        lines: list[CartLine] = []
        for entry in raw:
            if not isinstance(entry, dict):
                raise ConfigError("each line must be an object", "lines")
            selection = entry.get("selection")
            if not isinstance(selection, dict):
                raise ConfigError("each line needs a selection", "selection")
            qty = entry.get("qty", 1)
            if not isinstance(qty, int) or isinstance(qty, bool):
                raise ConfigError("quantity must be an integer", "qty")
            lines.append(
                CartLine(
                    sku=str(entry.get("sku") or "watch"),
                    selection=selection,
                    engraving=str(entry.get("engraving") or ""),
                    qty=qty,
                )
            )
            # Validate each line as it arrives so the error names the offender.
            validate(selection)

        return self._json(
            {"ok": True, "count": len(lines), "total": cart_total(lines).as_dict()}
        )


def serve(host: str = "127.0.0.1", port: int = 8140) -> None:
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"helio configurator on http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":  # pragma: no cover
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8140)
    serve(port=p.parse_args().port)
