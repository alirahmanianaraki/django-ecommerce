from decimal import Decimal
from django.test import TestCase
from django.urls import reverse

from myapp.models import Product
from myapp.recently_viewed import (
    RecentlyViewed, MAX_RECENTLY_VIEWED,
)


class RecentlyViewedServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.products = [
            Product.objects.create(
                title=f'P{i}', description='x',
                price=Decimal('10.00'), stock=1,
            )
            for i in range(MAX_RECENTLY_VIEWED + 3)
        ]

    def _request(self):
        from django.test import RequestFactory
        r = RequestFactory().get('/')
        r.session = self.client.session
        return r

    def test_empty_by_default(self):
        rv = RecentlyViewed(self._request())
        self.assertEqual(len(rv), 0)
        self.assertEqual(list(rv), [])

    def test_add_single(self):
        rv = RecentlyViewed(self._request())
        rv.add(self.products[0].pk)
        self.assertEqual(len(rv), 1)
        # __iter__ yields newest first
        self.assertEqual(list(rv), [self.products[0]])

    def test_newest_first(self):
        rv = RecentlyViewed(self._request())
        rv.add(self.products[0].pk)
        rv.add(self.products[1].pk)
        rv.add(self.products[2].pk)
        self.assertEqual(
            list(rv),
            [self.products[2], self.products[1], self.products[0]],
        )

    def test_reviewing_moves_to_front(self):
        rv = RecentlyViewed(self._request())
        rv.add(self.products[0].pk)
        rv.add(self.products[1].pk)
        rv.add(self.products[0].pk)  # revisit first
        self.assertEqual(
            list(rv),
            [self.products[0], self.products[1]],
        )

    def test_cap_enforced(self):
        rv = RecentlyViewed(self._request())
        for p in self.products:
            rv.add(p.pk)
        self.assertEqual(len(rv), MAX_RECENTLY_VIEWED)
        # Oldest should have fallen off
        yielded = list(rv)
        self.assertNotIn(self.products[0], yielded)
        # Newest should still be there
        self.assertIn(self.products[-1], yielded)

    def test_deleted_product_pruned_on_iter(self):
        rv = RecentlyViewed(self._request())
        rv.add(self.products[0].pk)
        rv.add(self.products[1].pk)
        p0_pk = self.products[0].pk
        self.products[0].delete()
        yielded = list(rv)
        self.assertEqual(yielded, [self.products[1]])
        self.assertEqual(len(rv), 1)

    def test_add_same_product_twice_is_noop_on_session(self):
        rv = RecentlyViewed(self._request())
        rv.add(self.products[0].pk)
        # Get the modified flag "clean" first
        self.client.session.save()
        # Now add again
        changed = rv.add(self.products[0].pk)
        self.assertFalse(changed)

    def test_clear(self):
        rv = RecentlyViewed(self._request())
        rv.add(self.products[0].pk)
        rv.add(self.products[1].pk)
        rv.clear()
        self.assertEqual(len(rv), 0)
        self.assertEqual(list(rv), [])


class RecentlyViewedViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            title='GPU', description='x',
            price=Decimal('100.00'), stock=5,
        )

    def test_viewing_detail_records_it(self):
        self.client.get(
            reverse('myapp:detail', kwargs={'slug': self.product.slug})
        )
        rv_session = self.client.session.get('recently_viewed', [])
        self.assertEqual(rv_session, [self.product.pk])

    def test_refresh_does_not_duplicate(self):
        url = reverse('myapp:detail', kwargs={'slug': self.product.slug})
        self.client.get(url)
        self.client.get(url)
        rv_session = self.client.session.get('recently_viewed', [])
        self.assertEqual(rv_session, [self.product.pk])

    # def test_clear_view(self):
    #     # Prime the session
    #     self.client.get(
    #         reverse('myapp:detail', kwargs={'slug': self.product.slug})
    #     )
    #     response = self.client.post(reverse('myapp:clear_recently_viewed'))
    #     self.assertEqual(response.status_code, 200)
    #     self.assertTrue(response.json()['success'])
    #     self.assertEqual(
    #         self.client.session.get('recently_viewed'), []
    #     )


class RecentlyViewedLoginLogoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth.models import User
        cls.user = User.objects.create_user(
            username='alice', password='StrongPass123!'
        )
        cls.product = Product.objects.create(
            title='GPU', description='x',
            price=Decimal('10.00'), stock=5,
        )

    def test_login_preserves_recently_viewed(self):
        # Anonymous user views a product
        self.client.get(
            reverse('myapp:detail', kwargs={'slug': self.product.slug})
        )
        self.assertEqual(
            self.client.session.get('recently_viewed'),
            [self.product.pk],
        )

        # Then logs in
        self.client.post(
            reverse('users:login'),
            {'username': 'alice', 'password': 'StrongPass123!'},
        )
        self.assertEqual(
            self.client.session.get('recently_viewed'),
            [self.product.pk],
        )