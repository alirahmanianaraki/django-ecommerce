// myapp/static/myapp/js/comparison.js
//
// Behaviour for the "Compare" toggle buttons.
// Each button must declare:
//   data-product-id="<pk>"
//   data-in-comparison="true|false"
//   data-add-url="<url>"
//   data-remove-url="<url>"

(function () {
    'use strict';

    function updateCompareBadge(count) {
        const badge = document.getElementById('compare-count');
        if (!badge) return;
        badge.textContent = count;
        if (count > 0) {
            badge.classList.remove('hidden');
        } else {
            badge.classList.add('hidden');
        }
    }

    function setButtonState(btn, inComparison) {
        btn.dataset.inComparison = inComparison ? 'true' : 'false';

        if (inComparison) {
            btn.classList.remove('bg-white', 'text-slate-600', 'border-slate-200');
            btn.classList.add('bg-cyan-50', 'text-cyan-700', 'border-cyan-200');
        } else {
            btn.classList.remove('bg-cyan-50', 'text-cyan-700', 'border-cyan-200');
            btn.classList.add('bg-white', 'text-slate-600', 'border-slate-200');
        }

        const label = btn.querySelector('.compare-label');
        if (label) label.textContent = inComparison ? 'In comparison' : 'Compare';
    }

    function getCookie(name) {
        const m = document.cookie.match(
            new RegExp('(?:^|;\\s*)' + name + '=([^;]+)')
        );
        return m ? decodeURIComponent(m[1]) : null;
    }

    // Find a CSRF token from anywhere on the page.
    function getCsrfToken() {
        const input = document.querySelector('[name=csrfmiddlewaretoken]');
        if (input && input.value) return input.value;
        return getCookie('csrftoken');
    }

    document.addEventListener('click', function (e) {
        const btn = e.target.closest('.compare-btn');
        if (!btn) return;

        // Prevent the parent <a> (product card link) from navigating.
        e.preventDefault();
        e.stopPropagation();

        const productId = btn.dataset.productId;
        const inComparison = btn.dataset.inComparison === 'true';
        const url = inComparison
            ? btn.dataset.removeUrl
            : btn.dataset.addUrl;

        if (!url) {
            // Developer mistake — button was rendered without URLs.
            console.error('[comparison.js] Missing data-add-url / data-remove-url on button.');
            return;
        }

        fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: new URLSearchParams({ product_id: productId }),
        })
            .then(function (r) {
                return r.json().then(function (data) {
                    return { ok: r.ok, data: data };
                });
            })
            .then(function (result) {
                const data = result.data;
                if (data.success) {
                    setButtonState(btn, !inComparison);
                    updateCompareBadge(data.count);
                } else {
                    alert(data.error || 'Something went wrong.');
                }
            })
            .catch(function () {
                alert('Network error. Please try again.');
            });
    });
})();