from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from users.models import Address
from cart.cart import Cart
from .models import Order, OrderItem
from .services import place_order, InsufficientStock


# Create your views here.
def checkout(request):
    cart = Cart(request)
    cart_length = len(cart)
    if request.user.is_authenticated:
        address = Address.objects.filter(user=request.user).first()
        return render(request, 'orders/checkout.html',
                      {
                          'address': address,
                          'cart_length': cart_length,
                          'cart': cart
                      })
    else:
        messages.error(request, 'You must first register or login')
        return redirect('users:register')

@require_POST
def place_order_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False,
            'error': 'Please register first or login',
            'redirect': 'register',
        }, status=401)

    cart = Cart(request)
    if len(cart) == 0:
        return JsonResponse({
            'success': False,
            'error': 'Your cart is empty',
            'redirect': 'index',
        }, status=400)

    try:
        place_order(user=request.user, cart=cart)
    except InsufficientStock as exc:
        return JsonResponse({
            'success': False,
            'error': str(exc),
            'redirect': 'cart',
        }, status=400)

    return JsonResponse({'success': True})

def order_success(request):
    return render(request, 'orders/order_success.html')

def order_failed(request):
    return render(request, 'orders/order_failed.html')
            