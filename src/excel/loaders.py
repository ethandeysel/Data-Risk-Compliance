from pathlib import Path
import json
import pandas as pd


class DataLoader:
    """
    Loads all extracted compliance JSON files and builds
    datasets used throughout the exporter.
    """

    def __init__(self, extracted_folder="data/extracted"):

        self.folder = Path(extracted_folder)

        self.rows = []

        self.acts = {}

        self.regulators = {}

        self.topics = {}

        self.data_types = {}

        self.countries = set()

    # ---------------------------------------------------------
    # Main
    # ---------------------------------------------------------

    def load(self):

        if not self.folder.exists():
            raise FileNotFoundError(
                f"{self.folder} does not exist."
            )

        country_dirs = sorted(
            d for d in self.folder.iterdir()
            if d.is_dir()
        )

        for country_dir in country_dirs:

            self._load_country(country_dir)

        self.df = pd.DataFrame(self.rows)

        if not self.df.empty:

            self.df.sort_values(

                [

                    "Country",

                    "Act",

                    "Section"

                ],

                inplace=True

            )

        return self

    # ---------------------------------------------------------
    # Country
    # ---------------------------------------------------------

    def _load_country(self, country_dir):

        country = country_dir.name

        self.countries.add(country)

        print(f"Loading {country}")

        for file in sorted(country_dir.glob("*.json")):

            self._load_document(

                country,

                file

            )

    # ---------------------------------------------------------
    # Document
    # ---------------------------------------------------------

    def _load_document(

        self,

        country,

        path

    ):

        with open(

            path,

            encoding="utf-8"

        ) as f:

            document = json.load(f)

        act = document["document"]

        act_key = (

            country,

            act

        )

        if act_key not in self.acts:

            self.acts[act_key] = {

                "Country": country,

                "Act": act,

                "Sections": 0,

                "Regulators": set(),

                "Topics": set(),

                "Data Types": set(),

                "Financial Relevance": ""

            }

        for section in document["sections"]:

            self._process_section(

                country,

                act,

                section

            )

    # ---------------------------------------------------------
    # Section
    # ---------------------------------------------------------

    def _process_section(

        self,

        country,

        act,

        section

    ):

        act_key = (

            country,

            act

        )

        self.acts[act_key]["Sections"] += 1

        authority = section.get(

            "authority",

            ""

        )

        if authority:

            self.acts[act_key][

                "Regulators"

            ].add(authority)

            if authority not in self.regulators:

                self.regulators[authority] = {

                    "Country": set(),

                    "Acts": set()

                }

            self.regulators[authority][

                "Country"

            ].add(country)

            self.regulators[authority][

                "Acts"

            ].add(act)

        relevance = section.get(

            "financial_relevance",

            ""

        )

        if relevance:

            self.acts[act_key][

                "Financial Relevance"

            ] = relevance

        topics = section.get(

            "topics",

            []

        )

        for topic in topics:

            self.acts[act_key][

                "Topics"

            ].add(topic)

            self.topics[topic] = (

                self.topics.get(topic, 0)

                + 1

            )

        dtypes = section.get(

            "data_types",

            []

        )

        for dtype in dtypes:

            self.acts[act_key][

                "Data Types"

            ].add(dtype)

            self.data_types[dtype] = (

                self.data_types.get(dtype, 0)

                + 1

            )

        requirements = section.get(

            "requirements",

            []

        )

        requirement_text = ""

        if requirements:

            parts = []

            for req in requirements:

                if isinstance(req, dict):

                    parts.append(

                        req.get(

                            "text",

                            ""

                        )

                    )

                else:

                    parts.append(

                        str(req)

                    )

            requirement_text = "\n\n".join(parts)

        self.rows.append({

            "Country":

                country,

            "Act":

                act,

            "Section":

                section.get(

                    "section",

                    ""

                ),

            "Heading":

                section.get(

                    "heading",

                    ""

                ),

            "Authority":

                authority,

            "Summary":

                section.get(

                    "summary",

                    ""

                ),

            "Requirements":

                requirement_text,

            "Topics":

                ", ".join(topics),

            "Data Types":

                ", ".join(dtypes),

            "Financial Relevance":

                relevance,

            "Confidence":

                section.get(

                    "confidence",

                    ""

                ),

            "Source Quote":

                section.get(

                    "source_quote",

                    ""

                )

        })

    # ---------------------------------------------------------
    # Summary
    # ---------------------------------------------------------

    def summary(self):

        return {

            "countries":

                len(self.countries),

            "acts":

                len(self.acts),

            "regulators":

                len(self.regulators),

            "topics":

                len(self.topics),

            "rows":

                len(self.rows)

        }

    # ---------------------------------------------------------
    # Lists used for dropdowns
    # ---------------------------------------------------------

    @property
    def country_list(self):

        return sorted(self.countries)

    @property
    def topic_list(self):

        return sorted(self.topics.keys())

    @property
    def regulator_list(self):

        return sorted(self.regulators.keys())

    @property
    def datatype_list(self):

        return sorted(self.data_types.keys())