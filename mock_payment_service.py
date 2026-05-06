from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import uuid


class MockPaymentHandler(BaseHTTPRequestHandler):
    def _send_json(self, status, payload):
        body = json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/health/':
            self._send_json(200, {'status': 'ok', 'service': 'mock-payment'})
        else:
            self._send_json(404, {'error': 'not_found'})

    def do_POST(self):
        if self.path != '/charge/':
            self._send_json(404, {'error': 'not_found'})
            return

        length = int(self.headers.get('Content-Length', '0'))
        raw = self.rfile.read(length) if length else b'{}'
        try:
            payload = json.loads(raw.decode('utf-8'))
        except json.JSONDecodeError:
            payload = {}

        self._send_json(200, {
            'status': 'completed',
            'transaction_id': payload.get('reference') or f'MOCK-{uuid.uuid4().hex[:12].upper()}',
            'amount': payload.get('amount', '0.00'),
            'method': payload.get('method', 'mock_card'),
        })

    def log_message(self, format, *args):
        return


if __name__ == '__main__':
    HTTPServer(('0.0.0.0', 9000), MockPaymentHandler).serve_forever()
