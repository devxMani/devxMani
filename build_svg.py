"""Generates dark_mode.svg / light_mode.svg templates with Arch Linux ASCII art.

Run this once to create the SVG templates, then run today.py (or let the Action
run) to fill in live stats.

 pip install pillow lxml && python build_svg.py
"""
import re
from xml.sax.saxutils import escape

WIDTH_CH = 60
SVG_WIDTH = 1000
SVG_HEIGHT = 650

ARCH_ART = [
    "                  -`",
    "                 .o+`",
    "                `ooo/",
    "               `+oooo:",
    "              `+oooooo:",
    "              -+oooooo+:",
    "            `/:-:++oooo+:",
    "           `/++++/+++++++:",
    "          `/++++++++++++++:",
    "         `/+++ooooooooooooo/`",
    "        ./ooosssso++osssssso+`",
    "       .oossssso-````/ossssss+`",
    "      -osssssso.      :ssssssso.",
    "     :osssssss/        osssso+++.",
    "    /ossssssss/        +ssssooo/-",
    "  `/ossssso+/:-        -:/+osssso+-",
    " `+sso+:-`                 `.-/+oso:",
    "`++:.                           `-/+/",
    "`.                                 `/",
    "",
    "",
    "",
    "",
    "",
    "",
]

LEN = dict(age=49, repo=6, star=13, commit=23, follower=10,
           contrib=5, loc=9, loc_add=9, loc_del=9)

PH = dict(repo="00", contrib="00", star="000", commit="0,000",
          follower="000", loc="000,000", loc_add="000,000", loc_del="00,000",
          age="0 years, 0 months, 0 days")


def static_dots(n):
    if n <= 2:
        return {0: "", 1: " ", 2: ". "}[n]
    return " " + "." * (n - 2) + " "


def jf_dots(length, value):
    just_len = max(0, length - len(value))
    if just_len <= 2:
        return {0: "", 1: " ", 2: ". "}[just_len]
    return " " + "." * just_len + " "


def pad_fill(length, value):
    return " " * max(0, length - len(value))


def keyspan(key):
    if "." in key:
        return ".".join('<tspan class="key">%s</tspan>' % escape(p) for p in key.split("."))
    return '<tspan class="key">%s</tspan>' % escape(key)


def field(key, value):
    pad = WIDTH_CH - 2 - len(key) - 1 - len(value)
    assert pad >= 0, (key, value, pad)
    return '. %s:%s<tspan class="value">%s</tspan>' % (keyspan(key), static_dots(pad), escape(value))


def dyn(key, vid, lenkey, placeholder):
    return '. %s:<tspan id="%s_dots">%s</tspan><tspan id="%s">%s</tspan>' % (
        keyspan(key), vid, jf_dots(LEN[lenkey], placeholder), vid, placeholder)


def blank():
    return ". "


def header(title):
    return "%s %s" % (escape(title), '—' * (WIDTH_CH - len(title) - 1))


def repos_line():
    return ('. Repos:'
            '<tspan id="repo_data_dots">%s</tspan><tspan id="repo_data">%s</tspan>'
            ' {Contributed:<tspan id="contrib_data_dots">%s</tspan><tspan id="contrib_data">%s</tspan>'
            '} | Stars:<tspan id="star_data_dots">%s</tspan><tspan id="star_data">%s</tspan>'
            ) % (jf_dots(LEN["repo"], PH["repo"]), PH["repo"],
                 pad_fill(LEN["contrib"], PH["contrib"]), PH["contrib"],
                 jf_dots(LEN["star"], PH["star"]), PH["star"])


def commits_line():
    return ('. Commits:'
            '<tspan id="commit_data_dots">%s</tspan><tspan id="commit_data">%s</tspan>'
            ' | Followers:<tspan id="follower_data_dots">%s</tspan><tspan id="follower_data">%s</tspan>'
            ) % (jf_dots(LEN["commit"], PH["commit"]), PH["commit"],
                 jf_dots(LEN["follower"], PH["follower"]), PH["follower"])


def loc_line():
    return ('. Total Lines of Code:'
            '<tspan id="loc_data_dots">%s</tspan><tspan id="loc_data">%s</tspan>'
            ' ( <tspan id="loc_add_dots">%s</tspan><tspan class="add" id="loc_add">%s</tspan>++, '
            '<tspan id="loc_del_dots">%s</tspan><tspan class="dele" id="loc_del">%s</tspan>-- )'
            ) % (pad_fill(LEN["loc"], PH["loc"]), PH["loc"],
                 pad_fill(LEN["loc_add"], PH["loc_add"]), PH["loc_add"],
                 pad_fill(LEN["loc_del"], PH["loc_del"]), PH["loc_del"])


# EDIT THESE PROJECTS to match your actual GitHub repos
PROJECTS = [
    ("Apple-iPhone-15-site", "iPhone 15 Pro clone with 3D"),
    ("StoryForge-AI", "AI choose-your-own-adventure"),
    ("AlgoGenesis", "Algorithm implementations in C"),
    ("Peek-link", "URL preview and metadata tool"),
]


def right_lines():
    lines = [
        header("devxMani"),
        field("Role", "Software Developer"),
        field("Host", "devxMani"),
        field("Location", "Milkyway"),
        dyn("Uptime", "age_data", "age", PH["age"]),
        field("Focus", "Intelligence"),
        blank(),
        field("Languages", "Python, TypeScript, Rust, C++"),
        field("Stack", "React, Node.js, FastAPI, Tailwind"),
        field("Site", "devxmani.tech"),
        blank(),
        header("- Projects"),
    ]
    for name, desc in PROJECTS:
        lines.append(field(name, desc))
    lines += [
        blank(),
        header("- Contact"),
        field("Email", "hello@devxmani.tech"),
        field("X", "@devxMani"),
        field("GitHub", "devxMani"),
        field("Portfolio", "devxmani.tech"),
        blank(),
        header("- GitHub Stats"),
        repos_line(),
        commits_line(),
        loc_line(),
    ]
    return lines


THEMES = {
    "dark_mode.svg": dict(
        bg="#0d1117", fg="#c9d1d9", key="#87CEEB", value="#e6edf3",
        cc="#4d4d49", ascii="#87CEEB", add="#3fb950", dele="#f85149"
    ),
    "light_mode.svg": dict(
        bg="#ffffff", fg="#24292f", key="#0366d6", value="#24292f",
        cc="#b8b8b3", ascii="#0366d6", add="#1a7f37", dele="#cf222e"
    ),
}


def place(line, y):
    return '<text x="390" y="%d" class="right">%s</text>' % (y, line)


def build(filename, theme, art):
    svg = '<?xml version="1.0" encoding="UTF-8"?>\n'
    svg += '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">\n' % (SVG_WIDTH, SVG_HEIGHT, SVG_WIDTH, SVG_HEIGHT)
    svg += '  <style>\n'
    svg += '    @import url("https://fonts.googleapis.com/css2?family=Consolas&amp;family=Courier+Prime&amp;display=swap");\n'
    svg += '    text { font-family: "Consolas", "Courier Prime", "Courier New", monospace; font-size: 16px; }\n'
    svg += '    .art { fill: %s; font-size: 16px; }\n' % theme["ascii"]
    svg += '    .right { fill: %s; font-size: 16px; }\n' % theme["fg"]
    svg += '    .key { fill: %s; font-size: 16px; font-weight: bold; }\n' % theme["key"]
    svg += '    .value { fill: %s; font-size: 16px; }\n' % theme["value"]
    svg += '    .add { fill: %s; font-size: 16px; }\n' % theme["add"]
    svg += '    .dele { fill: %s; font-size: 16px; }\n' % theme["dele"]
    svg += '  </style>\n'
    svg += '  <rect width="%d" height="%d" fill="%s" rx="12"/>\n' % (SVG_WIDTH, SVG_HEIGHT, theme["bg"])

    for i, line in enumerate(art):
        if line.strip():
            svg += '  <text x="30" y="%d" class="art">%s</text>\n' % (30 + 20 * i, escape(line))

    for i, line in enumerate(right_lines()):
        svg += '  %s\n' % place(line, 30 + 20 * i)

    svg += "</svg>\n"
    open(filename, "w").write(svg)


if __name__ == "__main__":
    ok = True
    for l in right_lines():
        vis = re.sub(r"<[^>]+>", "", l).replace("&", "&")
        if vis == ". ":
            continue
        if len(vis) != WIDTH_CH:
            ok = False
            print("WARN %3d |%s|" % (len(vis), vis))
    print("all lines 60ch" if ok else "MISALIGNED")

    for fn, theme in THEMES.items():
        build(fn, theme, ARCH_ART)
        print("wrote", fn)
