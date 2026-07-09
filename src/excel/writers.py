from openpyxl.styles import Font
from .workbook import finish_sheet


class ExcelWriter:

    def __init__(self, workbook, loader):

        self.wb = workbook
        self.loader = loader

    def build(self):

        self.write_database()
        self.write_acts()
        self.write_regulators()
        self.write_topics()
        self.write_lists()
        self.write_home()
        self.write_query()

    # ==========================================================
    # HOME
    # ==========================================================

    def write_home(self):

        ws = self.wb["Home"]

        ws["A1"] = "DTIA Compliance Knowledge Base"
        ws["A1"].font = Font(size=18, bold=True)

        stats = self.loader.summary()

        ws["A3"] = "Countries"
        ws["B3"] = stats["countries"]

        ws["A4"] = "Acts"
        ws["B4"] = stats["acts"]

        ws["A5"] = "Regulators"
        ws["B5"] = stats["regulators"]

        ws["A6"] = "Topics"
        ws["B6"] = stats["topics"]

        ws["A7"] = "Compliance Sections"
        ws["B7"] = stats["rows"]

        ws["A9"] = "Instructions"

        ws["A10"] = "1. Open the Query sheet."
        ws["A11"] = "2. Select a country/topic."
        ws["A12"] = "3. Filter the Compliance Database."

    # ==========================================================
    # QUERY
    # ==========================================================

    def write_query(self):

        ws = self.wb["Query"]

        ws["A1"] = "DTIA Query"
        ws["A1"].font = Font(size=16, bold=True)

        ws["A3"] = "Source Country"
        ws["A4"] = "Destination Country"
        ws["A5"] = "Topic"
        ws["A6"] = "Authority"
        ws["A7"] = "Data Type"

        ws["C3"] = "(dropdown later)"
        ws["C4"] = "(dropdown later)"
        ws["C5"] = "(dropdown later)"
        ws["C6"] = "(dropdown later)"
        ws["C7"] = "(dropdown later)"

    # ==========================================================
    # DATABASE
    # ==========================================================

    def write_database(self):

        ws = self.wb["Compliance Database"]

        ws.append(list(self.loader.df.columns))

        for row in self.loader.df.itertuples(index=False):

            ws.append(list(row))

        finish_sheet(
            ws,
            "ComplianceTable"
        )

    # ==========================================================
    # ACTS
    # ==========================================================

    def write_acts(self):

        ws = self.wb["Acts"]

        ws.append([
            "Country",
            "Act",
            "Sections",
            "Regulators",
            "Topics",
            "Financial Relevance"
        ])

        for act in self.loader.acts.values():

            ws.append([

                act["Country"],

                act["Act"],

                act["Sections"],

                ", ".join(sorted(act["Regulators"])),

                ", ".join(sorted(act["Topics"])),

                act["Financial Relevance"]

            ])

        finish_sheet(
            ws,
            "ActsTable"
        )

    # ==========================================================
    # REGULATORS
    # ==========================================================

    def write_regulators(self):

        ws = self.wb["Regulators"]

        ws.append([
            "Authority",
            "Countries",
            "Acts"
        ])

        for regulator, info in self.loader.regulators.items():

            ws.append([

                regulator,

                ", ".join(sorted(info["Country"])),

                ", ".join(sorted(info["Acts"]))

            ])

        finish_sheet(
            ws,
            "RegulatorTable"
        )

    # ==========================================================
    # TOPICS
    # ==========================================================

    def write_topics(self):

        ws = self.wb["Topics"]

        ws.append([
            "Topic",
            "Sections"
        ])

        for topic, count in sorted(
            self.loader.topics.items()
        ):

            ws.append([

                topic,

                count

            ])

        finish_sheet(
            ws,
            "TopicTable"
        )

    # ==========================================================
    # LISTS
    # ==========================================================

    def write_lists(self):

        ws = self.wb["Lists"]

        ws["A1"] = "Countries"

        for i, value in enumerate(
            self.loader.country_list,
            start=2
        ):
            ws.cell(i, 1).value = value

        ws["B1"] = "Topics"

        for i, value in enumerate(
            self.loader.topic_list,
            start=2
        ):
            ws.cell(i, 2).value = value

        ws["C1"] = "Authorities"

        for i, value in enumerate(
            self.loader.regulator_list,
            start=2
        ):
            ws.cell(i, 3).value = value

        ws["D1"] = "Data Types"

        for i, value in enumerate(
            self.loader.datatype_list,
            start=2
        ):
            ws.cell(i, 4).value = value