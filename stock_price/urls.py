from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
# router.register(r'items', views.ItemViewSet)

app_name = 'stock_price'

urlpatterns = [
    path('', include(router.urls)),
    path('stock/', views.StockRealtimeView.as_view(), name='stock_realtime'),
    path('stock/detail/', views.StockDetailView.as_view(), name='stock_detail_default'),
    path('stock/detail/<str:stock_code>/', views.StockDetailView.as_view(), name='stock_detail'),
    path('stock/ranking/', views.StockRankingView.as_view(), name='stock_ranking'),
]
