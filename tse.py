#!/usr/bin/env python3
"""
tse.py - KassenSichV / BSI TR-03153 Fast-Path via Apple Vision Barcode Detection.
Liest strukturierte Kassendaten (Datum, Bon-Nr, Betrag) direkt digital aus.
"""

from pathlib import Path
import time
from typing import Any, Dict, Optional
from Foundation import NSURL
import pymupdf
import Vision


def parse_tse_payload(payload: str) -> Optional[Dict[str, Any]]:
    """
    Parst die Rohdaten eines KassenSichV-QR-Codes (Standard BSI TR-03153 / DFKA).
    Format: V0;[Kassen-ID];Kassenbeleg-V1;Beleg^[Umsätze]^[Zahlungen];...
    """
    try:
        parts = payload.strip().split(";")
        if len(parts) < 8 or not parts[0].startswith("V0"):
            return None

        # 1. Beleg- / Transaktionsnummer (Feld 5 = Transaktion, Feld 4 = Signaturzähler)
        trans_nr = parts[5].strip() if parts[5].strip() else parts[4].strip()
        if not trans_nr:
            return None

        # 2. Datum aus ISO 8601 Zeitstempel (Feld 6: Startzeit, z.B. 2026-10-30T16:16:21.000Z)
        start_time = parts[6].strip()
        date_iso = start_time[:10]
        if len(date_iso) != 10 or date_iso.count("-") != 2:
            return None

        # 3. Beträge aus ProcessData (Feld 3: Beleg^5.58_17.45_0.00_0.00_0.00^23.03:Unbar)
        process_data = parts[3].strip()
        subparts = process_data.split("^")
        if len(subparts) < 2:
            return None

        # Betrag aus den Steuersätzen aufsummieren
        amounts_str = subparts[1].split("_")
        amounts = [float(a) for a in amounts_str if a]
        sum_from_taxes = round(sum(amounts), 2)

        total_amount = sum_from_taxes

        # Falls Zahlarten-Block vorhanden, Zahlbetrag zur Plausibilitätsprüfung heranziehen
        if len(subparts) >= 3 and ":" in subparts[2]:
            payment_str = subparts[2].split(":")[0].strip()
            try:
                payment_val = round(float(payment_str), 2)
                if payment_val > 0:
                    total_amount = payment_val
            except ValueError:
                pass

        if total_amount <= 0:
            return None

        return {
            "invoice_number": trans_nr,
            "date": date_iso,
            "total_amount": total_amount,
            "status": "Bezahlt",
            "source": "TSE-QR-FASTPATH",
        }

    except Exception:
        return None


def scan_tse(file_path: Path | str) -> Optional[Dict[str, Any]]:
    """
    Sucht mit Apple Vision nach einem TSE-QR-Code im Bild/PDF.
    Gibt bei Fund direkt das Rechnungs-Dictionary zurück, sonst None.
    Laufzeit: typischerweise 1 - 90 ms.
    """
    path = Path(file_path)
    if not path.exists():
        return None

    request = Vision.VNDetectBarcodesRequest.alloc().init()

    # Nur QR-Codes anfordern, um die Erkennung maximal zu beschleunigen
    # (Symbology-Filter)
    request.setSymbologies_([Vision.VNBarcodeSymbologyQR])

    temp_img = None
    if path.suffix.lower() == ".pdf":
        doc = pymupdf.open(path)
        if len(doc) > 0:
            pix = doc[0].get_pixmap(dpi=150)
            temp_img = path.parent / f".temp_qr_{path.stem}.png"
            pix.save(str(temp_img))
            target_path = temp_img
            doc.close()
        else:
            doc.close()
            return None
    else:
        target_path = path

    url = NSURL.fileURLWithPath_(str(target_path.resolve()))
    handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(
        url, None
    )

    success, error = handler.performRequests_error_([request], None)

    if temp_img and temp_img.exists():
        temp_img.unlink()

    if success and request.results():
        for item in request.results():
            payload = item.payloadStringValue()
            if payload and "V0;" in payload:
                facts = parse_tse_payload(payload)
                if facts:
                    return facts

    return None
