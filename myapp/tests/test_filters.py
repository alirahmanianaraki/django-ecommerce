from decimal import Decimal
from django.db.models import F, Value
from django.test import RequestFactory, TestCase

from myapp.filters import apply_product_filters
from myapp.models import Product


class ProductFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cheap = Product.objects.create(
            title="Cheap GPU", description="GPU", price=Decimal("100.00"), stock=0
        )
        cls.mid = Product.objects.create(
            title="Mid GPU", description="GPU", price=Decimal("300.00"), stock=5
        )
        cls.expensive = Product.objects.create(
            title="Expensive GPU", description="GPU", price=Decimal("900.00"), stock=2
        )

    def request(self, params=None):
        query = ""
        if params:
            from urllib.parse import urlencode
            query = "?" + urlencode(params)
        return RequestFactory().get("/", data=params or {})

    def test_min_and_max_price_filter(self):
        qs, context = apply_product_filters(
            self.request({"min_price": "200", "max_price": "500"}),
            Product.objects.all(),
        )
        self.assertEqual(list(qs), [self.mid])
        self.assertEqual(context["min_price"], "200")
        self.assertEqual(context["max_price"], "500")

    def test_negative_price_is_ignored(self):
        qs, _ = apply_product_filters(
            self.request({"min_price": "-10"}), Product.objects.all()
        )
        self.assertEqual(qs.count(), 3)

    def test_invalid_price_is_ignored(self):
        qs, _ = apply_product_filters(
            self.request({"min_price": "abc", "max_price": "xyz"}), Product.objects.all()
        )
        self.assertEqual(qs.count(), 3)

    def test_reversed_range_is_normalized(self):
        qs, context = apply_product_filters(
            self.request({"min_price": "800", "max_price": "200"}), Product.objects.all()
        )
        self.assertEqual(list(qs), [self.mid])
        self.assertEqual(context["min_price"], "800")
        self.assertEqual(context["max_price"], "200")

    def test_in_stock_filter(self):
        qs, context = apply_product_filters(
            self.request({"in_stock": "1"}), Product.objects.all()
        )
        self.assertEqual(set(qs), {self.mid, self.expensive})
        self.assertTrue(context["in_stock"])

    def test_sorting_options(self):
        cases = {
            "price_low": [self.cheap, self.mid, self.expensive],
            "price_high": [self.expensive, self.mid, self.cheap],
            "oldest": [self.cheap, self.mid, self.expensive],
            "newest": [self.expensive, self.mid, self.cheap],
        }
        for sort, expected in cases.items():
            with self.subTest(sort=sort):
                qs, context = apply_product_filters(
                    self.request({"sort": sort}), Product.objects.all()
                )
                self.assertEqual(list(qs), expected)
                self.assertEqual(context["sort"], sort)

    def test_unknown_sort_falls_back_to_newest(self):
        qs, context = apply_product_filters(
            self.request({"sort": "not-a-real-sort"}), Product.objects.all()
        )
        self.assertEqual(list(qs), [self.expensive, self.mid, self.cheap])
        self.assertEqual(context["sort"], "not-a-real-sort")

    def test_relevance_sort_is_available_only_when_allowed(self):
        request = self.request({"sort": "relevance"})
        qs_in = Product.objects.annotate(rank=Value(0.0))
        qs, context = apply_product_filters(
            request, qs_in, default_sort="relevance", allow_relevance=True
        )
        self.assertEqual(qs.query.order_by, ("-rank",))
        self.assertTrue(context["allow_relevance"])