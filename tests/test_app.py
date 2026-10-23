import io
import json
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from http.server import ThreadingHTTPServer
from server import Handler, REQUESTS, analyze, make_export, parse_csv


class EvidenceTests(unittest.TestCase):
    def test_missing_invoice_population_and_quote_excluded(self):
        result = analyze(REQUESTS)[0]
        self.assertEqual(result['population']['total'], 6)
        self.assertEqual(result['population']['matched'], 5)
        self.assertEqual(result['status'], 'missing')
        self.assertIn('TX-106', result['missing'][0])
        self.assertNotIn('DOC-008', [e['document_id'] for e in result['evidence']])

    def test_reconciliation_is_not_ready_and_statement_is(self):
        results = analyze(REQUESTS)
        self.assertEqual([r['status'] for r in results], ['missing', 'ready', 'needs_review', 'missing'])
        self.assertIn('$1,550', results[2]['missing'][1])

    def test_threshold_and_unknown_request(self):
        rows = parse_csv('request\nAll invoices over $20k from Q3 2026\nFind everything from last year\n')
        results = analyze(rows)
        self.assertEqual(results[0]['population']['total'], 1)
        self.assertEqual(results[1]['status'], 'needs_review')
        self.assertEqual(results[1]['evidence'], [])

    def test_invalid_csv(self):
        for text in ['foo\nbar', 'request\n', 'id,request\na,one\na,two', 'request\n""']:
            with self.assertRaises(ValueError):
                parse_csv(text)

    def test_export_preserves_gaps_and_blocks_false_approval(self):
        with zipfile.ZipFile(io.BytesIO(make_export(REQUESTS, {r['id']: True for r in REQUESTS}))) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            self.assertEqual([r['approved'] for r in manifest], [False, True, False, False])
            self.assertIn('Summit Consulting', archive.read('index.csv').decode())
            self.assertEqual(len([p for p in archive.namelist() if p.startswith('requests/')]), 7)


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_functional_api_and_export(self):
        with urllib.request.urlopen(self.base + '/api/demo') as response:
            data = json.load(response)
        self.assertEqual(len(data['results']), 4)
        payload = json.dumps({'csv': 'request\nSeptember 2026 operating bank statement', 'approvals': {'PBC-01': True}}).encode()
        for path in ['/api/analyze', '/api/export']:
            request = urllib.request.Request(self.base + path, data=payload, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(request) as response:
                body = response.read()
                if path.endswith('export'):
                    with zipfile.ZipFile(io.BytesIO(body)) as archive:
                        self.assertTrue(json.loads(archive.read('manifest.json'))[0]['approved'])
                else:
                    self.assertEqual(json.loads(body)['results'][0]['status'], 'ready')

    def test_bad_request_and_static_page(self):
        with urllib.request.urlopen(self.base) as response:
            self.assertIn(b'AuditReady', response.read())
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(urllib.request.Request(self.base + '/api/analyze', data=b'{"csv":"bad"}'))
        self.assertEqual(error.exception.code, 400)


if __name__ == '__main__':
    unittest.main()
