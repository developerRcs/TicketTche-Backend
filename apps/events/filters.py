import django_filters

from .models import Event


class EventFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="filter_search")
    start_date_after = django_filters.DateTimeFilter(field_name="start_date", lookup_expr="gte")
    start_date_before = django_filters.DateTimeFilter(field_name="start_date", lookup_expr="lte")
    company = django_filters.UUIDFilter(field_name="company__id")

    class Meta:
        model = Event
        fields = ["status", "company", "start_date_after", "start_date_before"]

    def filter_search(self, queryset, name, value):
        from django.db.models import Q
        return queryset.filter(
            Q(title__icontains=value) | Q(description__icontains=value) | Q(location__icontains=value)
        )
