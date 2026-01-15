from django.shortcuts import render
from django.views.generic import ListView
from .models import Theme

class DailyThemeListView(ListView):
    model = Theme
    template_name = 'theme_list.html'
    context_object_name = 'themes'
    
    def get_queryset(self):
        # 최신 날짜순, 같은 날짜 내에서는 분석 시각 역순
        return Theme.objects.prefetch_related('stocks', 'stocks__stock').all()
