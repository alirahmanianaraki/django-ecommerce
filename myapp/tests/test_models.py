from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from myapp.models import Product, Tag


class TagModelTests(TestCase):
    def test_str_returns_name(self):
        tag = Tag.objects.create(name="GPU")
        self.assertEqual(str(tag), "GPU")

    def test_save_generates_slug(self):
        tag = Tag.objects.create(name="Graphics Cards")
        self.assertEqual(tag.slug, "graphics-cards")

    def test_duplicate_names_get_unique_slugs(self):
        first = Tag.objects.create(name="Gaming")
        second = Tag.objects.create(name="Gaming")

        self.assertEqual(first.slug, "gaming")
        self.assertEqual(second.slug, "gaming-1")

    def test_get_absolute_url(self):
        tag = Tag.objects.create(name="GPUs")
        self.assertEqual(tag.get_absolute_url(), reverse("myapp:tag", kwargs={"slug": tag.slug}))


class ProductModelTests(TestCase):
    def test_save_generates_slug(self):
        product = Product.objects.create(
            title="RTX 5070",
            description="Graphics card",
            price=Decimal("599.99"),
            stock=5,
        )
        self.assertEqual(product.slug, "rtx-5070")

    def test_duplicate_titles_get_unique_slugs(self):
        first = Product.objects.create(
            title="Gaming Mouse",
            description="Mouse",
            price=Decimal("49.99"),
            stock=10,
        )
        second = Product.objects.create(
            title="Gaming Mouse",
            description="Another mouse",
            price=Decimal("59.99"),
            stock=5,
        )

        self.assertEqual(first.slug, "gaming-mouse")
        self.assertEqual(second.slug, "gaming-mouse-1")

    def test_str_contains_title_and_primary_key(self):
        product = Product.objects.create(
            title="Mechanical Keyboard",
            description="Keyboard",
            price=Decimal("100.00"),
            stock=3,
        )
        self.assertEqual(str(product), f"Mechanical Keyboard--id: {product.pk}")

    def test_get_absolute_url(self):
        product = Product.objects.create(
            title="RTX 5080",
            description="GPU",
            price=Decimal("999.99"),
            stock=2,
        )
        self.assertEqual(
            product.get_absolute_url(),
            reverse("myapp:detail", kwargs={"slug": product.slug}),
        )
