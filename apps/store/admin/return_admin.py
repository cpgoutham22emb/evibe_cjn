from django.contrib import admin
from ..models import ReturnRequest

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