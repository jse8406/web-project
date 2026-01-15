from django.urls import path
from .views import DailyThemeListView

app_name = 'stock_theme'

urlpatterns = [
    path('', DailyThemeListView.as_view(), name='daily_theme_list'),
]
