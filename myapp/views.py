from django.shortcuts import render, get_object_or_404
from django.contrib.postgres.search import (
    SearchQuery,
    SearchRank,
    SearchVector,
    TrigramSimilarity
)
import re
from django.db.models import F, Q
from .models import ProductImage, Product, Tag

# Create your views here.
def index(request):
    products = Product.objects.all()
    return render(request, 'myapp/index.html', 
                  {
                      'products': products,
                  })

def detail(request, slug):
    product = get_object_or_404(Product,
                                slug=slug)
    return render(request, 'myapp/detail.html',
                  {
                      'product': product
                  })

def tag(request, slug):
    tag = get_object_or_404(Tag, slug=slug)
    related_products = Product.objects.filter(tag=tag).prefetch_related('product_images')
    return render(request,'myapp/tagged-products.html',
                  {
                      'related_products': related_products,
                      'tag': tag
                  })

def search(request):
    MIN_SEARCH_LENGTH = 3
    MAX_SEARCH_LENGTH = 100

    query = request.GET.get('q', '').strip()
    query = re.sub(r'[\x00-\x08\x0b-\x1f\x7f]', '', query)
    results = Product.objects.none()
    error = None

    # Cap length
    if len(query) > MAX_SEARCH_LENGTH:
        query = query[:MAX_SEARCH_LENGTH]

    if query and len(query) < MIN_SEARCH_LENGTH:
        error = f"Please enter at least {MIN_SEARCH_LENGTH} characters."

    elif query:
        search_query = SearchQuery(query, config='english')

        results = (
            Product.objects
            .annotate(
                rank=SearchRank(F('search_vector'), search_query),
                similarity=TrigramSimilarity('title', query),
            )
            .filter(Q(rank__gte=0.1) | Q(similarity__gt=0.2))
            .order_by('-rank', '-similarity')
            .distinct()
        )

    return render(request, 'myapp/search.html',
                  {
                      'query': query,
                      'results': results,
                      'error': error
                  })