"""
Builds the DTIA workbook from a loaded DataLoader.

Sheets
------
Home                 — overview + instructions
Query                — interactive DTIA query engine (dropdowns + FILTER)
Compliance Database  — one row per section, with page references
Acts / Regulators / Topics — rollups
Lists (hidden)       — dropdown source values
"""

from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from .workbook import finish_sheet
from .styles import TITLE_FONT, TITLE_FILL, HEADER_FILL, HEADER_FONT, WRAP

WRAP_COLUMNS = {
    "Heading", "Topics", "Data Types", "Summary", "DTIA Summary",
    "Requirements", "Source Quote",
}


class ExcelWriter:

    def __init__(self, workbook, loader):
        self.wb = workbook
        self.loader = loader

    def build(self):
        self.write_lists()
        self.write_database()
        self.write_acts()
        self.write_regulators()
        self.write_topics()
        self.write_query()
        self.write_home()

    # =================================================================
    # LISTS (hidden) — dropdown sources
    # =================================================================

    def write_lists(self):
        ws = self.wb["Lists"]

        # (header, values) per column; "All" is prepended for filters.
        self._list_ranges = {}
        columns = [
            ("Country", self.loader.country_list),
            ("Category", self.loader.category_list),
            ("Topic", self.loader.topic_list),
            ("Data Type", self.loader.datatype_list),
            ("Financial Relevance", self.loader.relevance_list),
            ("Authority", self.loader.regulator_list),
        ]

        for col_idx, (header, values) in enumerate(columns, start=1):
            letter = get_column_letter(col_idx)
            ws.cell(1, col_idx, header)
            entries = ["All"] + list(values)
            for row_idx, value in enumerate(entries, start=2):
                ws.cell(row_idx, col_idx, value)
            last = len(entries) + 1
            self._list_ranges[header] = (
                f"Lists!${letter}$2:${letter}${last}"
            )

    # =================================================================
    # COMPLIANCE DATABASE
    # =================================================================

    def write_database(self):
        ws = self.wb["Compliance Database"]

        columns = list(self.loader.df.columns)
        ws.append(columns)
        for row in self.loader.df.itertuples(index=False):
            ws.append(list(row))

        finish_sheet(ws, "ComplianceTable")

        # Wrap the long text columns and widen them.
        for idx, name in enumerate(columns, start=1):
            if name in WRAP_COLUMNS:
                letter = get_column_letter(idx)
                ws.column_dimensions[letter].width = 45
                for cell in ws[letter][1:]:
                    cell.alignment = WRAP

    # =================================================================
    # QUERY ENGINE
    # =================================================================

    def write_query(self):
        ws = self.wb["Query"]
        ws.sheet_view.showGridLines = False

        ws["A1"] = "DTIA Query Engine"
        ws["A1"].font = TITLE_FONT
        ws["A1"].fill = TITLE_FILL
        ws.merge_cells("A1:D1")

        ws["A3"] = "Choose filters (leave as 'All' to ignore), then read the results below."
        ws["A3"].font = Font(italic=True)

        # Filter label -> (input cell, Lists header or None for free text)
        filters = [
            ("Country", "B4", "Country"),
            ("Category", "B5", "Category"),
            ("Topic", "B6", "Topic"),
            ("Data Type", "B7", "Data Type"),
            ("Financial Relevance", "B8", "Financial Relevance"),
            ("Authority", "B9", "Authority"),
            ("Keyword (free text)", "B10", None),
        ]

        for label, cell, list_header in filters:
            row = int(cell[1:])
            ws.cell(row, 1, label).font = Font(bold=True)
            target = ws[cell]
            if list_header:
                target.value = "All"
                dv = DataValidation(
                    type="list",
                    formula1=self._list_ranges[list_header],
                    allow_blank=True,
                )
                ws.add_data_validation(dv)
                dv.add(target)
            else:
                target.value = ""
            target.fill = HEADER_FILL

        # Live results — a single dynamic-array FILTER that spills.
        ws["A12"] = "Matching sections (scroll / widen columns to read):"
        ws["A12"].font = Font(bold=True)

        headers = list(self.loader.df.columns)
        for idx, name in enumerate(headers, start=1):
            c = ws.cell(13, idx, name)
            c.fill = HEADER_FILL
            c.font = HEADER_FONT

        ws["A14"] = self._filter_formula()

        ws.column_dimensions["A"].width = 22
        for letter in ("B", "C", "D"):
            ws.column_dimensions[letter].width = 24
        ws.freeze_panes = "A14"

    def _filter_formula(self):
        t = "ComplianceTable"
        # Each line: "All"/blank matches everything, otherwise exact match
        # (or substring for the comma-joined list columns and keyword).
        criteria = (
            f'((B4="All")+({t}[Country]=B4))*'
            f'((B5="All")+({t}[Category]=B5))*'
            f'((B6="All")+ISNUMBER(SEARCH(B6,{t}[Topics])))*'
            f'((B7="All")+ISNUMBER(SEARCH(B7,{t}[Data Types])))*'
            f'((B8="All")+({t}[Financial Relevance]=B8))*'
            f'((B9="All")+({t}[Authority]=B9))*'
            f'((B10="")+ISNUMBER(SEARCH(B10,'
            f'{t}[Heading]&" "&{t}[Summary]&" "&{t}[DTIA Summary]&" "&'
            f'{t}[Requirements]&" "&{t}[Source Quote])))'
        )
        return (
            f'=IFERROR(FILTER({t},{criteria},'
            f'"No matching sections - broaden your filters"),'
            f'"No matching sections - broaden your filters")'
        )

    # =================================================================
    # HOME
    # =================================================================

    def write_home(self):
        ws = self.wb["Home"]
        ws.sheet_view.showGridLines = False

        ws["A1"] = "DTIA Compliance Knowledge Base"
        ws["A1"].font = TITLE_FONT
        ws["A1"].fill = TITLE_FILL
        ws.merge_cells("A1:C1")

        stats = self.loader.summary()
        rows = [
            ("Countries", stats["countries"]),
            ("Acts", stats["acts"]),
            ("Regulators", stats["regulators"]),
            ("Topics", stats["topics"]),
            ("Compliance sections", stats["rows"]),
        ]
        for i, (label, value) in enumerate(rows, start=3):
            ws.cell(i, 1, label).font = Font(bold=True)
            ws.cell(i, 2, value)

        ws["A10"] = "How to use"
        ws["A10"].font = Font(bold=True, size=13)
        steps = [
            "1. Open the Query sheet.",
            "2. Pick a Country, Category, Topic, Data Type, "
            "Financial Relevance or Authority — or type a keyword.",
            "3. Matching sections appear below, each with its Act and "
            "page reference for the source document.",
            "4. The Compliance Database sheet holds every extracted "
            "section; Acts / Regulators / Topics summarise them.",
        ]
        for i, step in enumerate(steps, start=11):
            ws.cell(i, 1, step).alignment = Alignment(wrap_text=True)
            ws.merge_cells(f"A{i}:C{i}")

        ws.column_dimensions["A"].width = 26
        ws.column_dimensions["B"].width = 14

    # =================================================================
    # ACTS
    # =================================================================

    def write_acts(self):
        ws = self.wb["Acts"]
        ws.append([
            "Country", "Act", "Sections", "Regulators", "Topics",
            "Financial Relevance",
        ])
        for act in self.loader.acts.values():
            ws.append([
                act["Country"], act["Act"], act["Sections"],
                ", ".join(sorted(act["Regulators"])),
                ", ".join(sorted(act["Topics"])),
                act["Financial Relevance"],
            ])
        finish_sheet(ws, "ActsTable")

    # =================================================================
    # REGULATORS
    # =================================================================

    def write_regulators(self):
        ws = self.wb["Regulators"]
        ws.append(["Authority", "Countries", "Acts"])
        for regulator, info in sorted(self.loader.regulators.items()):
            ws.append([
                regulator,
                ", ".join(sorted(info["Country"])),
                ", ".join(sorted(info["Acts"])),
            ])
        finish_sheet(ws, "RegulatorTable")

    # =================================================================
    # TOPICS
    # =================================================================

    def write_topics(self):
        ws = self.wb["Topics"]
        ws.append(["Topic", "Sections"])
        for topic, count in sorted(
            self.loader.topics.items(), key=lambda kv: -kv[1]
        ):
            ws.append([topic, count])
        finish_sheet(ws, "TopicTable")
