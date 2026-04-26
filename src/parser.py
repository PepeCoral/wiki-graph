import bz2
import csv
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable, Iterator, Optional, Tuple

import config

logger = logging.getLogger(__name__)

MW_NS = "http://www.mediawiki.org/xml/export-0.11/"

# Captures the TARGET portion of:
#   [[Target]]
#   [[Target|Label]]
#   [[Target#Section]]
#   [[Target#Section|Label]]
#   [[:Target]]
#
_LINK_RE = re.compile(
    r"\[\["           # opening brackets
    r":?"             # optional leading colon (cross-namespace display links)
    r"([^\[\]|#\n]+)" # group 1: page title (no brackets, pipes, anchors, newlines)
    r"(?:[#|][^\[\]]*)?" # optional #anchor or |label  (non-capturing)
    r"\]\]",          # closing brackets
    re.UNICODE,
)

_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

_TEMPLATE_RE = re.compile(r"\{\{[^{}]*\}\}", re.DOTALL)

_SKIP_PREFIXES: Tuple[str, ...] = (
    "File:", "Image:", "Category:", "Template:", "Wikipedia:",
    "WP:", "Help:", "Portal:", "Talk:", "User:", "Special:",
    "MediaWiki:", "TimedText:", "Module:", "Draft:", "Education_Program:",
    # Spanish-language prefixes (eswiki)
    "Archivo:", "Categoría:", "Plantilla:", "Ayuda:",
    "Proyecto:", "Anexo:", "Especial:", "Usuario:", "Módulo:",
    "Discusión:", "Portal:", "Wikimedia:",
)


def _normalize_title(raw: str) -> str:
    t = raw.strip().replace("_", " ")
    if t:
        t = t[0].upper() + t[1:]
    return t


def _is_skip_title(title: str) -> bool:
    return any(title.startswith(p) for p in _SKIP_PREFIXES)


def _clean_wikitext(wikitext: str) -> str:
    text = _COMMENT_RE.sub("", wikitext)
    text = _TEMPLATE_RE.sub("", text)
    text = _TEMPLATE_RE.sub("", text)
    return text


def _extract_links(wikitext: str) -> Iterator[str]:
    cleaned = _clean_wikitext(wikitext)
    for m in _LINK_RE.finditer(cleaned):
        raw_target = m.group(1)
        target = _normalize_title(raw_target)
        if target and not _is_skip_title(target):
            yield target


def _iter_articles(
    dump_path: Path,
) -> Iterator[Tuple[str, Optional[str], str]]:
    tag_page     = f"{{{MW_NS}}}page"
    tag_title    = f"{{{MW_NS}}}title"
    tag_ns       = f"{{{MW_NS}}}ns"
    tag_text     = f"{{{MW_NS}}}text"
    tag_redirect = f"{{{MW_NS}}}redirect"

    with bz2.open(dump_path, "rb") as fh:
        context = ET.iterparse(fh, events=("end",))
        title        = None
        ns           = None
        text         = ""
        redirect_tgt = None

        for event, elem in context:
            if elem.tag == tag_title:
                title = elem.text or ""
            elif elem.tag == tag_ns:
                ns = elem.text
            elif elem.tag == tag_redirect:
                redirect_tgt = elem.get("title") or ""
            elif elem.tag == tag_text:
                text = elem.text or ""
            elif elem.tag == tag_page:
                if ns == str(config.ARTICLE_NAMESPACE) and title:
                    norm_redirect = (
                        _normalize_title(redirect_tgt)
                        if redirect_tgt is not None
                        else None
                    )
                    yield title, norm_redirect, text
                title        = None
                ns           = None
                text         = ""
                redirect_tgt = None
                elem.clear()



def parse_dump(
    dump_path: Path,
    output_csv: Path,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> Path:
    if not dump_path.exists():
        raise FileNotFoundError(f"Dump not found: {dump_path}")

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Parsing %s → %s", dump_path, output_csv)

    pages_done      = 0
    pairs_written   = 0
    redirects_done  = 0

    with open(output_csv, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, delimiter="\t")

        for title, redirect_target, wikitext in _iter_articles(dump_path):
            norm_title = _normalize_title(title)

            if redirect_target is not None:
                if (
                    redirect_target
                    and not _is_skip_title(redirect_target)
                    and redirect_target != norm_title
                ):
                    writer.writerow([norm_title, redirect_target])
                    pairs_written += 1
                    redirects_done += 1
            else:
                seen: set[str] = set()
                for target in _extract_links(wikitext):
                    if target != norm_title and target not in seen:
                        writer.writerow([norm_title, target])
                        pairs_written += 1
                        seen.add(target)

            pages_done += 1
            if pages_done % 10_000 == 0:
                logger.info(
                    "  Processed %d pages (%d redirects), %d pairs so far",
                    pages_done, redirects_done, pairs_written,
                )
            if progress_cb:
                progress_cb(pages_done)

    logger.info(
        "Parsing done: %d pages (%d redirects), %d link pairs → %s",
        pages_done, redirects_done, pairs_written, output_csv,
    )
    return output_csv


def parse_small(progress_cb: Optional[Callable[[int], None]] = None) -> Path:
    return parse_dump(config.SMALL_DUMP_FILE, config.SMALL_LINKS_CSV, progress_cb)


def parse_full(progress_cb: Optional[Callable[[int], None]] = None) -> Path:
    return parse_dump(config.FULL_DUMP_FILE, config.FULL_LINKS_CSV, progress_cb)