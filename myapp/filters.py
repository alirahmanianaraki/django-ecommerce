from .models import Category

def apply_product_filters(request, queryset, default_sort='newest', allow_relevance=False):
    raw_min = request.GET.get('min_price', '').strip()
    raw_max = request.GET.get('max_price', '').strip()
    raw_in_stock = request.GET.get('in_stock', '')
    raw_sort = request.GET.get('sort', '')
    raw_category = request.GET.get('category', '').strip()

    min_price = None
    max_price = None
    in_stock = raw_in_stock == '1'
    category = None

    try:
        if raw_min:
            min_price = float(raw_min)
            if min_price < 0:
                min_price = None
    except (ValueError, TypeError):
        min_price = None

    try:
        if raw_max:
            max_price = float(raw_max)
            if max_price < 0:
                max_price = None
    except (ValueError, TypeError):
        max_price = None

    if min_price is not None and max_price is not None and min_price > max_price:
        min_price, max_price = max_price, min_price

    if min_price is not None:
        queryset = queryset.filter(price__gte=min_price)
    if max_price is not None:
        queryset = queryset.filter(price__lte=max_price)
    if in_stock:
        queryset = queryset.filter(stock__gt=0)

    #category filter
    if raw_category:
        try:
            category = Category.objects.get(slug=raw_category)
            descendant_ids = [c.pk for c in category.get_descendants(include_self=True)]
            queryset = queryset.filter(category__in=descendant_ids).distinct()
        except Category.DoesNotExist:
            category = None

    # Sorting
    SORT_OPTIONS = {
        'price_low': 'price',
        'price_high': '-price',
        'newest': '-id',
        'oldest': 'id',
    }
    if allow_relevance:
        SORT_OPTIONS['relevance'] = '-rank'

    chosen_sort = raw_sort or default_sort
    if chosen_sort == 'relevance' and not allow_relevance and 'rank' not in queryset.query.annotations:
        chosen_sort = 'newest'

    sort_field = SORT_OPTIONS.get(chosen_sort, '-id')

    # fall back to -id.
    if sort_field == '-rank':
        try:
            queryset = queryset.order_by(sort_field)
        except Exception:
            queryset = queryset.order_by('-id')
    else:
        queryset = queryset.order_by(sort_field)

    context = {
        'min_price': raw_min,
        'max_price': raw_max,
        'in_stock': in_stock,
        'sort': chosen_sort,
        'allow_relevance': allow_relevance,
        'active_category': category,
    }

    return queryset, context