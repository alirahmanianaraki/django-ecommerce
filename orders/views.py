from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from users.models import Address
import logging
from django.contrib.auth.decorators import login_required
from cart.cart import Cart
from .models import Order, OrderItem
from .services import (
    place_order,
    transition_order, 
    InsufficientStock,
    MissingShippingAddress,
    InvalidCoupon,
    InvalidStatusTransition,
)
from .emails import send_order_confirmation

logger = logging.getLogger(__name__)

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

    address = Address.objects.filter(user=request.user).first()

    try:
        order = place_order(user=request.user, cart=cart, address=address)
    except MissingShippingAddress:
        return JsonResponse({
            'success': False,
            'error': 'Please add a shipping address before placing an order',
            'redirect': 'address',
        }, status=400)
    except InsufficientStock as exc:
        return JsonResponse({
            'success': False,
            'error': str(exc),
            'redirect': 'cart',
        }, status=400)
    except InvalidCoupon as exc:
        return JsonResponse({
            'success': False,
            'error': str(exc),
            'redirect': 'cart',
        }, status=400)

    try:
        send_order_confirmation(order, request=request)
    except Exception as exc:
        logger.exception('Order confirmation email failed for order #%s', order.pk)
        
    return JsonResponse({'success': True})

def order_success(request):
    return render(request, 'orders/order_success.html')

def order_failed(request):
    return render(request, 'orders/order_failed.html')

@login_required(login_url='users:login')
def order_list(request):
    """Show all of the current user's orders"""
    orders = (
        Order.objects
        .filter(user=request.user)
        .prefetch_related('orderitem_set__product')
        .order_by('-created_at')
    )
    return render(request, 'orders/order_list.html', 
                  {
                      'orders': orders
                  })

@login_required(login_url='users:login')
def order_detail(request, pk):
    """Show one order"""
    order = get_object_or_404(
        Order.objects
        .filter(user=request.user)
        .prefetch_related('orderitem_set__product__product_images',
                          'status_events__changed_by'
        ),
        pk=pk,
    )
    return render(request, 'orders/order_detail.html',
                  {
                      'order': order
                  })

@require_POST
@login_required(login_url='users:login')
def cancel_order(request, pk):
    """
    Allow the customer to cacnel their own order, only if it's still cancellable.
    """
    order = get_object_or_404(Order, pk=pk, user=request.user)
    if order.is_terminal or not order.can_transition_to(Order.Status.CANCELLED):
        messages.error(request, 'This order cannot be cancelled at this stage')
        return redirect('orders:order_detail', pk=pk)
    try:
        transition_order(
            order,
            Order.Status.CANCELLED,
            changed_by=request.user,
            note='Canclled by customer'
        )
    except InvalidStatusTransition as exc:
        messages.error(request, str(exc))
        return redirect('order:order_detail', pk=pk)

    messages.success(request, f'Order #{order.pk} has been cancelled')
    return redirect('orders:order_detail', pk=pk)
    
            