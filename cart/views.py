from django.shortcuts import render
from django.http import JsonResponse
from .cart import Cart

# Create your views here.
def add_to_cart(request):
    cart = Cart(request)
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        product_quantity = request.POST.get('product_quantity')
        print(f"Product: {product_id}, qty: {product_quantity}")
        cart.add(product_id=product_id, product_quantity=product_quantity)
        total_quantities = cart.__len__()
    return JsonResponse({'qty': total_quantities})

def cart_overview(request):
    cart = Cart(request)
    return render(request, 'cart/cart-overview.html',
                  {
                      'cart': cart
                  })

def update_cart(request):
    cart = Cart(request)
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        product_quantity = request.POST.get('product_quantity')
        cart.update(product_id=product_id, product_quantity=product_quantity)
        return JsonResponse({'Message': 'Product updated'})

def delete_cart(request):
    cart = Cart(request)
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        cart.delete(product_id=product_id)
        cart_quantity = cart.__len__()
        cart_total = cart.get_total_price()
        return JsonResponse({
            "qty": cart_quantity,
            'total': cart_total,
        })

    
