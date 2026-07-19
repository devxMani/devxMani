from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.jsonc"


def strip_jsonc(text: str) -> str:
    out: list[str] = []
    i = 0
    n = len(text)
    in_string = False
    escape = False
    in_line_comment = False
    in_block_comment = False

    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
                out.append(ch)
            i += 1
            continue

        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 2
            else:
                i += 1
            continue

        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue

        if ch == "/" and nxt == "/":
            in_line_comment = True
            i += 2
            continue

        if ch == "/" and nxt == "*":
            in_block_comment = True
            i += 2
            continue

        out.append(ch)
        i += 1

    stripped = "".join(out)
    while True:
        updated = re.sub(r",(\s*[}\]])", r"\1", stripped)
        if updated == stripped:
            return stripped
        stripped = updated


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(strip_jsonc(path.read_text(encoding="utf-8")))


def escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def span(text: str, fill: str, weight: str | None = None) -> str:
    attrs = [f'fill="{fill}"']
    if weight:
        attrs.append(f'font-weight="{weight}"')
    return f'<tspan {" ".join(attrs)}>{escape_xml(text)}</tspan>'


def render_svg(config: dict[str, Any]) -> str:
    canvas = config["canvas"]
    layout = config["layout"]
    colors = config["colors"]
    lines = config["lines"]

    width = int(canvas["width"])
    height = int(canvas["height"])
    radius = int(canvas.get("radius", 0))
    font_family = str(canvas["font_family"])
    font_size = int(canvas["font_size"])
    top_y = int(layout["top_y"])
    left_x = int(layout["left_x"])
    line_height = int(canvas["line_height"])

    rendered_lines: list[str] = []
    for index, row in enumerate(lines):
        y = top_y + index * line_height
        spans = []
        for item in row["spans"]:
            fill = colors.get(item["fill"], item["fill"])
            weight = item.get("weight")
            spans.append(span(item["text"], fill, weight))
        rendered_lines.append(
            f'<text x="{left_x}" y="{y}" xml:space="preserve">{"".join(spans)}</text>'
        )

    svg = "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            (
                f'<svg xmlns="http://www.w3.org/2000/svg" '
                f'width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
                f'font-family="{font_family}" font-size="{font_size}px">'
            ),
            "<style>",
            "@font-face {",
            "src: local('Consolas'), local('Consolas Bold');",
            "font-family: 'ConsolasFallback';",
            "font-display: swap;",
            "-webkit-size-adjust: 109%;",
            "size-adjust: 109%;",
            "}",
            "text, tspan { white-space: pre; }",
            "</style>",
            (
                f'<rect width="{width}" height="{height}" '
                f'fill="{colors["background"]}" rx="{radius}"/>'
            ),
            *rendered_lines,
            "</svg>",
        ]
    )
    return svg + "\n"


def main() -> int:
    config = load_config(CONFIG_PATH)
    output = ROOT / config["output"]
    output.write_text(render_svg(config), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
