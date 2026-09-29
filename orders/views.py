from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from .models import Order, OrderItem
from users.models import Address
from cart.cart import Cart

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
def place_order(request):
    order_success = False
    current_user = request.user
    cart = Cart(request)
    if len(cart) == 0:
        return JsonResponse(
            {'success': False,
             'error': 'Your cart is empty',
             'redirect': 'index'},
             status = 400
        )

    if request.method == 'POST':
        if request.user.is_authenticated:
            order = Order.objects.create(user=current_user, total_amount=cart.get_total_price())
            for item in cart:
                OrderItem.objects.create(
                    order=order,
                    product=item['product'],
                    quantity=item['qty']
                )
            order_success = True
            return JsonResponse({'success': order_success})

        else:
            return JsonResponse({
                'success': False,
                'error': 'Please register first or login',
                'redirect': 'register',
            },
            status=401
            )

def order_success(request):
    return render(request, 'orders/order_success.html')

def order_failed(request):
    return render(request, 'orders/order_failed.html')
            