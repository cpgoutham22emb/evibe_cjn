from django.db import models


class StoreConfiguration(models.Model):

    shipping_per_pant = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=149
    )

    cod_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=50
    )

    cod_enabled = models.BooleanField(
        default=True
    )

    max_cod_order_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=5000
    )

    return_window_days = models.PositiveIntegerField(
        default=7
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return "EVIBE Store Configuration"