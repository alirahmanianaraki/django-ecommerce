from django import template
from django.core.cache import cache
from myapp.models import Category

register = template.Library()

def _subtree_has_products(category, direct_product_ids, visited=None):
    """
    Return True if `category` itself, or any of its descendants, has a
    product directly assigned to it.

    `direct_product_ids` is a set of category PKs that have products
    directly assigned (compute that once, before calling this).

    `visited` guards against accidental cycles in the tree.
    """
    if visited is None:
        visited = set()
    if category.pk in visited:
        return False
    visited.add(category.pk)

    if category.pk in direct_product_ids:
        return True

    for child in category.children.all():
        if _subtree_has_products(child, direct_product_ids, visited):
            return True
    return False

def _build_node(category, direct_product_ids):
    """
    Return a nested dict for `category` and its visible descendants.
    """
    visible_children = []
    for child in category.children.all():
        node = _build_node(child, direct_product_ids)
        if node is not None:
            visible_children.append(node)

    has_products = (
        category.pk in direct_product_ids
        or bool(visible_children)
    )

    if not has_products:
        return None

    return {
        'category': category,
        'children': visible_children
    }

@register.simple_tag
def menu_categories():
    """
    Return the tree of categories that should appear in the site menu.

    Structure of each item:
        {
            'category': <Category instance>,
            'children': [ <same shape>, ... ],
        }

    Only nodes whose subtree contains at least one product are kept.
    'Uncategorized' is always excluded.
    """
    direct_product_ids = set(
        Category.objects
        .filter(products__isnull=False)
        .values_list('pk', flat=True)
    )

    roots = (
        Category.objects
        .filter(parent__isnull=True)
        .exclude(slug='uncategorized')
        .prefetch_related('children__children__children')
        .order_by('name')
    )

    menu = []
    for root in roots:
        node = _build_node(root, direct_product_ids)
        if node is not None:
            menu.append(node)

    return menu

@register.simple_tag(takes_context=True)
def active_category_ids(context):
    """
    Return a set of category PKs that should be highlighted in the menu
    for the current request.
    """
    request = context.get('request')
    if request is None:
        return set()

    # fetching the request.resolver_match by using a safety net
    match = getattr(request, 'resolver_match', None)
    if match is None or match.url_name != 'category':
        return set()

    slug = match.kwargs.get('slug')
    if not slug:
        return set()

    try:
        category = Category.objects.get(slug=slug)
    except Category.DoesNotExist:
        return set()

    ids = set()
    node = category
    while node is not None:
        ids.add(node.pk)
        node = node.parent
    return ids