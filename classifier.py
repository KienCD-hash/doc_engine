"""
classifier.py - Der lokale Router für doc_engine.
Klassifiziert Rohtext deterministisch in vordefinierte Dokumenttypen.
"""

# Feste Katakorien zur Vermeidung von Tippfehlern ( Magic Strings)
DOC_INVOICE = "INVOICE"
DOC_KNOWLEDGE = "KNOWLEDGE"
DOC_UNKNOWN = "UNKNOWN"


# Eindeutige Signalwörter (in Kleinbuchstaben)
SIGNALS_INVOICE = [
    "rechnung", "rechnungsnummer", "betrag", "mwst", "ust-id",
    "gesamtbetrag", "kassenbon", "tse-transaktion", "zu zahlen",
    "steuernummer", "iban", "fälligkeit", "quittung", "zahlungsbetrag",     "summe",
    "kasse",
    "bon",
    "steuer",
    "brutto",
    "netto",
    "rückgeld",
]

SIGNALS_KNOWLEDGE = [
    "notiz", "notizen", "meeting", "protokoll", "agenda",
    "zusammenfassung", "todo", "aufgaben", "idee", "entwurf",
    "besprechung", "recherche", "konzept", "beobachtung",
    "wissen", "wissenschaft", "analyse", "überlegung", "fazit",
    "dokumentation", "studie", "bericht"
]


def _count_matches(text_lower: str, keywords: list[str]) -> int:
    """Zählt, wie viele Signalwörter im Text vorkommen."""
    return sum(1 for kw in keywords if kw in text_lower)


def classify_document(text: str) -> str:
    """
    Analysiert den Text und gibt die Kategorie mit den meisten Treffern zurück.
    Erfordert mindestens 2 Treffer, um Fehlzuweisungen zu verhindern.
    """
    if not text or not text.strip():
        return DOC_UNKNOWN
    text_lower = text.lower()
    scores = {
        DOC_INVOICE: _count_matches(text_lower, SIGNALS_INVOICE),
        DOC_KNOWLEDGE: _count_matches(text_lower, SIGNALS_KNOWLEDGE),
    }
    best_category, best_score = max(scores.items(), key=lambda item: item[1])

    # Mindestens 2 Treffer nötig für eine sichere Zuweisung
    if best_score >= 2:
        return best_category
    return DOC_UNKNOWN
