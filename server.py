"""AuditReady: a dependency-free, synthetic audit evidence prototype."""
import csv
import io
import json
import re
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).parent
LEDGER = [
    dict(id='TX-101', vendor='Acme Cloud', date='2026-07-12', amount=12400),
    dict(id='TX-102', vendor='Northstar Analytics', date='2026-07-23', amount=18750),
    dict(id='TX-103', vendor='Atlas Design', date='2026-08-05', amount=11200),
    dict(id='TX-104', vendor='Beacon Security', date='2026-08-19', amount=24000),
    dict(id='TX-105', vendor='Acme Cloud', date='2026-09-12', amount=12400),
    dict(id='TX-106', vendor='Summit Consulting', date='2026-09-25', amount=16000),
    dict(id='TX-107', vendor='Office Supply Co', date='2026-09-28', amount=850),
]
DOCS = [
    dict(id=f'DOC-{i+1:03}', name=name, type='invoice', transaction_id=tx['id'],
         text=f"INVOICE — {tx['vendor']}\nTransaction reference: {tx['id']}\nInvoice date: {tx['date']}\nTotal: ${tx['amount']:,.2f}\nStatus: final")
    for i, (tx, name) in enumerate(zip(LEDGER[:5], ['invoice_final.txt', 'NS_july_invoice.txt', 'atlas_invoice_v2.txt', 'invoice_final_2.txt', 'acme_sept.txt']))
] + [
    dict(id='DOC-006', name='bank_sep_2026.txt', type='bank_statement', period='2026-09', text='BANK STATEMENT — DEMO OPERATING ACCOUNT\nPeriod: September 1–30, 2026\nOpening balance: $245,000.00\nClosing balance: $198,450.00\nAccount ending: 0042'),
    dict(id='DOC-007', name='reconciliation_september_DRAFT.txt', type='reconciliation', period='2026-09', text='SEPTEMBER BANK RECONCILIATION — DRAFT\nStatement ending balance: $198,450.00\nLedger balance: $200,000.00\nUnresolved difference: $1,550.00\nReviewer sign-off: MISSING'),
    dict(id='DOC-008', name='northstar_old_quote.txt', type='quote', text='QUOTE — Northstar Analytics\nDate: 2026-06-01\nProposed total: $18,750.00\nNot an invoice; not proof of a completed transaction.'),
]
REQUESTS = [
    dict(id='PBC-01', request='All invoices over $10,000 from Q3 2026', owner='Accounts payable (demo rule)'),
    dict(id='PBC-02', request='September 2026 operating bank statement', owner='Treasury (demo rule)'),
    dict(id='PBC-03', request='September 2026 bank reconciliation with reviewer sign-off', owner='Controller (demo rule)'),
    dict(id='PBC-04', request='October 2026 operating bank statement', owner='Treasury (demo rule)'),
]


def analyze(rows):
    results = []
    for row in rows:
        lower = row['request'].lower()
        item = dict(**row, status='needs_review', evidence=[], missing=[], population=None, explanation='')
        threshold = re.search(r'(?:over|above|greater than)\s*\$?([\d,]+(?:\.\d+)?)\s*(k)?\b', lower)
        if 'invoice' in lower and re.search(r'\bq3\s+2026\b', lower) and threshold:
            amount = float(threshold[1].replace(',', '')) * (1000 if threshold[2] else 1)
            population = [t for t in LEDGER if '2026-07-01' <= t['date'] <= '2026-09-30' and t['amount'] > amount]
            item['population'] = dict(total=len(population), matched=0, basis=f'Synthetic ledger · Q3 2026 · amount strictly greater than ${amount:,.2f}')
            for tx in population:
                docs = [d for d in DOCS if d['type'] == 'invoice' and d.get('transaction_id') == tx['id']]
                if len(docs) == 1:
                    item['evidence'].append(dict(document_id=docs[0]['id'], reason=f"Exact transaction reference {tx['id']} · ${tx['amount']:,.2f}", highlight=tx['id']))
                    item['population']['matched'] += 1
                else:
                    item['missing'].append(f"{tx['id']} · {tx['vendor']} · ${tx['amount']:,.2f} · {tx['date']}: supporting invoice missing or ambiguous")
            item['status'] = 'missing' if item['missing'] else ('ready' if population else 'needs_review')
            item['explanation'] = f"{item['population']['matched']} of {len(population)} qualifying transactions have an invoice. Coverage is limited to the supplied synthetic ledger."
        elif 'bank' in lower and ('statement' in lower or 'reconciliation' in lower) and re.search(r'\b(september|october)\s+2026\b', lower):
            period = '2026-09' if 'september' in lower else '2026-10'
            kind = 'reconciliation' if 'reconciliation' in lower else 'bank_statement'
            docs = [d for d in DOCS if d['type'] == kind and d.get('period') == period]
            item['evidence'] = [dict(document_id=d['id'], reason=f'Exact document type and period: {period}', highlight='MISSING' if kind == 'reconciliation' else 'September 1–30, 2026') for d in docs]
            if not docs:
                item['status'] = 'missing'
                item['missing'] = [f'No {kind.replace("_", " ")} found for {period}. Request it from the listed owner.']
                item['explanation'] = 'No matching document in the supplied corpus. It may exist elsewhere.'
            elif kind == 'reconciliation':
                item['missing'] = ['Reviewer sign-off is missing.', 'Unresolved $1,550 difference needs an explanation and corrected support.']
                item['explanation'] = 'A draft exists, but its unresolved difference and missing sign-off prevent readiness.'
            else:
                item['status'] = 'ready'
                item['explanation'] = 'Statement matches the requested period. A reviewer must verify authenticity and account scope.'
        else:
            item['explanation'] = 'Outside the supported demo rules. A reviewer must clarify scope; no match has been inferred.'
            item['missing'] = ['Manual scoping required. Supported: Q3 2026 invoices over an amount; September/October 2026 bank statements or reconciliations.']
        results.append(item)
    return results


def parse_csv(raw):
    reader = csv.DictReader(io.StringIO(raw.lstrip('\ufeff')))
    if not reader.fieldnames or 'request' not in reader.fieldnames:
        raise ValueError('CSV needs a request column. Optional columns: id, owner.')
    rows = []
    for index, row in enumerate(reader):
        if index >= 100:
            raise ValueError('Maximum 100 requests per upload.')
        if not row.get('request', '').strip():
            raise ValueError(f'Row {index + 2} has an empty request.')
        rows.append(dict(id=(row.get('id') or '').strip() or f'PBC-{index+1:02}', request=row['request'].strip()[:2000], owner=(row.get('owner') or '').strip() or 'Unassigned — reviewer to identify owner'))
    if not rows or len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Include at least one request and use unique request IDs.')
    return rows


def make_export(rows, approvals):
    output, index = io.BytesIO(), io.StringIO()
    writer = csv.writer(index)
    writer.writerow(['Request ID', 'Request', 'Evidence status', 'Reviewer approval', 'Owner', 'Evidence files', 'Unresolved items'])
    manifest = []
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for n, item in enumerate(analyze(rows), 1):
            approved = item['status'] == 'ready' and approvals.get(item['id']) is True
            files = []
            for evidence in item['evidence']:
                doc = next(d for d in DOCS if d['id'] == evidence['document_id'])
                path = f"requests/{n:03}/{doc['id']}_{doc['name']}"
                archive.writestr(path, doc['text'])
                files.append(path)
            # Prefix spreadsheet formula characters in user-controlled CSV cells.
            cells = [item['id'], item['request'], item['status'], 'approved in demo' if approved else 'not approved', item['owner'], '; '.join(files), '; '.join(item['missing'])]
            writer.writerow(["'" + str(c) if str(c).lstrip().startswith(('=', '+', '-', '@')) else c for c in cells])
            manifest.append(dict(**item, approved=approved))
        archive.writestr('index.csv', index.getvalue())
        archive.writestr('manifest.json', json.dumps(manifest, indent=2))
        archive.writestr('README.txt', 'AUDITREADY — SYNTHETIC DEMO ONLY\nAll requests, including unresolved items, appear in index.csv.\nMatching uses explicit rules, not AI. Coverage is limited to the synthetic ledger.\nApprovals are demo acknowledgments, not authenticated audit records.\nNot an audit opinion or a guarantee of completeness.\n')
    return output.getvalue()


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, data, mime, download=None):
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        if download:
            self.send_header('Content-Disposition', f'attachment; filename="{download}"')
        self.end_headers()
        self.wfile.write(data)

    def json_response(self, status, data):
        self.respond(status, json.dumps(data).encode(), 'application/json')

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/demo':
            self.json_response(200, dict(requests=REQUESTS, results=analyze(REQUESTS), documents=DOCS, ledger=LEDGER))
        elif path in ('/', '/app.js', '/style.css'):
            filename, mime = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript'), '/style.css': ('style.css', 'text/css')}[path]
            self.respond(200, (ROOT / 'static' / filename).read_bytes(), mime)
        else:
            self.json_response(404, dict(error='Not found'))

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 1_000_000:
                raise ValueError('Body must be between 1 byte and 1 MB.')
            payload = json.loads(self.rfile.read(length))
            rows = parse_csv(payload['csv'])
            path = urlsplit(self.path).path
            if path == '/api/analyze':
                self.json_response(200, dict(requests=rows, results=analyze(rows)))
            elif path == '/api/export':
                approvals = payload.get('approvals', {})
                if not isinstance(approvals, dict):
                    raise ValueError('Invalid approval format.')
                self.respond(200, make_export(rows, approvals), 'application/zip', 'auditready-evidence.zip')
            else:
                self.json_response(404, dict(error='Not found'))
        except (ValueError, KeyError, TypeError, AttributeError, csv.Error) as error:
            self.json_response(400, dict(error=str(error)))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--host', default='127.0.0.1')
    args = parser.parse_args()
    print(f'AuditReady running on {args.host}:{args.port}', flush=True)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
