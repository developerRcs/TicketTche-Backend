import django_filters
from django.db.models import ExpressionWrapper, FloatField, F, Q
from django.db.models.functions import ACos, Cos, Radians, Sin

from .models import Event


class EventFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="filter_search")
    start_date_after = django_filters.DateTimeFilter(field_name="start_date", lookup_expr="gte")
    start_date_before = django_filters.DateTimeFilter(field_name="start_date", lookup_expr="lte")
    company = django_filters.UUIDFilter(field_name="company__id")
    city = django_filters.CharFilter(method="filter_city")
    lat = django_filters.NumberFilter(method="noop")
    lng = django_filters.NumberFilter(method="noop")
    radius_km = django_filters.NumberFilter(method="noop")

    class Meta:
        model = Event
        fields = ["status", "company", "start_date_after", "start_date_before"]

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(title__icontains=value)
            | Q(description__icontains=value)
            | Q(location__icontains=value)
            | Q(city__icontains=value)
        )

    def filter_city(self, queryset, name, value):
        return queryset.filter(
            Q(city__icontains=value) | Q(location__icontains=value)
        )

    def noop(self, queryset, name, value):
        return queryset

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)

        lat = self.data.get("lat")
        lng = self.data.get("lng")
        radius_km = self.data.get("radius_km", 50)

        if lat and lng:
            try:
                lat = float(lat)
                lng = float(lng)
                radius_km = float(radius_km)
                queryset = (
                    queryset.filter(
                        latitude__isnull=False,
                        longitude__isnull=False,
                    )
                    .annotate(
                        distance_km=ExpressionWrapper(
                            6371
                            * ACos(
                                Cos(Radians(lat))
                                * Cos(Radians(F("latitude")))
                                * Cos(Radians(F("longitude")) - Radians(lng))
                                + Sin(Radians(lat)) * Sin(Radians(F("latitude")))
                            ),
                            output_field=FloatField(),
                        )
                    )
                    .filter(distance_km__lte=radius_km)
                    .order_by("distance_km")
                )
            except (ValueError, TypeError):
                pass

        return queryset
