import sqlite3
import csv
from typing import Dict, Any, Optional

DB_FILE = "doc_engine.db"


def get_connection() -> sqlite3.Connection:
    """Erstellt eine Verbindung zur lokalen SQLite-Datenbankdatei."""
    return sqlite3.connect(DB_FILE)


def init_db():
    """Erstellt die Tabelle 'invoices'. falls sie noch nicht existieren."""
    conn = get_connection()
    cursor = conn.cursor()

    # Reines, standardisiertes SQL
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT UNIQUE NOT NULL,
            invoice_date TEXT,
            total_amount REAL NOT NULL,
            status TEXT DEFAULT 'Unbekannt',
            raw_text TEXT
        )
    """)

    conn.commit()
    conn.close()
    print("Datenbank und Tabelle 'invoices' erfolgreich initialisiert!")


def save_invoice(data: Dict[str, Any], raw_text: Optional[str] = None) -> bool:
    """
    Speichert ein geparstes Rechnungs-Dictionary in der SQL-Datenbank.
    Verhindert Duplikate über 'INSERT OR IGNORE'.
    Gibt True zurück, wenn neu gespeichert, False bei Duplikat.
    """
    query = """
        INSERT OR IGNORE INTO invoices (invoice_number, invoice_date, total_amount, status, raw_text)
        VALUES (?, ?, ?, ?, ?)
    """

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (
            data["invoice_number"],
            data.get("date"),
            data["total_amount"],
            data.get("status", "Bezahlt"),
            raw_text or data.get("raw_text")
        ))
        rows_affected = cursor.rowcount

    return rows_affected > 0


def get_invoices_summary() -> Dict[str, Any]:
    """
    Berechnet Gesamtzahlen direkt in der SQL-Datenbank:
    Anzahl aller Rechnungen und Gesamtsumme aller Beträge.
    """
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT 
            COUNT(*) AS total_count,
            ROUND(SUM(total_amount), 2) AS total_sum
        FROM invoices
    """

    cursor.execute(query)
    row = cursor.fetchone()
    conn.close()

    total_sum = round(row[1], 2) if row[1] is not None else 0.0

    return {
        "anzahl_rechnungen": row[0] or 0,
        "gesamtsumme_euro": total_sum
    }


def get_open_invoices_count() -> Dict[str, Any]:
    """
    Zähle die offnen Rechungen in der SQL Datenbank
    """

    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT
            COUNT(*) 
            FROM invoices
            WHERE status = 'Offen'
    """

    cursor.execute(query)        # Den Zettel an die Datenbank schicken
    row = cursor.fetchone()      # Die Antwort in 'row' auffangen
    conn.close()

    return row[0] or 0


def export_invoices_to_csv(output_file: str = "invoices_export.csv"):
    """Exportiert alle Rechnungen aus der SQLite-Datenbank in eine CSV-Datei."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, invoice_number, invoice_date, total_amount, status FROM invoices")
    rows = cursor.fetchall()

    with open(output_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(
            ["ID", "Rechnungsnummer", "Datum", "Betrag_EUR", "Status"])
        writer.writerows(rows)

    conn.close()
    print(
        f"Erfolgreich {len(rows)} Rechnungen nach '{output_file}' exportiert!")


if __name__ == "__main__":
    init_db()

    # Ein Test-Datensatz, genau wie ihn parser.py liefert
    test_data = {
        "invoice_number": "RE-2024-0042",
        "date": "2024-03-15",
        "total_amount": 119.0,
        "status": "Offen"
    }
    # 1. Durchlauf: Muss True sein (wird neu eingetragen)
    erster_versuch = save_invoice(test_data)
    print("1. Versuch (Neu eingetragen?):", erster_versuch)

    # 2. Durchlauf mit denselben Daten: Muss False sein (Duplikat abgewehrt!)
    zweiter_versuch = save_invoice(test_data)
    print("2. Versuch (Als Duplikat erkannt?):", not zweiter_versuch)

    # 3. SQL-Statistik abfragen
    summary = get_invoices_summary()
    print("3. SQL-Statistik:", summary)

    # 4. Selbst geschriebene Abfrage testen
    offene = get_open_invoices_count()
    print("4. Offene Rechnungen:", offene)

    # 5. CSV-Export testen
    export_invoices_to_csv()
