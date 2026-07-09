import re

KEYWORDS = {

    # transfer
    "transfer",
    "transfers",
    "cross-border",
    "cross border",
    "outside the republic",
    "foreign",

    # processing
    "processing",
    "process",
    "processor",
    "operator",
    "third party",
    "recipient",

    # storage
    "storage",
    "retain",
    "retention",
    "record",
    "archive",
    "delete",
    "destruction",

    # security
    "security",
    "confidentiality",
    "integrity",
    "availability",
    "encryption",
    "access control",
    "authentication",
    "breach",
    "compromise",

    # privacy
    "personal information",
    "personal data",
    "special personal information",
    "consent",

    # financial
    "bank",
    "banking",
    "financial",
    "insurance",
    "payment",
    "payments",
    "credit",
    "investment",
    "customer",
    "client",

    # governance
    "information regulator",
    "supervisory authority",
    "outsourcing",
    "cloud"

}


def relevant(section):

    text = (
        section["heading"]
        + "\n"
        + section["text"]
    ).lower()

    hits = 0

    for keyword in KEYWORDS:

        if keyword in text:
            hits += 1

    return hits >= 2

def score(section):

    text = (
        section["heading"]
        + "\n"
        + section["text"]
    ).lower()

    matches = []

    for keyword in KEYWORDS:

        if keyword in text:
            matches.append(keyword)

    return matches