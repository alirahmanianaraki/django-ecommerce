from .models import Product

RECENTLY_VIEWED_SESSION_KEY = 'recently_viewed'
MAX_RECENTLY_VIEWED = 12

class RecentlyViewed:
    """
    Session-backed recently viewed products list
    """

    def __init__(self, request):
        self.session = request.session
        raw = self.session.get(RECENTLY_VIEWED_SESSION_KEY)
        if raw is None:
            raw = []
        # Normalize: everything stored as int
        clean = []
        for item in raw:
            try:
                clean.append(int(item))
            except (TypeError, ValueError):
                continue
        # Trim to cap
        if len(clean) > MAX_RECENTLY_VIEWED:
            clean = clean[-MAX_RECENTLY_VIEWED:]
        self._ids = clean
        # Persists the clean version back
        if clean != raw:
            self.session[RECENTLY_VIEWED_SESSION_KEY] = clean
            self.session.modified = True

    def __len__(self):
        return len(self._ids)

    def __iter__(self):
        """
        Yield Product instances, newest first, skipping any that no longer exist.
        """
        if not self._ids:
            return

        products_by_id = {
            p.pk: p
            for p in Product.objects.filter(pk__in=self._ids)
        }

        pruned = [pid for pid in self._ids if pid in products_by_id]
        if pruned != self._ids:
            self._ids = pruned
            self.session[RECENTLY_VIEWED_SESSION_KEY] = pruned
            self.session.modified = True

        for pid in reversed(self._ids):
            yield products_by_id[pid]

    @property
    def ids(self):
        return list(reversed(self._ids))

    def add(self, product_id):
        """
        Push a product to the front of the recently-veiwed list.
        """
        try:
            pid = int(product_id)
        except (TypeError, ValueError):
            return False

        # Already at the front -> no-op
        if self._ids and self._ids[-1] == pid:
            return False

        # Remove if present (dedupe) and append (newest at end)
        self._ids = [i for i in self._ids if i != pid]
        self._ids.append(pid)

        # Enforce the cap from the front (oldest first)
        if len(self._ids) > MAX_RECENTLY_VIEWED:
            self._ids = self._ids[-MAX_RECENTLY_VIEWED:]

        self.session[RECENTLY_VIEWED_SESSION_KEY] = self._ids
        self.session.modified = True
        return True

    def clear(self):
        if not self._ids:
            return
        self._ids = []
        self.session[RECENTLY_VIEWED_SESSION_KEY] = []
        self.session.modified = True

        