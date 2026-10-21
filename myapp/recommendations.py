from django.db.models import Q, Count
from .models import Product

DEFAULT_RELATED_LIMIT = 8

def _deepest_categories(product):
    """
    Return the list of the product's categories that have no children
    within the product's own category set
    """
    categories = list(product.category.all())
    if not categories:
        return []

    leaves = [c for c in categories if not c.children.exists()]
    return leaves or categories

def get_related_products(product, limit=DEFAULT_RELATED_LIMIT):
    """
    Return up to 'limit' products related to 'product' by:
    - being in the same most-specific category (or a descendant of it)
    - sharing feature values
    - sharing tags    
    """
    source_categories = _deepest_categories(product)
    if not source_categories:
        return Product.objects.none()

    candidate_category_ids = set()
    for cat in source_categories:
        candidate_category_ids.add(cat.pk)
        for desc in cat.get_descendants(include_self=False):
            candidate_category_ids.add(desc.pk)

    value_ids = list(
        product.features.values_list('value_id', flat=True)
    )
    tag_ids = list(
        product.tag.values_list('id', flat=True)
    )
    if not value_ids and not tag_ids:
        return Product.objects.none()

    return (
        Product.objects
        .filter(is_available=True)
        .filter(category__pk__in=candidate_category_ids)
        .exclude(pk=product.pk)
        .annotate(
            shared_features=Count(
                'features',
                filter=Q(features__value_id__in=value_ids),
                distinct=True
            ),
            shared_tags=Count(
                'tag',
                filter=Q(tag__id__in=tag_ids),
                distinct=True
            ),
        )
        .filter(Q(shared_features__gt=0) | Q(shared_tags__gt=0))
        .order_by('-shared_features', '-shared_tags', '-id')
        .prefetch_related('product_images')
        .distinct()
        [:limit]
    )