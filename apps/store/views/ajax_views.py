from django.http import JsonResponse
from apps.store.models import OrderItem


def get_order_items(request):

    order_id = request.GET.get("order_id")

    items = OrderItem.objects.filter(order_id=order_id)

    data = [
        {
            "id": item.id,
            "text": f"{item.product.name} (Qty: {item.quantity})"
        }
        for item in items
    ]

    return JsonResponse({"items": data})