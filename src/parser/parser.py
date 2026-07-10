"""
Section parser.

Legal documents here use two very different numbering conventions:

  * Style A — "12. Security measures" : a number, a dot, then the
    heading (most Acts: POPIA, Banks Act, FICA, Cybercrimes…).

  * Style B — decimal numbering "12.1 …" with the heading on its own
    unnumbered line above it (the Joint Standards, directives, the
    cybersecurity policy framework).

The style is detected per document.  Style-A documents use the original,
well-tested logic unchanged.  Style-B documents previously matched only
their table-of-contents lines and dumped the whole body into one giant
"section"; they now get running headers + TOC lines stripped and are
split on their decimal numbering.

Page numbers are tracked per page so every section keeps an accurate
page reference for DTIA citation.
"""

import collections
import json
import re
from pathlib import Path

from .cleaner import clean_page

# "12. Heading" (original Style-A pattern — unchanged behaviour).
STYLE_A = re.compile(r"(?m)^(\d+)\.\s+([^\n]+)")

# "12.1" decimal subsection at the start of a line.
DECIMAL = re.compile(r"(?m)^\s*(\d+)\.(\d+)\b")

# A line that opens a numbered item (used to reject it as a heading).
NUMBERED_LINE = re.compile(r"^\s*(\d+[.)]|\(\w+\))")

DOT_LEADER = re.compile(r"\.{4,}")

CHAPTER_PATTERN = re.compile(r"CHAPTER\s+\d+[A-Z]?", re.IGNORECASE)
PART_PATTERN = re.compile(r"Part\s+[A-Z]", re.IGNORECASE)
CONDITION_PATTERN = re.compile(r"Condition\s+\d+", re.IGNORECASE)


class SectionParser:

    def parse(self, json_file: Path):
        with open(json_file, encoding="utf-8") as f:
            document = json.load(f)

        cleaned = [clean_page(p["text"]) for p in document["pages"]]

        if self._is_decimal_style(cleaned):
            sections = self._parse_decimal(document["pages"], cleaned)
        else:
            sections = self._parse_style_a(document["pages"], cleaned)

        return {
            "country": document["country"],
            "document": document["document"],
            "sections": sections,
        }

    # -----------------------------------------------------------------
    # Style detection
    # -----------------------------------------------------------------

    def _is_decimal_style(self, cleaned_pages):
        text = "\n\n".join(cleaned_pages)
        a = len(STYLE_A.findall(text))
        b = len(DECIMAL.findall(text))
        return b >= 10 and b > 1.5 * a

    # -----------------------------------------------------------------
    # Style A — original logic (unchanged), preserved for the 16 acts
    # that already parse correctly.
    # -----------------------------------------------------------------

    def _parse_style_a(self, pages, cleaned):
        full_text = ""
        page_map = []
        for page, page_text in zip(pages, cleaned):
            page_map.append((len(full_text), page["page"]))
            full_text += page_text + "\n\n"

        full_text = self._drop_leading_toc(full_text)

        matches = list(STYLE_A.finditer(full_text))
        sections = []
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
            sections.append(self._section(
                match.group(1), match.group(2).strip(),
                full_text, start, end, page_map,
            ))
        return sections

    def _drop_leading_toc(self, text):
        chapters = list(re.finditer(r"CHAPTER\s+1\b", text, re.IGNORECASE))
        if len(chapters) >= 2:
            return text[chapters[1].start():]
        return text

    # -----------------------------------------------------------------
    # Style B — decimal numbering.  Strips running headers + TOC lines,
    # then splits on the top-level number.
    # -----------------------------------------------------------------

    def _parse_decimal(self, pages, cleaned):
        headers = self._repeated_lines(cleaned)

        full_text = ""
        page_map = []
        for page, page_text in zip(pages, cleaned):
            kept = [
                line for line in page_text.split("\n")
                if not (line.strip() and line.strip() in headers)
                and not DOT_LEADER.search(line)
            ]
            page_map.append((len(full_text), page["page"]))
            full_text += "\n".join(kept).strip() + "\n\n"

        lines = full_text.split("\n")
        offsets, pos = [], 0
        for line in lines:
            offsets.append(pos)
            pos += len(line) + 1

        starts = []
        seen = set()
        for i, line in enumerate(lines):
            m = re.match(r"^\s*(\d+)\.(\d+)\b", line)
            if not m:
                continue
            top = int(m.group(1))
            if top in seen:
                continue
            # Accept only sequential section numbers (rejects "see 5.2").
            if seen and top != max(seen) + 1:
                continue
            if not seen and top > 3:
                continue
            seen.add(top)

            # Heading = nearest preceding non-empty, non-numbered line.
            heading_line = i
            j = i - 1
            while j >= 0:
                s = lines[j].strip()
                if not s:
                    j -= 1
                    continue
                if not NUMBERED_LINE.match(s):
                    heading_line = j
                break
            starts.append((
                offsets[heading_line],
                str(top),
                lines[heading_line].strip() if heading_line != i else "",
            ))

        if len(starts) < 3:
            return self._parse_style_a(pages, cleaned)

        sections = []
        for k, (start, identifier, heading) in enumerate(starts):
            end = starts[k + 1][0] if k + 1 < len(starts) else len(full_text)
            sections.append(self._section(
                identifier, heading, full_text, start, end, page_map,
            ))
        return sections

    @staticmethod
    def _repeated_lines(cleaned_pages):
        """Lines appearing on 3+ pages are page headers/footers."""
        counts = collections.Counter()
        for page_text in cleaned_pages:
            for stripped in {
                l.strip() for l in page_text.split("\n")
                if 15 <= len(l.strip()) <= 120
            }:
                counts[stripped] += 1
        return {line for line, n in counts.items() if n >= 3}

    # -----------------------------------------------------------------

    def _section(self, identifier, heading, text, start, end, page_map):
        return {
            "identifier": identifier,
            "heading": heading,
            "chapter": self._last_match(CHAPTER_PATTERN, text, start),
            "part": self._last_match(PART_PATTERN, text, start),
            "condition": self._last_match(CONDITION_PATTERN, text, start),
            "page_start": self._page(start, page_map),
            "page_end": self._page(end, page_map),
            "text": text[start:end].strip(),
        }

    def _last_match(self, pattern, text, position):
        matches = list(pattern.finditer(text[:position]))
        return matches[-1].group() if matches else None

    def _page(self, offset, page_map):
        page = page_map[0][1] if page_map else 1
        for char_pos, page_number in page_map:
            if char_pos <= offset:
                page = page_number
            else:
                break
        return page
