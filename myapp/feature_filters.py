from collections import defaultdict
from .models import Feature

# A cap on how many values a user can request for a single feature
MAX_VALUES_PER_FEATURE = 50

def parse_feature_filters(request, known_feature_slugs):
    """
    Read feature_value selections from the request's query string.
    """
    selections = defaultdict(list)

    for name, values in request.GET.lists():
        if name not in known_feature_slugs:
            continue

        seen = set()
        for raw in values:
            value_slug = raw.strip().lower()
            # if the value is empty
            if not value_slug:
                continue
            if value_slug in seen:
                continue
            seen.add(value_slug)
            selections[name].append(value_slug)

            if len(selections[name]) >= MAX_VALUES_PER_FEATURE:
                break

    return {
        feature_slug: value_slugs
        for feature_slug, value_slugs in selections.items()
        if value_slugs
    }

def build_filter_groups(selections):
    """Assemble the data the sidebar template needs"""
    features = (
        Feature.objects
        .filter(is_filterable=True)
        .prefetch_related('values')
        .order_by('display_order', 'name')
    )
    groups = []
    for feature in features:
        values = list(feature.values.all())
        if not values:
            continue

        selected_slugs = set(selections.get(feature.slug, []))
        groups.append({
            'feature': feature,
            'values': values,
            'selected_slugs': selected_slugs
        })
    return groups

def apply_feature_filters(queryset, selections):
    """
    Narrow 'queryset' to products that match the given feature selections
    """
    if not selections:
        return queryset

    for feature_slug, value_slugs in selections.items():
        if not value_slugs:
            continue
        queryset = queryset.filter(
            features__feature__slug=feature_slug,
            features__value__slug__in=value_slugs,
        )
    return queryset.distinct()

def build_sidebar_context(request, queryset):
    """Run the full feature-filter pipeline for a request"""
    known_feature_slugs = set(
        Feature.objects
        .filter(is_filterable=True)
        .values_list('slug', flat=True)
    )
    selections = parse_feature_filters(request, known_feature_slugs)
    queryset = apply_feature_filters(queryset, selections)
    filter_groups = build_filter_groups(selections)

    sidebar_context = {
        'selections': selections,
        'filter_groups': filter_groups
    }

    return queryset, sidebar_context