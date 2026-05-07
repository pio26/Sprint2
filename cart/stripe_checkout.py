from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.urls import reverse

try:
    import stripe
except ImportError:
    stripe = None


class StripeCheckoutError(Exception):
    pass


def stripe_checkout_is_configured():
    return bool(settings.STRIPE_SECRET_KEY) and stripe is not None


def amount_to_minor_units(amount):
    return int((Decimal(amount) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def build_line_items(cart_items):
    line_items = []
    for item in cart_items:
        line_items.append({
            'price_data': {
                'currency': settings.STRIPE_CURRENCY,
                'product_data': {
                    'name': item.product.name,
                },
                'unit_amount': amount_to_minor_units(item.product.effective_price),
            },
            'quantity': item.quantity,
        })
    return line_items


def create_checkout_session(request, order, cart_items):
    if stripe is None:
        raise StripeCheckoutError('The stripe package is not installed.')
    if not settings.STRIPE_SECRET_KEY:
        raise StripeCheckoutError('STRIPE_SECRET_KEY is not configured.')

    stripe.api_key = settings.STRIPE_SECRET_KEY
    success_url = request.build_absolute_uri(
        reverse('cart:order_confirmation', args=[order.pk])
    )
    cancel_url = request.build_absolute_uri(reverse('cart:checkout'))

    try:
        return stripe.checkout.Session.create(
            mode='payment',
            line_items=build_line_items(cart_items),
            customer_email=request.user.email or None,
            client_reference_id=str(order.pk),
            metadata={
                'order_id': str(order.pk),
                'order_number': order.order_number,
            },
            success_url=f'{success_url}?session_id={{CHECKOUT_SESSION_ID}}',
            cancel_url=cancel_url,
        )
    except stripe.error.StripeError as exc:
        raise StripeCheckoutError(str(exc)) from exc


def construct_webhook_event(payload, signature):
    if stripe is None:
        raise StripeCheckoutError('The stripe package is not installed.')
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise StripeCheckoutError('STRIPE_WEBHOOK_SECRET is not configured.')

    return stripe.Webhook.construct_event(
        payload,
        signature,
        settings.STRIPE_WEBHOOK_SECRET,
    )
