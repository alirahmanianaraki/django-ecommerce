from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from myapp.models import Product, Tag


class ProductViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            title="RTX 5070",
            description="Powerful graphics card",
            price=Decimal("599.99"),
            stock=5,
        )
        cls.other = Product.objects.create(
            title="Office Keyboard",
            description="Mechanical keyboard",
            price=Decimal("99.99"),
            stock=0,
        )
        cls.tag = Tag.objects.create(name="Graphics Cards")
        cls.product.tag.add(cls.tag)

    def test_index_returns_products(self):
        response = self.client.get(reverse("myapp:index"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "myapp/index.html")
        self.assertContains(response, self.product.title)
        self.assertContains(response, self.other.title)

    def test_index_filters_products(self):
        response = self.client.get(reverse("myapp:index"), {"in_stock": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.title)
        self.assertNotContains(response, self.other.title)

    def test_detail_returns_product(self):
        response = self.client.get(
            reverse("myapp:detail", kwargs={"slug": self.product.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "myapp/detail.html")
        self.assertEqual(response.context["product"], self.product)

    def test_detail_for_missing_product_returns_404(self):
        response = self.client.get(reverse("myapp:detail", kwargs={"slug": "missing"}))
        self.assertEqual(response.status_code, 404)

    def test_tag_view_returns_only_tagged_products(self):
        response = self.client.get(
            reverse("myapp:tag", kwargs={"slug": self.tag.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.title)
        self.assertNotContains(response, self.other.title)

    def test_search_rejects_queries_shorter_than_three_characters(self):
        response = self.client.get(reverse("myapp:search"), {"q": "gp"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter at least 3 characters.")
        self.assertEqual(response.context["query"], "gp")

    def test_search_strips_control_characters(self):
        response = self.client.get(reverse("myapp:search"), {"q": "  gpu\x00  "})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["query"], "gpu")

    def test_search_caps_query_at_100_characters(self):
        query = "a" * 150
        response = self.client.get(reverse("myapp:search"), {"q": query})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["query"]), 100)

    def test_search_returns_matching_product(self):
        response = self.client.get(reverse("myapp:search"), {"q": "RTX"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.title)
