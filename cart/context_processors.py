from .models import Cart


def cart_count(request):
    if request.user.is_authenticated and hasattr(request.user, 'role') and request.user.role in ('customer', 'community', 'restaurant'):
        try:
            return {'cart_count': request.user.cart.item_count}
        except Cart.DoesNotExist:
            return {'cart_count': 0}
    return {'cart_count': 0}


def notification_count(request):
    if request.user.is_authenticated:
        return {'notification_count': request.user.notifications.filter(is_read=False).count()}
    return {'notification_count': 0}
