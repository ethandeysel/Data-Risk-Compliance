"""
Schemas used throughout the LLM extraction pipeline.

These are NOT Gemini schemas.

They simply define the expected structure
returned by the model and provide lightweight
validation before saving to disk.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any


# ----------------------------------------------------
# Individual Requirement
# ----------------------------------------------------

@dataclass
class Requirement:

    text: str

    obligation_type: str = ""

    applies_to: List[str] = field(default_factory=list)


# ----------------------------------------------------
# Extracted Section
# ----------------------------------------------------

@dataclass
class ComplianceExtraction:

    section: str = ""

    heading: str = ""

    summary: str = ""

    authority: str = ""

    financial_relevance: str = "None"

    confidence: str = "Low"

    topics: List[str] = field(default_factory=list)

    data_types: List[str] = field(default_factory=list)

    requirements: List[Requirement] = field(default_factory=list)

    source_quote: str = ""


# ----------------------------------------------------
# Batch
# ----------------------------------------------------

@dataclass
class ExtractionBatch:

    extractions: List[ComplianceExtraction] = field(
        default_factory=list
    )


# ----------------------------------------------------
# Convert JSON -> Dataclass
# ----------------------------------------------------

def from_json(data: Dict[str, Any]) -> ExtractionBatch:

    batch = ExtractionBatch()

    for item in data.get("extractions", []):

        reqs = []

        for r in item.get("requirements", []):

            reqs.append(

                Requirement(

                    text=r.get("text", ""),

                    obligation_type=r.get(
                        "obligation_type",
                        ""
                    ),

                    applies_to=r.get(
                        "applies_to",
                        []
                    )

                )

            )

        batch.extractions.append(

            ComplianceExtraction(

                section=item.get("section", ""),

                heading=item.get("heading", ""),

                summary=item.get("summary", ""),

                authority=item.get("authority", ""),

                financial_relevance=item.get(
                    "financial_relevance",
                    "None"
                ),

                confidence=item.get(
                    "confidence",
                    "Low"
                ),

                topics=item.get(
                    "topics",
                    []
                ),

                data_types=item.get(
                    "data_types",
                    []
                ),

                requirements=reqs,

                source_quote=item.get(
                    "source_quote",
                    ""
                )

            )

        )

    return batch


# ----------------------------------------------------
# Convert dataclass -> dict
# ----------------------------------------------------

def to_dict(batch: ExtractionBatch):

    return asdict(batch)