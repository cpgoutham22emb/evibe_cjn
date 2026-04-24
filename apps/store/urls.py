from django.urls import path

# PRODUCT
from .views.product_views import (
    product_list,
    product_detail,
    category_products
)

# CART
from .views.cart_views import (
    cart_detail,
    add_to_cart,
    remove_from_cart,
    increase_quantity,
    decrease_quantity
)

# CHECKOUT
from .views.checkout_views import (
    checkout,
    order_success
)

# ORDERS
from .views.order_views import (
    my_orders,
    track_order
)

# WEBHOOKS
from .views.webhook_views import (
    payment_success,
    razorpay_webhook,
    courier_webhook,
    
)

# AJAX
from .views.ajax_views import (
    get_order_items
)



urlpatterns = [

    # PRODUCT
    path("", product_list, name="product_list"),
    path("product/<slug:slug>/", product_detail, name="product_detail"),
    path("category/<slug:slug>/", category_products, name="category_products"),

    # CART
    path("cart/", cart_detail, name="cart"),
    path("cart/add/", add_to_cart, name="add_to_cart"),
    path("cart/remove/<int:variant_id>/", remove_from_cart, name="remove_from_cart"),
    path("cart/increase/<int:variant_id>/", increase_quantity, name="increase_quantity"),
    path("cart/decrease/<int:variant_id>/", decrease_quantity, name="decrease_quantity"),

    # CHECKOUT
    path("checkout/", checkout, name="checkout"),
    path("order-success/", order_success, name="order_success"),

    # ORDERS
    path("track-order/<int:order_id>/", track_order, name="track_order"),
    path("my-orders/", my_orders, name="my_orders"),

    # WEBHOOKS
    path('payment-success/', payment_success, name='payment_success'),
    path("webhook/razorpay/", razorpay_webhook, name="razorpay_webhook"),
    path("courier/webhook/", courier_webhook, name="courier_webhook"),

    # AJAX
    path("ajax/order-items/", get_order_items, name="get_order_items"),
]   