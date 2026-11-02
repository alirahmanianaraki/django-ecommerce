from .models import Product

MAX_COMPARE = 4
SESSION_KEY = 'comparison'

class Comparison:
    """
    Session-backed product comparison list.
    """

    def __init__(self, request):
        self.session = request.session
        ids = self.session.get(SESSION_KEY)
        if ids is None:
            ids = self.session[SESSION_KEY] = []
        self._ids = [str(i) for i in ids]
        self.session[SESSION_KEY] = self._ids

    def __len__(self):
        return len(self._ids)

    def __iter__(self):
        """
        Yield Product instances in the stored order
        """
        if not self._ids:
            return
        
        products_by_id = {
            str(p.pk): p
            for p in Product.objects.filter(pk__in=self._ids)
        }
        missing = [pid for pid in self._ids if pid not in products_by_id]
        if missing:
            self._ids = [pid for pid in self._ids if pid in products_by_id]
            self.session[SESSION_KEY] = self._ids
            self.session.modified = True
        for pid in self._ids:
            yield products_by_id[pid]

    def contains(self, product_id):
        return str(product_id) in self._ids

    def is_full(self):
        return len(self._ids) >= MAX_COMPARE

    def add(self, product_id):
        """
        Add a product; Returns a dict with what happened.
        """
        pid = str(product_id)

        if pid in self._ids:
            return {'added': False, 'reason': 'duplicate'}
        if self.is_full():
            return {"added": False, 'reason': 'full'}
        if not Product.objects.filter(pk=pid).exists():
            return {'added': False, 'reason': 'not_found'}

        self._ids.append(pid)
        self.session[SESSION_KEY] = self._ids
        self.session.modified = True
        return {'added': True, 'reason': None}

    def remove(self, product_id):
        pid = str(product_id)
        if pid not in self._ids:
            return False
        self._ids.remove(pid)
        self.session[SESSION_KEY] = self._ids
        self.session.modified = True
        return True

    def clear(self):
        if not self._ids:
            return
        self._ids = []
        self.session[SESSION_KEY] = []
        self.session.modified = True

    @property
    def ids(self):
        return list(self._ids)

def build_comparison_table(products):
    products = list(products)
    if not products:
        return {'products': [], 'rows': []}

    specs_by_product = {p.pk: {} for p in products}
    all_features = {}

    for product in products:
        for pf in product.features.all():
            if not pf.feature.is_visible_on_product_page:
                continue
            all_features[pf.feature.pk] = pf.feature
            display_value = pf.value.value
            if pf.value.unit:
                display_value += f" {pf.value.unit}"
            bucket = specs_by_product[product.pk].setdefault(pf.feature.pk, [])
            if display_value not in bucket:
                bucket.append(display_value)

    ordered_features = sorted(
        all_features.values(),
        key=lambda f: (f.display_order, f.name),
    )

    rows = []
    for feature in ordered_features:
        cells = []
        raw_values = []
        for product in products:
            values = specs_by_product[product.pk].get(feature.pk, [])
            display = ", ".join(values) if values else None
            cells.append({'product': product, 'value': display})
            if values:
                raw_values.append(tuple(values))

        all_same = len({tuple(v) for v in raw_values}) <= 1 if raw_values else True
        rows.append({
            'feature': feature,
            'cells': cells,
            'all_same': all_same
        })
    return {'products': products, 'rows': rows}
