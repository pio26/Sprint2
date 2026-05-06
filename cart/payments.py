import json
import urllib.error
import urllib.request
from decimal import Decimal

from django.conf import settings


def process_payment(amount, reference='', method='mock_card'):
    payload = {
        'amount': str(Decimal(amount).quantize(Decimal('0.01'))),
        'reference': reference,
        'method': method,
    }

    if settings.PAYMENT_SERVICE_URL:
        request = urllib.request.Request(
            f'{settings.PAYMENT_SERVICE_URL.rstrip("/")}/charge/',
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                if data.get('status') == 'completed':
                    return data.get('transaction_id', reference), 'completed'
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            pass

    return reference, 'completed' if method == 'mock_card' else 'pending'
