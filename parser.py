import re
from typing import Optional, Dict, Any


def normalize_amount(raw: str) -> Optional[float]:
    """
    Wandelt Beträge aus Rechnungen robust in float um.
    Beherrscht:
      - Deutsches Format: '1.234,56' -> 1234.56
      - Standard Deutsch: '14,76'    -> 14.76
      - US / Cloud:       '1,234.56' -> 1234.56
      - Einfaches Float:  '14.76'    -> 14.76
    """
    if not raw:
        return None
    s = raw.strip().replace(" ", "")

    # Haben wir sowohl Punkt als auch Komma? (z. B. '1.234,56' oder '1,234.56')
    if "." in s and "," in s:
        # Der letzte Trenner entscheidet!
        if s.rfind(",") > s.rfind("."):
            # Deutsches Format (1.234,56): Punkt weg, Komma zu Punkt
            s = s.replace(".", "").replace(",", ".")
        else:
            # US Format (1,234.56): Komma weg
            s = s.replace(",", "")
    elif "," in s:
        # Nur Komma (z. B. 14,76)
        s = s.replace(",", ".")

    try:
        return float(s)
    except ValueError:
        return None


AMOUNT_PATTERN = r"(?:\d{1,3}(?:[.,]\d{3})+|\d+)[,.]\s*\d{2}(?!\.\d)(?!\s*%)"


def parse_invoice(text: str) -> Optional[Dict[str, Any]]:
    """
    Parst Kernfelder aus einem Rechnungstext.
    Pflichtfelder: Rechnungsnummer, Datum & Betrag.
    """
    # 0. Schutzfilter: Reine Anlagen/Remissionen ohne eigene Gesamtrechnung abweisen
    if re.search(r"Anlage\s+zur\s+Rechnung", text, re.IGNORECASE):
        if not re.search(r"(?:Gesamtbetrag|Endbetrag|Rechnungsbetrag|Zahlbetrag)[\s:•\-\*]*(?:EUR|€)?[\s:•\-\*]*\d+[,.]\d{2}", text, re.IGNORECASE):
            return None

    # 1. Rechnungsnummer ermitteln
    inv_pattern = (
        r"\b(?:Rech(?:nung)?\.?[\-\s]*(?:s?nummer|s?nr\.?)|"
        r"Auft[\s\-]*rag(?:s?nummer|s?[\-\s]*nr\.?)?|"
        r"Transaktion(?:s?nummer|s?[\-\s]*nr\.?)?|"
        r"TA\b[\-\s]*(?:nummer|nr\.?)?|"
        r"Genehmigung(?:s?nummer|s?[\-\s]*nr\.?)?|"
        r"Trace[\-\s]*(?:nummer|nr\.?)?|"
        r"Bele[gs][\-\s]*(?:s?nummer|s?nr\.?)?|"
        r"Buchung[\-\s]*(?:s?code|s?nummer|s?nr\.?)?|"
        r"(?:Kassen[\-\s]*)?bo[rn][\-\s]*(?:s?nummer|s?nr\.?)?|"
        r"BNr|"
        r"TSE[\-\s]*(?:Transaktion|Transaktionsnummer))"
        r"[\s.:#-]*\n*(?:[^\d\n]+\n*)*?([A-Za-z0-9\-]*\d+[A-Za-z0-9\-]*)"
    )

    invoice_number = None

    # Spezialfall: 3-Spalten-Kassenkopf (z. B. EDEKA "Pos Bed Bon \n 105 105 9577") -> 3. Wert ist die Bon-Nummer!
    pos_bed_bon = re.search(
        r"\b(?:Pos|Kasse)\s+Bed(?:iener)?\s+Bon\s*\n\s*\d+\s+\d+\s+(\d+)",
        text,
        re.IGNORECASE,
    )
    # Spezialfall: Buchungscode für Tickets (z. B. Stern und Kreisschiffahrt)
    buchung_match = re.search(
        r"\bBuchungs(?:code|nummer|nr)[\s.:#-]*([A-Za-z0-9]{5,})", text, re.IGNORECASE)
    if buchung_match:
        invoice_number = buchung_match.group(1)
    if pos_bed_bon:
        invoice_number = pos_bed_bon.group(1)

    if not invoice_number:
        for m in re.finditer(inv_pattern, text, re.IGNORECASE):
            candidate = m.group(1).strip()

            # Schutzfilter A: Folgt direkt ein Komma (z. B. "11, 34"), ist es ein Preis!
            rest_after = text[m.end():m.end() + 10]
            if re.match(r"\s*[,.]\s*\d{1,2}", rest_after):
                continue
            # Schutzfilter B: Einzelne Ziffern (z. B. "6") sind Zeilenumbruch-Reste, keine Belegnummern
            if len(candidate) < 3 and candidate.isdigit():
                continue
            invoice_number = candidate
            break

    if not invoice_number:
        # Fallback für Büro-Rechnungen
        inv_match = re.search(
            r"\b(?:Rechnung|RECHNUNG)\b[\s\S]{0,100}?\bNummer[\s.:#-]+(?:\n[^\d\n]+:\s*)*\n?([A-Za-z0-9\-]*\d+[A-Za-z0-9\-]*)",
            text,
            re.IGNORECASE,
        )
        if inv_match:
            candidate = inv_match.group(1).strip()
            if len(candidate) >= 3 or not candidate.isdigit():
                invoice_number = candidate

    if not invoice_number:
        return None

    # 2. Datum ermitteln: Zuerst 4-stelliges Jahr (20xx), um Verwechslungen mit Uhrzeiten (12:51) auszuschließen
    date_match = re.search(
        r"\b(0?[1-9]|[12]\d|3[01])\.\s*(0?[1-9]|1[0-2])\s*\.?\s*(20\d{2}|19\d{2})", text
    )
    if date_match:
        day = date_match.group(1).zfill(2)
        month = date_match.group(2).zfill(2)
        year = date_match.group(3)
        iso_date = f"{year}-{month}-{day}"
    else:
        # Fallback: 2-stelliges Jahr (aber nicht direkt von ':' gefolgt, um Uhrzeiten zu ignorieren)
        date_match = re.search(
            r"\b(0?[1-9]|[12]\d|3[01])\.\s*(0?[1-9]|1[0-2])\s*\.?\s*(\d{2}(?!:))", text
        )
        if date_match:
            day = date_match.group(1).zfill(2)
            month = date_match.group(2).zfill(2)
            year = f"20{date_match.group(3)}"
            iso_date = f"{year}-{month}-{day}"
        else:
            # Rettungsanker: Datum aus dem TSE-Block (z. B. 2026-09-12)
            tse_date_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
            if tse_date_match:
                iso_date = f"{tse_date_match.group(1)}-{tse_date_match.group(2)}-{tse_date_match.group(3)}"
            else:
                iso_date = None

    if not iso_date:
        return None

        # 3. Gesamtbetrag ermitteln
    total_amount = None

    # A) Höchste Priorität: Expliziter Zahlbetrag des Kunden ("zu zahlen: 5,93", "Zahlung erfolgt: 11,94")
    zu_zahlen_match = re.search(
        rf"(?:zu\s*zahlen|Zahlbetrag|Endbetrag|Zahlung\s+erfolgt)[\s:•\-\*]*(?:EUR|€)?[\s:•\-\*]*\n*(?:[^\d\n]+\n)?\s*(?:EUR|€)?[\s:•\-\*]*({AMOUNT_PATTERN})",
        text,
        re.IGNORECASE,
    )
    if zu_zahlen_match:
        total_amount = normalize_amount(zu_zahlen_match.group(1))

    # B) Kartenzahlungs-Beleg (immer den höchsten EUR-Betrag im Kartenbereich nehmen)
    if not total_amount:
        card_block = re.search(
            r"(?:Kartenzahlung|girocard|gi\s*rocard|MasterCard|Visa)[\s\S]{0,500}?(?:Zahlung\s+erfolgt|Kundenbeleg|$)",
            text,
            re.IGNORECASE
        )
        if card_block:
            card_vals = [
                normalize_amount(val)
                for val in re.findall(rf"(?:EUR|€)\s*({AMOUNT_PATTERN})", card_block.group(0))
            ]
            valid_card_vals = [v for v in card_vals if v is not None]
            if valid_card_vals:
                total_amount = max(valid_card_vals)

    # C) BackWerk-Muster: 'Total' für Barzahler ohne nachfolgendes Kartenterminal
    if not total_amount:
        total_match = re.search(
            rf"\bTotal\b[\s:•\-\*]*(?:[^\d\n]+\n)?\s*(?:EUR|€)?[\s:•\-\*]*({AMOUNT_PATTERN})",
            text,
            re.IGNORECASE,
        )
        if total_match:
            total_amount = normalize_amount(total_match.group(1))

    # D) Steuertabelle mit 2 Brutto-Teilbeträgen (z. B. 19% + 7% bei Kaufland & Netto)
    if not total_amount:
        brutto_table = re.search(
            rf"\bBRUTTO\b[\s:•\-\*]*\n*({AMOUNT_PATTERN})\s*\n*({AMOUNT_PATTERN})", text, re.IGNORECASE
        )
        if brutto_table:
            val1 = normalize_amount(brutto_table.group(1))
            val2 = normalize_amount(brutto_table.group(2))
            if val1 is not None and val2 is not None:
                total_amount = round(val1 + val2, 2)

    # D2) Barzahlungs-Trio (Summe, Bar gegeben, Rückgeld: 50.00 - 32.50 = 17.50)
    if not total_amount:
        pattern_trio = rf"(?:EUR|€)?\s*({AMOUNT_PATTERN})\s*\n*(?:EUR|€)?\s*-?\s*({AMOUNT_PATTERN})\s*\n*(?:EUR|€)?\s*({AMOUNT_PATTERN})"
        for m in re.finditer(pattern_trio, text):
            v1 = normalize_amount(m.group(1))
            v2 = normalize_amount(m.group(2))
            v3 = normalize_amount(m.group(3))
            if v1 and v2 and v3 and round(v2 - v3, 2) == v1 and v1 > 0:
                total_amount = v1
                break

    # E) Mehrspalten-Block (Brutto, Gesamt, Summe, Betrag)
    if not total_amount:
        candidates = []
        pattern_multi = (
            r"(?:\b(?:Total|Gesamt(?:betrag|summe)?|Endbetrag|Rechnungsbetrag|Zahlbetrag|Brutto(?:betrag)?|zu\s*zahlen|girocard|Kartenzahlung)\b|Summe(?!\s*(?:mwst|netto|steuer))|Betrag)"
            r"(?!\s*(?:mwst|netto|steuer|rabatt|gespart|preisvorteil|ersparnis))"
            r"[\s:•\-\*]*(?:EUR|€)?[\s:•\-\*]*\n*(?:[^\n]+\n){0,3}?\s*"
            r"((?:(?:EUR|€)?[\s:•\-\*]*" +
            AMOUNT_PATTERN + r"[A-Za-z]?\s*\n*)+)"
        )
        for m in re.finditer(pattern_multi, text, re.IGNORECASE):
            raw_vals = [normalize_amount(val) for val in re.findall(
                AMOUNT_PATTERN, m.group(1))]
            raw_vals = [v for v in raw_vals if v is not None]
            if not raw_vals:
                continue
            if re.search(r"\b(?:BAR|Bar|Gegeben|Rückgabe|Rückgeld)\b", m.group(0)):
                candidates.append(raw_vals[0])
            else:
                candidates.extend(raw_vals)

        if candidates:
            total_amount = max(candidates)
    # F) Fallback Einzelzeile
    if not total_amount:
        pattern_single = (
            r"(?:\b(?:Total|Gesamt(?:betrag|summe)?|Endbetrag|Rechnungsbetrag|Zahlbetrag|Brutto(?:betrag)?|zu\s*zahlen|girocard|Kartenzahlung)\b|Summe(?!\s*(?:mwst|netto|steuer))|Betrag)"
            r"(?!\s*(?:mwst|netto|steuer|rabatt|gespart|preisvorteil|ersparnis))"
            r"[\s:•\-\*]*(?:[^\n]+\n){0,3}?\s*(?:EUR|€)?[\s:•\-\*]*(" +
            AMOUNT_PATTERN + r")"
        )
        for m in re.finditer(pattern_single, text, re.IGNORECASE):
            val = normalize_amount(m.group(1))
            if val is not None:
                candidates.append(val)
        if candidates:
            total_amount = max(candidates)
    if not total_amount:
        return None

    # 4. Status ermitteln
    status_match = re.search(r"Status:\s*([A-Za-z]+)", text, re.IGNORECASE)
    if status_match:
        status = status_match.group(1).capitalize()
    elif re.search(r"(?:zahlbar\s+bis|fällig|überweisen|bitte\s+überweisen)", text, re.IGNORECASE):
        status = "Offen"
    else:
        status = "Bezahlt"

    return {
        "invoice_number": invoice_number,
        "date": iso_date,
        "total_amount": total_amount,
        "status": status
    }
