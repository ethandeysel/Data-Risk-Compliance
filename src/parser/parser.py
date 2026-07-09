import json
import re
from pathlib import Path

from .cleaner import clean_page


class SectionParser:

    def parse(self, json_file: Path):

        with open(json_file, encoding="utf-8") as f:
            document = json.load(f)

        full_text = ""
        page_map = []

        for page in document["pages"]:

            cleaned = clean_page(page["text"])

            page_map.append(
                (len(full_text), page["page"])
            )

            full_text += cleaned + "\n\n"

        full_text = self._remove_table_of_contents(full_text)

        return {
            "country": document["country"],
            "document": document["document"],
            "sections": self._extract_sections(
                full_text,
                page_map
            )
        }

    ###########################################################

    def _remove_table_of_contents(self, text):

        # Usually the TOC finishes before the first actual chapter
        chapters = list(
            re.finditer(
                r"CHAPTER\s+1",
                text,
                flags=re.IGNORECASE
            )
        )

        # first occurrence = TOC
        # second occurrence = actual Act

        if len(chapters) >= 2:

            return text[chapters[1].start():]

        return text

    ###########################################################

    def _extract_sections(self, text, page_map):

        section_pattern = re.compile(
            r"(?m)^(\d+)\.\s+([^\n]+)"
        )

        chapter_pattern = re.compile(
            r"CHAPTER\s+\d+[A-Z]?",
            re.IGNORECASE
        )

        part_pattern = re.compile(
            r"Part\s+[A-Z]",
            re.IGNORECASE
        )

        condition_pattern = re.compile(
            r"Condition\s+\d+",
            re.IGNORECASE
        )

        matches = list(section_pattern.finditer(text))

        sections = []

        for i, match in enumerate(matches):

            start = match.start()

            if i == len(matches)-1:
                end = len(text)
            else:
                end = matches[i+1].start()

            body = text[start:end].strip()

            chapter = self._last_match(
                chapter_pattern,
                text,
                start
            )

            part = self._last_match(
                part_pattern,
                text,
                start
            )

            condition = self._last_match(
                condition_pattern,
                text,
                start
            )

            sections.append({

                "identifier": match.group(1),

                "heading": match.group(2).strip(),

                "chapter": chapter,

                "part": part,

                "condition": condition,

                "page_start": self._page(
                    start,
                    page_map
                ),

                "page_end": self._page(
                    end,
                    page_map
                ),

                "text": body

            })

        return sections

    ###########################################################

    def _last_match(self, pattern, text, position):

        matches = list(
            pattern.finditer(
                text[:position]
            )
        )

        if matches:
            return matches[-1].group()

        return None

    ###########################################################

    def _page(self, offset, page_map):

        page = 1

        for char_pos, page_number in page_map:

            if char_pos <= offset:
                page = page_number
            else:
                break

        return page