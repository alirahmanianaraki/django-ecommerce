from django.shortcuts import render, get_object_or_404
from django.contrib.postgres.search import (
    SearchQuery,
    SearchRank,
    SearchVector,
    TrigramSimilarity
)
import re
from django.db.models import F, Q
from .filters import apply_product_filters
from .pagination import paginate
from .feature_filters import (parse_feature_filters,
                            build_filter_groups,
                            apply_feature_filters,)
from .models import (ProductImage, 
                     Product, 
                     Tag, 
                     Category,
                     Feature)

# Create your views here.
def index(request):
    base_queryset = Product.objects.all().prefetch_related('product_images')
    products_qs, filter_context = apply_product_filters(request, base_queryset)
    known_feature_slugs = set(
        Feature.objects
        .filter(is_filterable=True)
        .values_list('slug', flat=True)
    )
    selections = parse_feature_filters(request, known_feature_slugs)
    products_qs = apply_feature_filters(products_qs, selections)
    page_obj, pagination_context= paginate(request, products_qs)

    filter_groups = build_filter_groups(selections)
    
    context = {
        'page_obj': page_obj,
        'selection': selections,
        'filter_groups': filter_groups,
        **filter_context,
        **pagination_context
    }
    return render(request, 'myapp/index.html', context)

def detail(request, slug):
    product = get_object_or_404(
        Product.objects.prefetch_related(
            'category', 
            'tag', 
            'product_images')
            .with_specs(),
        slug=slug
        )
    return render(request, 'myapp/detail.html',
                  {
                      'product': product,
                      'has_visible_specs': product.has_visible_specs,
                  })

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
    known_feature_slugs = set(
        Feature.objects
        .filter(is_filterable=True)
        .values_list('slug', flat=True)
    )
    selections = parse_feature_filters(request, known_feature_slugs)
    results_qs = apply_feature_filters(request, known_feature_slugs)
    page_obj, pagination_context = paginate(request, results_qs)

    filter_groups = build_filter_groups(selections)

    return render(request, 'myapp/search.html',
                  {
                      'query': query,
                      'page_obj': page_obj,
                      'error': error,
                      'selections': selections,
                      'filter_groups': filter_groups,
                      **filter_context,
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
    product_qs, filter_context = apply_product_filters(request, base_queryet)
    known_feature_slugs = set(
        Feature.objects
        .filter(is_filterable=True)
        .values_list('slug', flat=True)
    )
    selections = parse_feature_filters(request, known_feature_slugs)
    product_qs = apply_feature_filters(product_qs, selections)
    page_obj, pagination_context = paginate(request, product_qs)
    subcategories = category_obj.children.all()

    filter_groups = build_filter_groups(selections)

    return render(request, 'myapp/category.html',
                  {
                      'category': category_obj,
                      'subcategories': subcategories,
                      'page_obj': page_obj,
                      'selections': selections,
                      'filter_groups': filter_groups,
                      **filter_context,
                      **pagination_context,
                      'active_category': category_obj
                  })

