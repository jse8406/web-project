from django.urls import path
from .views import DailyThemeListView, ThemeHeatmapView

app_name = 'stock_theme'

urlpatterns = [
    path('', DailyThemeListView.as_view(), name='daily_theme_list'),
    path('heatmap/', ThemeHeatmapView.as_view(), name='theme_heatmap'),
]
