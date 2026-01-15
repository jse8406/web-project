from django.contrib import admin
from .models import Theme, ThemeStock

class ThemeStockInline(admin.TabularInline):
    model = ThemeStock
    extra = 1

@admin.register(Theme)
class ThemeAdmin(admin.ModelAdmin):
    list_display = ('date', 'name', 'created_at')
    inlines = [ThemeStockInline]

@admin.register(ThemeStock)
class ThemeStockAdmin(admin.ModelAdmin):
    list_display = ('theme', 'stock', 'reason')
    list_filter = ('theme__date',)
