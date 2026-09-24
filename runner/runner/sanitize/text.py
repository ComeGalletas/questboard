"""Text preparation before recognition: Unicode folding, HTML to text, quoted replies and
signatures removed, and the final length cap. Pure functions; nothing is logged."""

from __future__ import annotations

import html
import re
import unicodedata
from html.parser import HTMLParser

CAP = 800  # chars of sanitized body kept (CLAUDE.md "cap body at ~800 chars")
WINDOW = 1200  # chars analysed; everything after is dropped before recognition

_ZERO_WIDTH = re.compile("[​‌‍⁠﻿­]")
_SPACES = re.compile("[    - ]")
_DASHES = re.compile("[‐-―−]")


def fold(text: str) -> str:
    """NFKC (full-width digits -> ASCII), no zero-width characters, plain spaces and dashes.
    Hiding a number with look-alike characters must not get it past the recognizers."""
    text = unicodedata.normalize("NFKC", text)
    text = _ZERO_WIDTH.sub("", text)
    text = _SPACES.sub(" ", text)
    text = _DASHES.sub("-", text)
    return text.replace("\r\n", "\n").replace("\r", "\n")


class _TextExtractor(HTMLParser):
    _BLOCK = frozenset({"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "table", "td"})
    _SKIP = frozenset({"script", "style", "head", "title"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self._SKIP:
            self._skip += 1
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP and self._skip:
            self._skip -= 1
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def html_to_text(markup: str) -> str:
    """Visible text only; links keep their text, never their href (hrefs carry tracking ids)."""
    parser = _TextExtractor()
    parser.feed(markup)
    parser.close()
    text = html.unescape("".join(parser.parts))
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n\n", text)).strip()


_REPLY_HEADERS = [
    re.compile(r"^\s*On .{0,200}wrote:\s*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*El .{0,200}escribi[óo]:\s*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*-{2,}\s*(Original Message|Mensaje original)\s*-{2,}\s*$", re.I | re.M),
    # Outlook: "From: …" / "De: …" followed by "Sent:" / "Enviado:" within a few lines.
    re.compile(r"^\s*(From|De):.*\n(?:.*\n){0,3}\s*(Sent|Enviado|Fecha|Date):", re.I | re.M),
]
_SIGN_OFF = re.compile(
    r"^\s*(--|—|__+|Sent from my .*|Enviado desde mi .*|Get Outlook for .*|"
    r"(Saludos|Cordialmente|Atentamente|Cordial saludo|Un saludo|Gracias|Muchas gracias|"
    r"Best|Best regards|Regards|Kind regards|Thanks|Thank you|Cheers|Sincerely)[,.!]?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def strip_replies_and_signature(text: str) -> tuple[str, list[str]]:
    """Drop quoted replies ("> …", "On … wrote:") and everything from a sign-off line on.
    Returns the text and which rules fired (for sanitization_log)."""
    fired: list[str] = []
    lines = text.split("\n")
    kept = [ln for ln in lines if not ln.lstrip().startswith(">")]
    if len(kept) != len(lines):
        fired.append("strip.quoted_lines")
    text = "\n".join(kept)
    cut = min((m.start() for p in _REPLY_HEADERS if (m := p.search(text))), default=None)
    if cut is not None:
        text = text[:cut]
        fired.append("strip.reply_header")
    sign = _SIGN_OFF.search(text)
    if sign and sign.start() > 0:
        text = text[: sign.start()]
        fired.append("strip.signature")
    return text.strip(), fired


def cap(text: str, limit: int = CAP) -> tuple[str, bool]:
    """At most `limit` chars, cut at whitespace so no token or word is split."""
    text = re.sub(r"[ \t]+", " ", text).strip()
    if len(text) <= limit:
        return text, False
    cut = text.rfind(" ", 0, limit + 1)
    newline = text.rfind("\n", 0, limit + 1)
    cut = max(cut, newline)
    return text[: cut if cut > 0 else limit].rstrip() + " …", True
