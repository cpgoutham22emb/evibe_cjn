from django.http import HttpResponse
from django.urls import include, path
from . import views
from .views import product_list,product_detail, checkout, order_success, cart_detail, add_to_cart, remove_from_cart, payment_success, razorpay_webhook, get_order_items

urlpatterns = [
    path("", product_list, name="product_list"),

    path('category/<slug:slug>/', views.category_products, name='category_products'),
    path("product/<slug:slug>/", product_detail, name="product_detail"),
    path('cart/', cart_detail, name='cart'),
    path('cart/add/', add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:variant_id>/', remove_from_cart, name='remove_from_cart'),

    path('checkout/', checkout, name='checkout'),
    path('order-success/', order_success, name='order_success'),
    path('payment-success/', payment_success, name='payment_success'),
    path('webhook/razorpay/', razorpay_webhook, name='razorpay_webhook'),
    path('cart/increase/<int:variant_id>/', views.increase_quantity, name='increase_quantity'),
    path('cart/decrease/<int:variant_id>/', views.decrease_quantity, name='decrease_quantity'),
    path("track-order/<int:order_id>/", views.track_order, name="track_order"),
    path("my-orders/", views.my_orders, name="my_orders"),
    path("courier/webhook/", views.courier_webhook, name="courier_webhook"),
    path("ajax/order-items/", get_order_items, name="get_order_items"),

]

