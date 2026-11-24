"""Tiny XML builder for ONVIF responses.

Responses are built as strings with explicit prefixes (tt:, tds:, ...). All prefixes are
declared once on the envelope (see namespaces.PREFIXES), which is what real cameras do and
what NVR parsers are tested against.

    el("tt:Resolution", el("tt:Width", 1920), el("tt:Height", 1080))
    el("tt:Bounds", x=0, y=0, width=1920, height=1080)      # attributes only
    el("tr2:Profiles", el("tr2:Name", "main"), token="Profile_1", fixed=True)

Children that are `str` produced by el() are inserted as-is; any other value (int, float,
bool, plain text wrapped by t()) is escaped text.
"""
from xml.sax.saxutils import escape, quoteattr

from lxml import etree


class Xml(str):
    """A string that is already XML (not escaped again)."""


def _fmt(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() and abs(v) < 1e15 else f"{v:.6g}"
    return str(v)


def t(value) -> str:
    """Escape text content."""
    return escape(_fmt(value))


def el(tag: str, *children, **attrs) -> Xml:
    attr_txt = "".join(
        f" {k.replace('__', ':').rstrip('_')}={quoteattr(_fmt(v))}" for k, v in attrs.items() if v is not None
    )
    body = []
    for c in children:
        if c is None:
            continue
        if isinstance(c, Xml):
            body.append(c)
        elif isinstance(c, (list, tuple)):
            body.extend(x for x in c if x is not None)
        else:
            body.append(t(c))
    if not body:
        return Xml(f"<{tag}{attr_txt}/>")
    return Xml(f"<{tag}{attr_txt}>{''.join(body)}</{tag}>")


def els(items) -> Xml:
    return Xml("".join(i for i in items if i))


# ---- request parsing helpers (namespace-agnostic: match by local name) ---------------------

def local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def ns_of(tag: str) -> str:
    return tag[1:].split("}", 1)[0] if tag.startswith("{") else ""


def child(node: etree._Element | None, *names: str) -> etree._Element | None:
    """Walk down by local names: child(body, "Configuration", "Resolution", "Width")."""
    cur = node
    for name in names:
        if cur is None:
            return None
        cur = next((c for c in cur if isinstance(c.tag, str) and local(c.tag) == name), None)
    return cur


def children(node: etree._Element | None, name: str) -> list[etree._Element]:
    if node is None:
        return []
    return [c for c in node if isinstance(c.tag, str) and local(c.tag) == name]


def text(node: etree._Element | None, *names: str, default: str | None = None) -> str | None:
    n = child(node, *names) if names else node
    if n is None or n.text is None:
        return default
    return n.text.strip()


def num(node, *names, default=None, cast=float):
    v = text(node, *names)
    if v is None or v == "":
        return default
    try:
        return cast(float(v)) if cast is int else cast(v)
    except ValueError:
        return default


def boolean(node, *names, default: bool | None = None) -> bool | None:
    v = text(node, *names)
    if v is None:
        return default
    return v.lower() in ("true", "1")
