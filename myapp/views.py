from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.postgres.search import (
    SearchQuery,
    SearchRank,
    SearchVector,
    TrigramSimilarity
)
import re
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import F, Q
from django.db.models import Avg, Count
from .filters import apply_product_filters
from .pagination import paginate
from .feature_filters import build_sidebar_context
from .forms import ReviewForm, StockAlerForm
from .recommendations import get_related_products
from .models import ( Product, 
                     Tag, 
                     Category,
                     Review,
                     StockAlert)
from orders.models import OrderItem

# Create your views here.
def index(request):
    base_queryset = Product.objects.all().prefetch_related('product_images')
    products_qs, filter_context = apply_product_filters(request, base_queryset)
    products_qs, sidebar_context = build_sidebar_context(request, products_qs)
    page_obj, pagination_context= paginate(request, products_qs)
    
    context = {
        'page_obj': page_obj,
        **filter_context,
        **pagination_context,
        **sidebar_context
    }
    return render(request, 'myapp/index.html', context)

def detail(request, slug):
    product = get_object_or_404(
        Product.objects.prefetch_related(
            'category', 
            'tag', 
            'product_images',
            'reviews__user')
            .with_specs(),
        slug=slug
        )
    review_form = ReviewForm()
    existing_review = None
    can_review = False
    has_purchased = False
    if request.user.is_authenticated:
        existing_review = Review.objects.filter(
            product=product, user=request.user
        ).first()
        has_purchased = OrderItem.objects.filter(
            order__user=request.user,
            product=product,
        ).exists()

        # Eligible if they bought it and don't have a review yet
        can_review = has_purchased and existing_review is None

    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.error(request, 'Please log in to write a review')
            return redirect('users:login')
        if not has_purchased:
            messages.error(request, 'Only verified buyers can review this product')
            return redirect(product.get_absolute_url())
        if existing_review is not None:
            messages.error(request, 'You have already reviewed this product')
            return redirect(product.get_absolute_url())

        review_form = ReviewForm(request.POST)
        if review_form.is_valid():
            review = review_form.save(commit=False)
            review.product = product
            review.user = request.user
            review.save()
            messages.success(request, 'Thanks for your review')
            return redirect(product.get_absolute_url())

    # Aggregate + Distribution
    reviews_qs = product.reviews.all()
    distribution = _rating_distribution(product)
    related_products = get_related_products(product)

    return render(request, 'myapp/detail.html',
                  {
                      'product': product,
                      'has_visible_specs': product.has_visible_specs,
                      'reviews': reviews_qs,
                      'review_form': review_form,
                      'existing_review': existing_review,
                      'can_review': can_review,
                      'has_purchased': has_purchased,
                      'rating_distribution': distribution,
                      'related_products': related_products
                  })

def _rating_distribution(product):
    rows = (
        product.reviews
        .values('rating')
        .annotate(count=Count('id'))
        .order_by('-rating')
    )
    counts = {5:0 , 4:0, 3:0, 2:0, 1:0}
    for row in rows:
        counts[row['rating']] = row['count']
    total = sum(counts.values())
    percentages = {
        star: (counts[star] * 100.0/ total) if total else 0.0 
        for star in counts
    }
    return {
        'counts': counts,
        'percentages': percentages,
        'total': total
    }

def tag(request, slug):
    tag = get_object_or_404(Tag, slug=slug)
    related_products_qs = (
        Product.objects
        .filter(tag=tag)
        .prefetch_related('product_images')
        .order_by('-id')
        )
    page_obj, pagination_context = paginate(request, related_products_qs)
    return render(request,'myapp/tagged-products.html',
                  {
                      'page_obj': page_obj,
                      'tag': tag,
                      **pagination_context
                  })

def search(request):
    MIN_SEARCH_LENGTH = 3
    MAX_SEARCH_LENGTH = 100

    query = request.GET.get('q', '').strip()
    query = re.sub(r'[\x00-\x08\x0b-\x1f\x7f]', '', query)
    base_queryset = Product.objects.none()
    error = None

    # Cap length
    if len(query) > MAX_SEARCH_LENGTH:
        query = query[:MAX_SEARCH_LENGTH]

    if query and len(query) < MIN_SEARCH_LENGTH:
        error = f"Please enter at least {MIN_SEARCH_LENGTH} characters."

    elif query:
        search_query = SearchQuery(query, config='english')

        base_queryset = (
            Product.objects
            .annotate(
                rank=SearchRank(F('search_vector'), search_query),
                similarity=TrigramSimilarity('title', query),
            )
            .filter(Q(rank__gte=0.1) | Q(similarity__gt=0.2))
            .prefetch_related('product_images')
            .distinct()
        )

    results_qs, filter_context = apply_product_filters(
        request, 
        base_queryset, 
        default_sort='relevance', 
        allow_relevance=True
        )
    results_qs, sidebar_context = build_sidebar_context(request, results_qs)
    page_obj, pagination_context = paginate(request, results_qs)

    return render(request, 'myapp/search.html',
                  {
                      'query': query,
                      'page_obj': page_obj,
                      'error': error,
                      **filter_context,
                      **sidebar_context,
                      **pagination_context
                  })

def category(request, slug):
    category_obj = get_object_or_404(Category, slug=slug)
    descendants_ids = [c.pk for c in category_obj.get_descendants(include_self=True)]
    base_queryet = (
        Product.objects
        .filter(category__in=descendants_ids)
        .prefetch_related('product_images')
        .distinct()
    )
    products_qs, filter_context = apply_product_filters(request, base_queryet)
    products_qs, sidebar_context = build_sidebar_context(request, products_qs)
    page_obj, pagination_context = paginate(request, products_qs)
    subcategories = category_obj.children.all()

    return render(request, 'myapp/category.html',
                  {
                      'category': category_obj,
                      'subcategories': subcategories,
                      'page_obj': page_obj,
                      **filter_context,
                      **sidebar_context,
                      **pagination_context,
                      'active_category': category_obj
                  })

@require_POST
def notify_when_available(request, slug):
    """
    Register a stock alert for a product
    """
    product = get_object_or_404(Product, slug=slug)
    if product.stock > 0:
        if _is_ajax(request):
            return JsonResponse({
                'success': False,
                'error': 'This product is currenlty in stock',
            }, status=400)
        messages.error(request, 'This product is currently in stock')
        return redirect(product.get_absolute_url())

    form = StockAlerForm(request.POST)

    if not form.is_valid():
        if _is_ajax(request):
            return JsonResponse({
                'success': False,
                'error': 'Please enter a valid email address',
                'errors': form.errors,
            }, status=400)
        # Non-AJAX
        messages.error(request, 'Please enter a valid email address')
        return redirect(product.get_absolute_url())

    email = form.cleaned_data['email']

    # Deduplicate (product, email)
    exisiting = StockAlert.objects.filter(
        product=product,
        email=email,
        notified_at__isnull=True,
    ).exists()

    if not exisiting:
        StockAlert.objects.create(product=product, email=email)
    if _is_ajax(request):
        return JsonResponse({
            'success': True,
            'message': 'Your are on the list. We will email you when it is back',
            'already_subscribed': exisiting
        })
    messages.success(
        request,
        'Your are on the list. We will email you when it is back'
    )
    return redirect(product.get_absolute_url())

def _is_ajax(request):
    """Return True if the request was made via AJAX"""
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'
    