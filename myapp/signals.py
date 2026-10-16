from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.db.models import Avg, Count
from .models import Product, Category, Review

def get_uncategorized_category():
    """
    Get or create the fallback Uncategorized category.
    """
    uncategorized, _ = Category.objects.get_or_create(
        slug='uncategorized',
        defaults={'name': 'Uncategorized'}
    )
    return uncategorized


@receiver(post_save, sender=Product)
def assign_uncategorized_to_new_product(sender, instance, created, **kwargs):
    """
    Give every newly created product a temporary fallback category.
    If the product receives a real category afterward, the m2m_changed
    signal will remove Uncategorized.
    """
    if not created:
        return

    uncategorized = get_uncategorized_category()
    instance.category.add(uncategorized)


@receiver(m2m_changed, sender=Product.category.through)
def maintain_product_categories(
    sender,
    instance,
    action,
    reverse,
    model,
    pk_set,
    using,
    **kwargs
):
    """
    Every Product must have at least one category.
    Uncategorized is used only as a fallback.
    """

    # forward Product -> Category relationship.
    if reverse:
        return

    if action not in {'post_add', 'post_remove', 'post_clear'}:
        return

    uncategorized = get_uncategorized_category()
    categories = instance.category.all()


    # CASE 1: Product has at least one real category.
    real_categories_exist = categories.exclude(
        pk=uncategorized.pk
    ).exists()

    if real_categories_exist:
        if categories.filter(pk=uncategorized.pk).exists():
            instance.category.remove(uncategorized)
        return

    # CASE 2: Product has zero categories.
    if not categories.exists():
        instance.category.add(uncategorized)

def recompute_product_rating(product):
    """
    Recalculate avg_rating and rating_count for a single product
    """
    aggregate = product.reviews.aggregate(
        avg=Avg('rating'),
        count=Count('id'),
    )
    product.avg_rating = aggregate['avg'] or 0
    product.rating_count = aggregate['count'] or 0
    product.save(update_fields=['avg_rating', 'rating_count'])

@receiver(post_save, sender=Review)
def update_rating_on_save(sender, instance, **kwargs):
    recompute_product_rating(instance.product)

@receiver(post_delete, sender=Review)
def update_rating_on_delete(sender, instance, **kwargs):
    recompute_product_rating(instance.product)