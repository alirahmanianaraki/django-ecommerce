from django.db import migrations


def create_uncategorized_category(apps, schema_editor):
    Category = apps.get_model('myapp', 'Category')
    Product = apps.get_model('myapp', 'Product')

    uncategorized, _ = Category.objects.get_or_create(
        slug='uncategorized',
        defaults={'name': 'Uncategorized'},
    )

    # At this point in migration history, the field is still named 'Category'
    # (capital C). Migration 0009 renames it to 'category'.
    orphaned_products = Product.objects.filter(Category__isnull=True)

    if orphaned_products.exists():
        through = Product._meta.get_field('Category').remote_field.through
        through.objects.bulk_create([
            through(product_id=prod.pk, category_id=uncategorized.pk)
            for prod in orphaned_products
        ])


def remove_uncategorized_category(apps, schema_editor):
    Category = apps.get_model('myapp', 'Category')
    try:
        uncategorized = Category.objects.get(slug='uncategorized')
        uncategorized.products.clear()
        uncategorized.delete()
    except Category.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ("myapp", "0007_category_product_category"),
    ]

    operations = [
        migrations.RunPython(
            create_uncategorized_category,
            remove_uncategorized_category
        )
    ]