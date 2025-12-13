from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
# router.register(r'items', views.ItemViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('hello/', views.hello_world, name='hello_world'),
]
