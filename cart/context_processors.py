from .models import Cart


def cart_count(request):
    if request.user.is_authenticated and hasattr(request.user, 'role') and request.user.role == 'customer':
        try:
            return {'cart_count': request.user.cart.item_count}
        except Cart.DoesNotExist:
            return {'cart_count': 0}
    return {'cart_count': 0}
