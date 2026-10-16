"""Minimaler RTF-Textextrahierer (nur Standardbibliothek) für die Nexis-Uni-Exporte: Absätze, Unicode (\\uN), Hex-Zeichen (\\'hh, cp1252),
geschützte Leerzeichen; Schriften-, Farb-, Stil- und Kopfzeilen-Gruppen werden übersprungen."""
import re

_SKIP = {"fonttbl", "colortbl", "stylesheet", "info", "header", "footer", "pict", "listtable", "listoverridetable", "rsidtbl", "generator",
         "latentstyles", "themedata", "datastore", "xmlnstbl", "mmathPr", "fldinst", "bkmkstart", "bkmkend"}
_TOKEN = re.compile(rb"\\([a-zA-Z]+)(-?\d+)? ?|\\'([0-9a-fA-F]{2})|\\([^a-zA-Z])|([{}])|([^\\{}]+)")


def rtf_zu_text(roh: bytes) -> str:
    out, stack, skip_ab, uc = [], [], None, 1
    skip_tiefe = 0
    for m in _TOKEN.finditer(roh):
        wort, zahl, hexz, sym, klammer, text = m.groups()
        if klammer == b"{":
            stack.append(uc)
            if skip_ab is not None:
                skip_tiefe += 1
            continue
        if klammer == b"}":
            if stack:
                uc = stack.pop()
            if skip_ab is not None:
                if skip_tiefe == 0:
                    skip_ab = None
                else:
                    skip_tiefe -= 1
            continue
        if skip_ab is not None:
            continue
        if wort is not None:
            w = wort.decode("ascii")
            if w in _SKIP:
                skip_ab, skip_tiefe = w, 0
            elif w in ("par", "line", "sect", "page"):
                out.append("\n")
            elif w == "tab":
                out.append("\t")
            elif w == "u" and zahl is not None:
                n = int(zahl)
                out.append(chr(n + 65536 if n < 0 else n))
            elif w == "uc" and zahl is not None:
                uc = int(zahl)
            continue
        if hexz is not None:
            out.append(bytes([int(hexz, 16)]).decode("cp1252", errors="replace"))
        elif sym is not None:
            s = sym.decode("ascii")
            out.append({"~": "\u00a0", "_": "-", "{": "{", "}": "}", "\\": "\\"}.get(s, ""))
        elif text is not None:
            out.append(text.decode("cp1252", errors="replace").replace("\r", "").replace("\n", ""))
    return "".join(out)
