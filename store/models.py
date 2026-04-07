from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
from django.utils.text import slugify
from django.db import models, transaction
from django.db.models import Sum
from django.conf import settings
from datetime import timedelta
from django.utils import timezone
from django.core.exceptions import ValidationError
import os

# Adding the image field to the product model to allow for product images to be uploaded and displayed on the website. The image will be stored in the 'products/' directory within the media folder.
# The 'active' field is added to allow for products to be marked as active or inactive, which can be useful for managing inventory and displaying only available products on the website. The 'created_at' field is added to keep track of when each product was created, which can be useful for sorting and filtering products based on their creation date.

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def save(self, *args, **kwargs):
        self.name = self.name.strip().lower() 
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Product(models.Model):
    product_code = models.CharField(max_length=100, unique=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name="products"
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    
    cost_price = models.DecimalField(max_digits=10, decimal_places=2)
    mrp = models.DecimalField(max_digits=10, decimal_places=2)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    
    offer_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    offer_end = models.DateTimeField(null=True, blank=True)
    
    #  Admin control flags
    is_featured = models.BooleanField(default=False)
    featured_order = models.PositiveIntegerField(null=True, blank=True)

    is_best_seller = models.BooleanField(default=False)
    best_seller_order = models.PositiveIntegerField(null=True, blank=True)

    is_new_arrival = models.BooleanField(default=False)
    new_arrival_order = models.PositiveIntegerField(null=True, blank=True)
    
    show_countdown = models.BooleanField(default=False)

    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_offer_active(self):
        return (
            self.offer_price and
            self.offer_end and
            self.offer_end > timezone.now()
        )

    def get_final_price(self):
        if self.is_offer_active():
            return self.offer_price
        return self.price
    
    def get_discount_percentage(self):
        final_price = self.get_final_price()

        if self.mrp > 0:
            discount = ((self.mrp - final_price) / self.mrp) * 100
            return round(discount)

        return 0

    def get_discount_amount(self):
        if self.is_offer_active():
            return self.mrp - self.offer_price
        return self.mrp - self.price

    def save(self, *args, **kwargs):
        base_slug = slugify(f"{self.product_code}-{self.name}")
        slug = base_slug
        counter = 1

        while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        self.slug = slug

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    size = models.CharField(max_length=10)
    stock = models.IntegerField()

    def __str__(self):
        return f"{self.product.name} - {self.size}"
    

# ProductImage model handles:
# 1. Storing the original uploaded product image.
# 2. Automatically generating optimized WebP images (400px, 800px, 1200px).
# 3. Saving optimized image paths inside a JSONField for fast template access.
# 
# Why this approach?
# - Keeps original image untouched.
# - Improves performance using optimized images.
# - Avoids template path manipulation.
# - Centralizes image processing logic inside the model (production-safe).
class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images"
    )

    original_image = models.ImageField(
        upload_to="products/%Y/%m/%d/original/",
        null=True,
        blank=True
    )

    optimized = models.JSONField(blank=True, null=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        from .utils import generate_optimized_images
        generate_optimized_images(self)

    def __str__(self):
        return f"{self.product.name}"

# -----------------------
# ORDER AND ORDER ITEM MODELS
# -----------------------
class Order(models.Model):
    STATUS_CHOICES = [
        ('CREATED', 'Created'),
        ('PAID', 'Paid'),
        ('PROCESSING', 'Processing'),
        ('PACKED', 'Packed'),
        ('SHIPPED', 'Shipped'),
        ('OUT_FOR_DELIVERY', 'Out For Delivery'),
        ('DELIVERED', 'Delivered'),
        ('RTO', 'Returned To Origin'),
        ('CANCELLED', 'Cancelled'),
    ]

    PAYMENT_CHOICES = [
        ('COD', 'Cash on Delivery'),
        ('ONLINE', 'Online Payment'),
    ]

    RETURN_STATUS = [
    ("NONE", "None"),
    ("IN_PROGRESS", "Return In Progress"),
    ("PARTIAL_RETURNED", "Partially Returned"),
    ("FULLY_RETURNED", "Fully Returned"),
    ]

    return_status = models.CharField(
        max_length=20,
        choices=RETURN_STATUS,
        default="NONE"
    )


    customer_name = models.CharField(max_length=200)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20)
    address = models.TextField()
    city = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)

    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='CREATED', db_index=True)

    #  PRICE FIELDS (MOVE HERE)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # RAZORPAY FIELDS
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=200, blank=True, null=True)
    
    refund_processed = models.BooleanField(default=False)
    paid_at = models.DateTimeField(blank=True, null=True)

    # Shipping details
    courier_name = models.CharField(max_length=100, blank=True, null=True)
    awb_code = models.CharField(max_length=100, blank=True, null=True)
    
    shipment_id = models.CharField(max_length=100, blank=True, null=True)

    shipped_at = models.DateTimeField(blank=True, null=True)

    shipment_status = models.CharField(max_length=50, blank=True, null=True)

    tracking_url = models.URLField(blank=True, null=True)

    delivered_at = models.DateTimeField(blank=True, null=True)

    # RTO details
    rto_reason = models.CharField(max_length=200, blank=True, null=True)

    rto_date = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    stock_restored = models.BooleanField(default=False)

    last_updated_at = models.DateTimeField(auto_now=True)

    stock_deducted = models.BooleanField(default=False)

    def __str__(self):
        return f"Order #{self.id} - {self.customer_name}"
    
# The OrderItem model represents individual items within an order, linking to the main Order and the specific ProductVariant. It tracks the quantity ordered, price, and any returns or refunds associated with that item. The save method includes validation to prevent invalid return or refund quantities, ensuring data integrity. The refundable_quantity method calculates how many units of the item are still eligible for refund based on returns and previous refunds.
class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, null=True, blank=True)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    returned_quantity = models.IntegerField(default=0)
    refunded_quantity = models.IntegerField(default=0)

    def save(self, *args, **kwargs):

        # Prevent warehouse staff entering invalid returned quantity
        if self.returned_quantity > self.quantity:
            raise ValueError("Returned quantity cannot exceed ordered quantity")

        # Prevent refund exceeding returned quantity
        if self.refunded_quantity > self.returned_quantity:
            raise ValueError("Refunded quantity cannot exceed returned quantity")

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} - {self.variant.size} x {self.quantity}"
    
    def refundable_quantity(self):
        return self.returned_quantity - self.refunded_quantity

# Refund   
class Refund(models.Model):

    STATUS_CHOICES = [
        ('INITIATED', 'Initiated'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    razorpay_refund_id = models.CharField(max_length=100, blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES)

    created_at = models.DateTimeField(auto_now_add=True)

    refunded_at = models.DateTimeField(blank=True, null=True)

    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"Refund #{self.id} - Order {self.order.id}"
    
#   The ReturnRequest model manages product return requests, linking to the Order and specific OrderItem. It tracks the quantity being returned, the status of the return process, and any inspection notes. The save method includes validation to ensure that return quantities do not exceed what was ordered and that status transitions follow a defined workflow. When a return is approved, it updates the returned quantity on the OrderItem and triggers an order status update to reflect the return process.
class ReturnRequest(models.Model):

    STATUS_CHOICES = [
        ('REQUESTED', 'Requested'),
        ('APPROVED', 'Approved'),
        ('PICKED', 'Picked'),
        ('RECEIVED', 'Received'),

        ('QC_APPROVED', 'QC Approved'),
        ('QC_REJECTED', 'QC Rejected'),

        ('REJECTED', 'Rejected'),
    ]

    order = models.ForeignKey("Order", on_delete=models.CASCADE)
    order_item = models.ForeignKey("OrderItem", on_delete=models.CASCADE)

    quantity = models.PositiveIntegerField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='REQUESTED'
    )

    inspection_notes = models.TextField(blank=True, null=True)

    refund_processed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    processed_at = models.DateTimeField(blank=True, null=True)


    def save(self, *args, **kwargs):

        from store.services import update_return_status, log_order_event
        from store.models import Refund, OrderItem

        with transaction.atomic():

            is_new = self.pk is None

            # -----------------------------
            # BASIC VALIDATION
            # -----------------------------
            if self.quantity <= 0:
                raise ValidationError("Return quantity must be greater than zero")

            if self.quantity > self.order_item.quantity:
                raise ValidationError("Return qty cannot exceed ordered qty")

            # -----------------------------
            # RETURN WINDOW VALIDATION
            # -----------------------------
            if not self.order.delivered_at:
                raise ValidationError("Return allowed only after delivery")

            return_deadline = self.order.delivered_at + timedelta(days=5)

            if timezone.now() > return_deadline:
                raise ValidationError("Return window closed (5 days)")

            # -----------------------------
            # CUMULATIVE RETURN VALIDATION
            # -----------------------------
            existing_qty = ReturnRequest.objects.filter(
                order_item=self.order_item
            ).exclude(pk=self.pk).aggregate(
                total=Sum("quantity")
            )["total"] or 0

            if existing_qty + self.quantity > self.order_item.quantity:

                remaining = self.order_item.quantity - existing_qty

                raise ValidationError(
                    f"Return exceeds ordered quantity. Remaining allowed: {remaining}"
                )

            # -----------------------------
            # STATUS TRANSITION VALIDATION
            # -----------------------------
            old_status = None

            if self.pk is not None:

                old = ReturnRequest.objects.select_for_update().get(pk=self.pk)

                old_status = old.status

                allowed_transitions = {
                    "REQUESTED": ["APPROVED", "REJECTED"],
                    "APPROVED": ["PICKED"],
                    "PICKED": ["RECEIVED"],
                    "RECEIVED": ["QC_APPROVED", "QC_REJECTED"],
                    "QC_APPROVED": [],
                    "QC_REJECTED": [],
                    "REJECTED": []
                }

                if self.status != old.status:

                    if self.status not in allowed_transitions.get(old.status, []):

                        raise ValidationError(
                            f"Invalid transition: {old.status} → {self.status}"
                        )

            # -----------------------------
            # QC APPROVED FLOW
            # -----------------------------
            if (old_status != "QC_APPROVED") and self.status == "QC_APPROVED":

                order_item = OrderItem.objects.select_for_update().get(
                    id=self.order_item.id
                )

                if order_item.returned_quantity + self.quantity > order_item.quantity:

                    raise ValidationError(
                        "Total returned exceeds ordered quantity"
                    )

                # update returned quantity
                order_item.returned_quantity += self.quantity
                order_item.save()

                # update order return status
                update_return_status(self.order)

                # -----------------------------
                # AUTO CREATE REFUND RECORD
                # -----------------------------
                refund_amount = self.quantity * order_item.price

                existing = Refund.objects.filter(
                    order=self.order,
                    status="INITIATED",
                    amount=refund_amount
                ).exists()

                if not existing:

                    Refund.objects.create(
                        order=self.order,
                        amount=refund_amount,
                        status="INITIATED"
                    )

                self.processed_at = timezone.now()

                # -----------------------------
                # TIMELINE LOG
                # -----------------------------
                log_order_event(
                    self.order,
                    "RETURN",
                    f"{self.quantity} item(s) returned for {order_item.product.name}"
                )

            super().save(*args, **kwargs)

            # -----------------------------
            # MARK RETURN IN PROGRESS
            # -----------------------------
            if is_new:

                self.order.return_status = "IN_PROGRESS"
                self.order.save()


    def __str__(self):

        return f"Return #{self.id} | Order {self.order.id} | Qty {self.quantity} | {self.status}" 
    
class OrderTimeline(models.Model):

    EVENT_TYPES = [
        ('CREATED', 'Order Created'),
        ('STATUS_CHANGED', 'Status Changed'),
        ('PAYMENT', 'Payment'),
        ('SHIPMENT', 'Shipment'),
        ('RETURN', 'Return'),
        ('REFUND', 'Refund'),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="timeline")

    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)

    message = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.order.id} - {self.event_type}"