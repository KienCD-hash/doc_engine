# doc_engine

A local-first document processing pipeline for German cash register receipts and invoices.

## Background and Motivation

Most cloud-based document parsers rely on large vision-language models (VLMs) or external OCR APIs, introducing latency, recurring token costs, and data privacy concerns under GDPR.

In Germany, the Cash Register Security Ordinance (KassenSichV / BSI TR-03153) mandates that modern electronic cash registers print a QR code with cryptographically signed transaction data. This includes transaction numbers, timestamps, tax rates, and gross totals.

`doc_engine` exploits this standard by implementing a two-stage extraction architecture:
1. Fast-Path (TSE / QR Code): Decodes structured KassenSichV payloads directly via the macOS Vision framework. Processing takes under 5 milliseconds with zero OCR errors.
2. Fallback (Apple Vision OCR): For older receipts or DIN A4 invoices without a QR code, the engine falls back to on-device OCR running on the Apple Neural Engine, followed by a tax-arithmetic parser (validating Netto + MwSt = Brutto).

Documents are classified before parsing. Valid invoices and receipts are written to a local SQLite database and exported to CSV. Research notes are archived as Markdown. Documents with insufficient or illegible text (such as duplex scanner bleed-through pages) are rejected via an explicit abstain pattern to prevent database corruption.

## Fleet Benchmark

Benchmarked on an Apple M1 Mac mini across 50 real-world thermal receipts, folded slips, and invoices:

| Metric | Result |
|---|---|
| Total test documents | 50 |
| Accuracy | 50 / 50 passed (0 failed) |
| Cold run (initial OCR parsing) | 6.76 seconds (~135 ms / doc) |
| Warm run (cached OCR / TSE) | < 1.5 seconds |
| External API calls | 0 |
| Cloud costs | 0.00 EUR |

## Requirements

* macOS 12+ (Apple Silicon recommended for native Vision framework acceleration)
* Python 3.10+

## Setup

git clone https://github.com/KienCD-hash/doc_engine.git
cd doc_engine
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

## Usage

1. Place incoming documents (PDF, PNG, JPG, HEIC) into the inbox/ directory.
2. Run the processing pipeline:
   python main.py
3. Run the regression test suite:
   python test_suite.py

## Repository Structure

* main.py - Orchestration pipeline and archive routing
* tse.py - KassenSichV / BSI TR-03153 barcode detection and payload parser
* extractor.py - Apple Vision OCR and PDF rasterization
* parser.py - Regex parsing and cashier-arithmetic validation
* classifier.py - Document classification and abstain gatekeeper
* database.py - SQLite schema, queries, and CSV exporter
* test_suite.py - Fleet benchmark and regression test runner

## License

MIT License. Copyright (c) 2026 Duc Kien Chu.
