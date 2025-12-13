from rest_framework import viewsets, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth.models import User
from .serializers import UserSerializer


@api_view(['GET'])
def hello_world(request):
    """
    간단한 테스트용 API 엔드포인트
    """
    return Response({
        'message': 'Hello, World!',
        'status': 'success'
    })


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    사용자 목록 조회를 위한 ViewSet (읽기 전용)
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer


# 예시: 커스텀 모델 ViewSet
# from .models import Item
# from .serializers import ItemSerializer
#
# class ItemViewSet(viewsets.ModelViewSet):
#     queryset = Item.objects.all()
#     serializer_class = ItemSerializer
