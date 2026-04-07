from django.contrib import admin
from .shipping_service import create_shipment
from .models import Product, Category, ProductVariant, ProductImage, Order, OrderItem, Refund, ReturnRequest
from .services import update_order_status, calculate_refund_amount, process_refund
from django.utils.html import format_html
from django.utils import timezone
from django.utils.safestring import mark_safe
import razorpay
from django.conf import settings
from django.contrib import messages
from django.urls import path
from django.utils.html import format_html
from django.shortcuts import redirect 
from django.core.exceptions import ValidationError

 
# ----------------------------
# PRODUCT ADMIN
# ----------------------------

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',) 
    ordering = ('name',)

class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0

    readonly_fields = ("image_preview",)

    def image_preview(self, obj):
        if obj.original_image:
            return format_html(
                '<img src="{}" width="100" />',
                obj.original_image.url
            )
        return "-"
    
    image_preview.short_description = "Preview"


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'product_code',
        'name',
        'category',
        'price',
        'offer_price',
        'is_best_seller',
        'best_seller_order',
        'is_featured',
        'featured_order',
        'is_new_arrival',
        'new_arrival_order',       
        'active',
    )

    list_editable = (
        'is_featured',
        'featured_order',
        'is_best_seller',
        'best_seller_order',
        'is_new_arrival',
        'new_arrival_order',
    )
    list_filter = (
        'active',
        'is_best_seller',
        'is_featured',
        'is_new_arrival',
    )

    search_fields = ('name', 'product_code')

    inlines = [ProductVariantInline, ProductImageInline]

    fieldsets = (
        ("Basic Information", {
            "fields": ("product_code", "name", "category", "slug")
        }),

        ("Pricing", {
            "fields": ("cost_price", "mrp", "price", "offer_price", "offer_end")
        }),

        ("Display Controls", {
            "fields": (
                "is_featured",
                "is_best_seller",
                "is_new_arrival",
                "show_countdown",
                "active",
            )
        }),
    )
# -----------------------
# ORDER ADMIN
# -----------------------
# Inline admin for order items
class OrderItemInline(admin.TabularInline):

    model = OrderItem

    extra = 0

    readonly_fields = (
        "product",
        "variant",
        "quantity",
        "price",
        "refunded_quantity",
    )

    fields = (
        "product",
        "variant",
        "quantity",
        "price",
        "returned_quantity",
        "refunded_quantity",
    )

def create_shipment_action(modeladmin, request, queryset):

    for order in queryset:

            if order.status != "PACKED":
                messages.error(request, f"Order {order.id} is not PACKED")
                continue

            if order.awb_code:
                messages.error(request, f"Order {order.id} already shipped")
                continue

            try:
                shipment = create_shipment(order)

                order.shipment_id = shipment["shipment_id"]
                order.awb_code = shipment["awb_code"]
                order.courier_name = shipment["courier_name"]
                order.save()

                # USE SERVICE (IMPORTANT)
                update_order_status(order, "SHIPPED")

            except ValidationError as e:
                messages.error(request, f"Order {order.id}: {str(e)}")


#  MARK REFUND PENDING ACTION
def mark_refund_pending(self, request, order_id):

    order = Order.objects.get(id=order_id)

    try:
        update_order_status(order, "REFUND_PENDING")

        # Create refund entry
        existing = Refund.objects.filter(order=order).exists()

        if not existing:
            Refund.objects.create(
                order=order,
                amount=calculate_refund_amount(order),
                status="INITIATED"
            )

        self.message_user(request, "Moved to Refund Pending", messages.SUCCESS)

    except Exception as e:
        self.message_user(request, str(e), messages.ERROR)

    return redirect(request.META.get("HTTP_REFERER"))

# APPROVE REFUND ACTION
def approve_refund(modeladmin, request, queryset):

    for order in queryset:

        try:
            if order.status != "REFUND_PENDING":
                raise ValidationError("Only REFUND_PENDING orders allowed")

            # Check if a refund is already initiated for this order
            existing = Refund.objects.filter(order=order, status__in=["INITIATED", "SUCCESS"]).exists()
            if existing:
                raise ValidationError("Refund already created")

            Refund.objects.create(
                order=order,
                amount=calculate_refund_amount(order),
                status="INITIATED"
            )

            messages.success(request, f"Refund approved for Order {order.id}")

        except ValidationError as e:
            messages.error(request, f"Order {order.id}: {str(e)}")


#def has_add_permission(self, request, obj=None):
#    return request.user.is_superuser


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'customer_name',
        'phone',
        'total_amount',
        'payment_method',
        'status',
        'return_status',
        'action_buttons',
        'created_at'
    )

    readonly_fields = (
        "subtotal",
        "shipping_charge",
        "total_amount",
        "razorpay_payment_id",
        "created_at",
        "paid_at",
        "shipped_at"
        #"status"
    )

    inlines = [OrderItemInline]

    # -----------------------------
    # 🔘 ACTION BUTTONS COLUMN
    # -----------------------------
    def action_buttons(self, obj):

        buttons = ""

        # START PROCESSING
        if obj.status == "PAID":
            buttons += f'<a class="button" href="start-processing/{obj.id}/">▶ Start</a> '

        # PACK
        elif obj.status == "PROCESSING":
            buttons += f'<a class="button" href="pack/{obj.id}/">📦 Pack</a> '

        # SHIP
        elif obj.status == "PACKED":
            buttons += f'<a class="button" href="ship/{obj.id}/">🚚 Ship</a> '

        elif obj.status == "RTO":
            buttons += f'<a class="button" href="return-received/{obj.id}/">Warehouse Received</a> '

        # REFUND FLOW
        elif obj.status == "RETURN_RECEIVED":
            buttons += f'<a class="button" href="refund-pending/{obj.id}/">💸 Refund</a> '

        # CANCEL OPTION
        if obj.status in ["CREATED", "PAID", "PROCESSING", "PACKED"]:
            buttons += f'<a style="background:red;color:white;padding:4px 8px;border-radius:4px;" href="cancel/{obj.id}/">❌ Cancel</a>'

        return mark_safe(buttons or "-")

    action_buttons.short_description = "Actions"

    # -----------------------------
    # 🔗 CUSTOM URLS
    # -----------------------------
    def get_urls(self):
        urls = super().get_urls()

        custom_urls = [
            path("start-processing/<int:order_id>/", self.admin_site.admin_view(self.start_processing)),
            path("pack/<int:order_id>/", self.admin_site.admin_view(self.pack_order)),
            path("ship/<int:order_id>/", self.admin_site.admin_view(self.ship_order)),
            path("return-received/<int:order_id>/", self.admin_site.admin_view(self.mark_return_received),),
            path("refund-pending/<int:order_id>/", self.admin_site.admin_view(self.mark_refund_pending)),
            path("cancel/<int:order_id>/", self.admin_site.admin_view(self.cancel_order)),
        ]

        return custom_urls + urls

     # -----------------------------
    # 📦 PROCESS ORDER
    # -----------------------------
    def start_processing(self, request, order_id):

        order = Order.objects.get(id=order_id)

        try:
            update_order_status(order, "PROCESSING")
            self.message_user(request, "Order moved to PROCESSING", messages.SUCCESS)

        except Exception as e:
            self.message_user(request, str(e), messages.ERROR)

        return redirect(request.META.get("HTTP_REFERER"))
    # -----------------------------
    # 📦 PACK ORDER
    # -----------------------------
    def pack_order(self, request, order_id):

        order = Order.objects.get(id=order_id)

        try:
            update_order_status(order, "PACKED")
            self.message_user(request, "Order Packed", messages.SUCCESS)

        except Exception as e:
            self.message_user(request, str(e), messages.ERROR)

        return redirect(request.META.get("HTTP_REFERER"))

    # -----------------------------
    # 🚚 SHIP ORDER (WITH SHIPMENT)
    # -----------------------------
    def ship_order(self, request, order_id):

        order = Order.objects.get(id=order_id)

        try:
            # 🔥 Create shipment if not exists
            if not order.awb_code:
                shipment = create_shipment(order)

                order.shipment_id = shipment["shipment_id"]
                order.awb_code = shipment["awb_code"]
                order.courier_name = shipment["courier_name"]
                order.save()

            update_order_status(order, "SHIPPED")

            self.message_user(request, "Order Shipped", messages.SUCCESS)

        except Exception as e:
            self.message_user(request, str(e), messages.ERROR)

        return redirect(request.META.get("HTTP_REFERER"))
    
    # -----------------------------
    # 💸 Mark return received
    # -----------------------------
    def mark_return_received(self, request, order_id):

        order = Order.objects.get(id=order_id)

        try:
            update_order_status(order, "RETURN_RECEIVED")
            self.message_user(request, "Order marked as RETURN_RECEIVED")

        except Exception as e:
            self.message_user(request, str(e), level=messages.ERROR)

        return redirect(request.META.get("HTTP_REFERER"))
    
    # -----------------------------
    # 💸 MOVE TO REFUND PENDING
    # -----------------------------
    def mark_refund_pending(self, request, order_id):

        order = Order.objects.get(id=order_id)

        try:
            # move order status
            update_order_status(order, "REFUND_PENDING")

            # prevent duplicate refund
            existing = Refund.objects.filter(order=order).exists()

            if not existing:

                refund_amount = calculate_refund_amount(order)

                Refund.objects.create(
                    order=order,
                    amount=refund_amount,
                    status="INITIATED"
                )

            self.message_user(request, "Refund initiated successfully")

        except Exception as e:
            self.message_user(request, str(e), level=messages.ERROR)

        return redirect(request.META.get("HTTP_REFERER"))
    
    # -----------------------------
    # 💸 Cancel 
    # -----------------------------

    def cancel_order(self, request, order_id):

        order = Order.objects.get(id=order_id)

        try:
            update_order_status(order, "CANCELLED")
            self.message_user(request, "Order Cancelled", messages.SUCCESS)

        except Exception as e:
            self.message_user(request, str(e), messages.ERROR)

        return redirect(request.META.get("HTTP_REFERER"))



@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'amount', 'colored_status','approved_by','approve_button', 'created_at')
    readonly_fields = ('order','razorpay_refund_id', 'status', 'created_at')
    search_fields = ('order__id',)
    list_filter = ('status',)

    def colored_status(self, obj):

        if obj.status == "SUCCESS":
            color = "green"
        elif obj.status == "FAILED":
            color = "red"
        else:
            color = "orange"

        return format_html(
            '<span style="color:white;padding:4px 8px;border-radius:6px;background-color:{};">{}</span>',
            color,
            obj.status
        )
    
    # -------------------
    # BUTTON COLUMN
    # -------------------
    def approve_button(self, obj):

        if obj.status == "INITIATED":
            return format_html(
                '<a style="background-color:#28a745;color:white;padding:6px 12px;border-radius:6px;text-decoration:none;" href="approve-refund/{}/">{}</a>',
                obj.id,
                "Approve"
            )

        elif obj.status == "FAILED":
            return format_html(
                '<a style="background-color:#ffc107;color:black;padding:6px 12px;border-radius:6px;text-decoration:none;" href="approve-refund/{}/">{}</a>',
                obj.id,
                "Retry"
            )

        return format_html(
            '<span style="color:green;font-weight:bold;">{}</span>',
            "✔ Refunded"
        )

    # -------------------
    # CUSTOM URL
    # -------------------
    def get_urls(self):
        urls = super().get_urls()

        custom_urls = [
            path(
                'approve-refund/<int:refund_id>/',
                self.admin_site.admin_view(self.process_refund_view),
            ),
        ]

        return custom_urls + urls

    # -------------------
    # BUTTON ACTION LOGIC
    # -------------------
    def process_refund_view(self, request, refund_id):

        if not request.user.is_superuser:
            self.message_user(request, "Only admin can approve refund", level=messages.ERROR)
            return redirect(request.META.get('HTTP_REFERER'))

        refund = Refund.objects.get(id=refund_id)

        try:
            if refund.status not in ["INITIATED", "FAILED"]:
                self.message_user(request, "Already processed", level=messages.ERROR)
                return redirect(request.META.get('HTTP_REFERER'))

            result = process_refund(refund.order, refund, None)

            refund.refresh_from_db()

            if result.status == "SUCCESS":

                refund.approved_by = request.user
                refund.save()

                # Optional: show how much refund still pending
                remaining = calculate_refund_amount(refund.order)

                if remaining > 0:
                    self.message_user(
                        request,
                        f"Refund SUCCESS. Remaining refundable amount: ₹{remaining}",
                        level=messages.SUCCESS
                    )
                else:
                    self.message_user(request, "Refund SUCCESS. All items refunded.", level=messages.SUCCESS)

            else:
                self.message_user(request, "Refund FAILED", level=messages.ERROR)

        except Exception as e:
            self.message_user(request, str(e), level=messages.ERROR)

        return redirect(request.META.get('HTTP_REFERER'))

class Media:
    js = ("admin/js/return_request.js",)

# ReturnRequestAdmin allows admin users to manage return requests for orders. It displays key information about each return request, including the associated order, 
# the specific item being returned, the quantity, and the status of the request. 
# Admins can filter return requests by status and search for specific requests using the order ID. 
# This interface helps streamline the process of handling returns and ensures that all return requests are properly tracked and managed.

@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'order',
        'order_item',
        'quantity',
        'status',
        'created_at'
    )

    list_filter = ('status',)
    search_fields = ('order__id',)

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ('order', 'order_item', 'quantity')
        return ()
    
    class Media:
        js = ("admin/js/return_request.js",)
