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
        self.write_engine()
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

        # Results: classic INDEX/MATCH pulled from the hidden Engine sheet
        # (works in every Excel version — no dynamic arrays).
        n = len(self.loader.df)
        last = n + 1  # data rows on Compliance Database / Engine: 2..n+1

        ws["A12"] = f"Matching sections (of {n} total):"
        ws["A12"].font = Font(bold=True)
        ws["C12"] = f"=Engine!$D$1"          # live match count
        ws["C12"].font = Font(bold=True)

        headers = list(self.loader.df.columns)
        for idx, name in enumerate(headers, start=1):
            c = ws.cell(13, idx, name)
            c.fill = HEADER_FILL
            c.font = HEADER_FONT

        for r in range(14, 14 + n):
            k = r - 13  # this row shows the k-th matching section
            match = f"MATCH({k},Engine!$C$2:$C${last},0)"
            for idx in range(1, len(headers) + 1):
                col = get_column_letter(idx)
                # IF/ISNA/INDEX/MATCH only — no functions newer than 2003.
                ws.cell(r, idx).value = (
                    f'=IF(ISNA({match}),"",'
                    f"INDEX('Compliance Database'!${col}$2:${col}${last},"
                    f"{match}))"
                )
                if headers[idx - 1] in WRAP_COLUMNS:
                    ws.cell(r, idx).alignment = WRAP

        for idx, name in enumerate(headers, start=1):
            width = 45 if name in WRAP_COLUMNS else 18
            ws.column_dimensions[get_column_letter(idx)].width = width
        ws.column_dimensions["A"].width = 16
        ws.freeze_panes = "A14"

    # =================================================================
    # ENGINE (hidden) — per-row match flag + running rank
    # =================================================================

    def write_engine(self):
        ws = self.wb["Engine"]
        n = len(self.loader.df)
        last = n + 1
        db = "'Compliance Database'"

        ws["A1"] = "match"
        ws["B1"] = "rank"
        ws["C1"] = "rankval"
        ws["D1"] = f'=SUM($A$2:$A${last})'   # total matches (shown on Query)

        for i in range(2, last + 1):
            # Column map on Compliance Database:
            # A Country F Category G FinRelevance I Topics J DataTypes
            # K Authority ; keyword searches D,L,M,N,O.
            ws.cell(i, 1).value = (
                "=IF(AND("
                f'OR(Query!$B$4="All",{db}!$A{i}=Query!$B$4),'
                f'OR(Query!$B$5="All",{db}!$F{i}=Query!$B$5),'
                f'OR(Query!$B$6="All",ISNUMBER(SEARCH(Query!$B$6,{db}!$I{i}))),'
                f'OR(Query!$B$7="All",ISNUMBER(SEARCH(Query!$B$7,{db}!$J{i}))),'
                f'OR(Query!$B$8="All",{db}!$G{i}=Query!$B$8),'
                f'OR(Query!$B$9="All",{db}!$K{i}=Query!$B$9),'
                f'OR(Query!$B$10="",ISNUMBER(SEARCH(Query!$B$10,'
                f'{db}!$D{i}&" "&{db}!$L{i}&" "&{db}!$M{i}&" "&'
                f'{db}!$N{i}&" "&{db}!$O{i})))'
                "),1,0)"
            )
            # Running rank of matches; C mirrors it as a number for MATCH.
            ws.cell(i, 2).value = f'=IF($A{i}=1,SUM($A$2:$A{i}),"")'
            ws.cell(i, 3).value = f'=IF($A{i}=1,SUM($A$2:$A{i}),0)'

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
