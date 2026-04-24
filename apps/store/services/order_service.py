from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from ..models import Order, ProductVariant

from .inventory_service import restore_full_stock
from .timeline_service import log_order_event

def validate_order_transition(old_status, new_status):

    allowed_transitions = {
        "CREATED": ["PAID", "CANCELLED"],
        "PAID": ["PROCESSING", "CANCELLED"],
        "PROCESSING": ["PACKED", "CANCELLED"],
        "PACKED": ["SHIPPED", "CANCELLED"],
        "SHIPPED": ["OUT_FOR_DELIVERY", "RTO"],
        "OUT_FOR_DELIVERY": ["DELIVERED", "RTO"],
        "DELIVERED": [],
        "RTO": [],
        "CANCELLED": []
    }

    if new_status not in allowed_transitions.get(old_status, []):
        raise ValidationError(f"Invalid transition: {old_status} → {new_status}")
    

def update_order_status(order, new_status):

    if new_status == "PAID" and order.status == "PAID":
        raise ValidationError("Order already paid")


    with transaction.atomic():

        #  LOCK ORDER FIRST
        order = Order.objects.select_for_update().get(id=order.id)
        old_status = order.status

        if old_status == new_status:
            return

        validate_order_transition(old_status, new_status)
        # -------------------
        # Paid Timestamp
        # -------------------
        if new_status == "PAID":

            order.paid_at = timezone.now()

        # -------------------
        # STOCK DEDUCTION (PAID)
        # -------------------
        if new_status == "PACKED":

            for item in order.items.select_related('variant'):

                variant = item.variant
                variant = ProductVariant.objects.select_for_update().get(id=variant.id)

                if variant.stock < item.quantity:
                    raise ValidationError("Insufficient stock")

                variant.stock -= item.quantity
                variant.save()
            
            order.stock_deducted = True

        # -------------------
        # SHIPPING VALIDATION
        # -------------------
        if new_status == "SHIPPED":

            order.shipped_at = timezone.now()

            if not order.awb_code:
                raise ValidationError("AWB code is required before shipping")

            if not order.courier_name:
                raise ValidationError("Courier name is required before shipping")
            
        # -------------------
        # DELIVERY CONFIRMATION
        # -------------------
        if new_status == "DELIVERED":

            if not order.shipped_at:
                raise ValidationError("Order cannot be delivered before shipping")

            order.delivered_at = timezone.now()
            
        # -------------------
        # STOCK RESTORE (CANCELLED)
        # -------------------
        if new_status == "CANCELLED":

            if not order.stock_deducted:
                return  # No stock deduction, so no need to restore

            if order.stock_restored:
                raise ValidationError("Stock already restored")

            restore_full_stock(order)
            order.stock_restored = True

        # -------------------
        # RTO FLOW
        # -------------------
        if new_status == "RTO":

            order.rto_date = timezone.now()
            order.return_status = "FULLY_REFUNDED"
            log_order_event(
                order,
                "STATUS_CHANGED",
                f"{old_status} → RTO"
            )

        # -------------------
        # SAVE STATUS
        # -------------------
        order.status = new_status
        order.save()

        # -------------------
        # TIMELINE
        # -------------------
        log_order_event(
            order,
            "STATUS_CHANGED",
            f"{old_status} → {new_status}"
        )