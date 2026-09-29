from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from myapp.models import Product
from .models import Wishlist, WishlistItems
from .wishlist import WishlistService

# Create your views here.
@require_POST
def add_item_to_wishlist(request):
    if not request.user.is_authenticated:
        return JsonResponse({'success': False,
                             'error': 'Register or Login first'},
                             status= 400)
    
    product_id = request.POST.get('product_id')
    if not product_id:
        return JsonResponse({
            'success': False, 
            'error': 'Product id is required'}, 
            status= 401)
    current_wishlist = WishlistService(user=request.user, request=request)
    created = current_wishlist.add(product_id=product_id)
    if created:
        message = 'Added to the wishlist'
    else:
        message = 'Already in the wishlist'

    return JsonResponse({
        'success': True, 
        'added': created,
        'message': message
        })

@require_POST
def remove_item_from_wishlist(request):
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False,
            'removed': False,
            'message': 'Register or Login first'
        },
        status= 401)
    user_wishlist = WishlistService(user=request.user, request=request)
    deleted = user_wishlist.remove(product_id=request.POST.get('product_id'))
    return JsonResponse({
        'success': True,
        'deleted': deleted,
        'message': 'Item successfully deleted'
    })

def wishlist_overview(request):
    if not request.user.is_authenticated:
        messages.error(request, 'Register or Login first')
        return redirect('users:register')
    user_wishlist = WishlistService(user=request.user, request=request)
    items = WishlistItems.objects.filter(wishlist=user_wishlist.wishlist).select_related('product').prefetch_related('product__product_images', 'product__tag')
    return render(request, 'wishlists/wishlist_overview.html',
                  {
                      'items': items
                  })

