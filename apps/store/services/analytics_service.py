from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta

from apps.store.models import Order, OrderItem, Refund, ReturnRequest, ProductVariant


def get_revenue_today():
    today = timezone.now().date()

    revenue = (
        Order.objects.filter(
            created_at__date=today,
            status="DELIVERED"
        ).aggregate(total=Sum("total_amount"))["total"] or 0
    )

    return revenue


def get_orders_today():
    today = timezone.now().date()

    return Order.objects.filter(
        created_at__date=today
    ).count()


def get_pending_orders():
    return Order.objects.filter(
        status__in=["CREATED", "PAID", "PROCESSING", "PACKED"]
    ).count()


def get_in_transit_orders():
    return Order.objects.filter(
        status__in=["SHIPPED", "OUT_FOR_DELIVERY"]
    ).count()


def get_returns_count():
    return ReturnRequest.objects.count()


def get_refunds_total():
    return (
        Refund.objects.filter(status="SUCCESS")
        .aggregate(total=Sum("amount"))["total"] or 0
    )


def get_top_products(limit=10):

    return (
        OrderItem.objects.values("product__name")
        .annotate(total_sold=Sum("quantity"))
        .order_by("-total_sold")[:limit]
    )


def get_low_stock_products():

    return ProductVariant.objects.filter(
        stock__lt=5
    ).select_related("product")

def get_orders_trend(days=7):

    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days - 1)

    data = (
        Order.objects.filter(created_at__date__gte=start_date)
        .values("created_at__date")
        .annotate(count=Count("id"))
        .order_by("created_at__date")
    )

    trend = {}

    for i in range(days):
        date = start_date + timedelta(days=i)
        trend[date] = 0

    for row in data:
        trend[row["created_at__date"]] = row["count"]

    labels = [d.strftime("%d %b") for d in trend.keys()]
    values = list(trend.values())

    return labels, values

def get_order_status_distribution():

    data = (
        Order.objects
        .values("status")
        .annotate(total=Count("id"))
        .order_by()
    )

    labels = []
    values = []

    for row in data:
        labels.append(row["status"])
        values.append(row["total"])

    return labels, values

def get_revenue_trend(days=7):

    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days - 1)

    data = (
        Order.objects.filter(
            created_at__date__gte=start_date,
            status="DELIVERED"   # ✅ only completed revenue
        )
        .values("created_at__date")
        .annotate(total=Sum("total_amount"))
        .order_by("created_at__date")
    )

    trend = {}

    for i in range(days):
        date = start_date + timedelta(days=i)
        trend[date] = 0

    for row in data:
        trend[row["created_at__date"]] = float(row["total"] or 0)

    labels = [d.strftime("%d %b") for d in trend.keys()]
    values = list(trend.values())

    return labels, values