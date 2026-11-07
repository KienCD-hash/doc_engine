
import shutil
from tse import scan_tse
from datetime import datetime
from pathlib import Path
from extractor import extract_text
from parser import parse_invoice
from database import init_db, save_invoice, get_invoices_summary, export_invoices_to_csv
from classifier import classify_document, DOC_INVOICE, DOC_KNOWLEDGE, DOC_UNKNOWN


# Ziel-Ordner für das Archiv
ARCHIV_RECHNUNGEN = Path("archiv/rechnungen")
ARCHIV_DUPLIKATE = Path("archiv/duplikate")
ARCHIV_WISSEN = Path("archiv/wissen")
ARCHIV_ABGEWIESEN = Path("archiv/abgewiesen")


def process_document(file_path: str):
    print(f"=== Verarbeitete Datei: {file_path} ===")
    """
    Zweistufige Rakete:
    Stufe 1: TSE-QR-Code Fast-Path (KassenSichV)
    Stufe 2: Fallback via Apple Vision OCR & Text-Klassifizierung
    """
    # ---------------------------------------------------------
    # STUFE 1: Fast-Path via TSE-QR-Code
    # ---------------------------------------------------------
    tse_facts = scan_tse(file_path)
    if tse_facts:
        print(
            f"-> FAST-PATH: TSE-QR-Code erkannt (Bon-Nr: {tse_facts['invoice_number']}, {tse_facts['total_amount']} EUR)"
        )
        neu_gespeichert = save_invoice(
            tse_facts, raw_text=f"TSE-PAYLOAD: {tse_facts}"
        )
        if neu_gespeichert:
            print(
                f"-> ERFOLG: Rechnung {tse_facts['invoice_number']} ({tse_facts['total_amount']} EUR) verbucht."
            )
            return "SAVED"
        else:
            print(
                f"-> DUPLIKAT: Rechnung {tse_facts['invoice_number']} bereits in Datenbank."
            )
            return "DUPLICATE"

    # ---------------------------------------------------------
    # STUFE 2: Fallback (Bestehende OCR-Pipeline)
    # ---------------------------------------------------------
    # 1. Modul 1: Text extrahieren
    raw_text = extract_text(file_path)

    # 2. Dokumenttyp ermitteln
    doc_type = classify_document(raw_text)
    print(f"-> Klassifizierung: {doc_type}")

    # 3. Fachabteilung ansteuern
    if doc_type == DOC_INVOICE:
        facts = parse_invoice(raw_text)
        if facts:
            neu_gespeichert = save_invoice(facts, raw_text=raw_text)
            if neu_gespeichert:
                print(
                    f"-> ERFOLG: Rechnung {facts['invoice_number']} ({facts['total_amount']} EUR) verbucht."
                )
                return "SAVED"
            else:
                print(
                    f"-> DUPLIKAT: Rechnung {facts['invoice_number']} bereits in Datenbank."
                )
                return "DUPLICATE"
        else:
            print("-> ABSTAIN: Pflichtfelder fehlen oder fehlerhaft!")
            return "ABSTAIN"
    elif doc_type == DOC_KNOWLEDGE:
        print("-> WISSEN: Notiz / Dokument erkannt.")

        # Markdown-Datei mit modernem pathlib im Wissensarchiv anlegen
        p = Path(file_path)
        md_path = ARCHIV_WISSEN / f"{p.stem}.md"

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# Notiz / Dokument: {p.name}\n\n")
            f.write(f"- **Quelldatei:** `{p.name}`\n")
            f.write(
                f"- **Erfasst am:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            )
            f.write("---\n\n")
            f.write(raw_text.strip())
            f.write("\n")

        print(f"   -> Markdown-Text erzeugt: {md_path}")
        return "KNOWLEDGE"
    else:
        print("-> ABSTAIN: Dokumenttyp unklar oder zu wenig Text.")
        return "ABSTAIN"


def process_inbox(folder_path: str = "inbox"):
    """
    Durchsucht den Eingangsordner und verarbeitet alle Belege im Stapel.
    """
    inbox = Path(folder_path)
    if not inbox.exists():
        print(f"Ordner {folder_path} existiert nicht!")
        return

    # Statistik für den aktuellen Durchlauf
    stats = {"SAVED": 0, "DUPLICATE": 0, "KNOWLEDGE": 0, "ABSTAIN": 0}
    # Alle Dateien in der Inbox verarbeiten
    for file_path in sorted(inbox.iterdir()):
        if not file_path.is_file() or file_path.name.startswith("."):
            continue
        try:
            result = process_document(str(file_path))
        except Exception as e:
            print(f"-> KRITISCHER FEHLER bei {file_path.name}: {e}")
            # Kaputte Datei isolieren, damit die Inbox nicht blockiert wird:
            shutil.move(str(file_path), ARCHIV_ABGEWIESEN / file_path.name)
            stats["ABSTAIN"] += 1
            continue
        stats[result] += 1
        # Ziel-Aktion anhand des Ergebnisses ausführen
        if result == "KNOWLEDGE":
            # Originalfoto nach erfolgreicher Digitalisierung restlos entfernen
            file_path.unlink()
            print("    -> Originalfoto gelöscht (Digitaler Text liegt als .md im Archiv)")
        else:
            if result == "SAVED":
                target_dir = ARCHIV_RECHNUNGEN
            elif result == "DUPLICATE":
                target_dir = ARCHIV_DUPLIKATE
            else:  # ABSTAIN
                target_dir = ARCHIV_ABGEWIESEN

            # Ordner automatisch anlegen, falls noch nicht vorhanden
            target_dir.mkdir(parents=True, exist_ok=True)
            # Datei physisch verschieben
            shutil.move(str(file_path), target_dir / file_path.name)
            print(f"    -> Archiviert nach: {target_dir / file_path.name}")
    # Abschlussbericht
    print("\n" + "=" * 45)
    print("           STAPELLAUF-ABSCHLUSSBERICHT       ")
    print("=" * 45)
    print(f"Neu gebucht (Rechnungen): {stats['SAVED']}")
    print(f"Wissen archiviert       : {stats['KNOWLEDGE']}")
    print(f"Duplikate ignoriert     : {stats['DUPLICATE']}")
    print(f"Abgewiesen (Abstain)    : {stats['ABSTAIN']}")
    # Gesamt-Stand aus der SQL-Datenbank
    print("-" * 45)
    db_stats = get_invoices_summary()
    print(
        f"Gesamtbestand in SQL: {db_stats['anzahl_rechnungen']} Rechnungen ({db_stats['gesamtsumme_euro']} EUR)")
    print("=" * 45)


if __name__ == "__main__":
    init_db()
    process_inbox("inbox")
    export_invoices_to_csv()
