from django.db import models
from stock_price.models import StockInfo

class Theme(models.Model):
    """
    하루의 시장 테마를 정의하는 모델.
    예: '2차전지', '초전도체', 'AI 반도체' 등
    """
    date = models.DateField(auto_now_add=True, db_index=True, verbose_name="생성 일자")
    name = models.CharField(max_length=255, verbose_name="테마명")
    description = models.TextField(verbose_name="테마 설명/요약")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="분석 시각")

    class Meta:
        db_table = 'daily_theme'
        ordering = ['-date', '-created_at']
        verbose_name = "일일 테마"
        verbose_name_plural = "일일 테마 목록"

    def __str__(self):
        return f"[{self.date}] {self.name}"

class ThemeStock(models.Model):
    """
    특정 테마에 속한 종목과 편입 사유를 저장하는 모델 (N:M 해소)
    """
    theme = models.ForeignKey(Theme, on_delete=models.CASCADE, related_name='stocks', verbose_name="테마")
    stock = models.ForeignKey(StockInfo, on_delete=models.CASCADE, related_name='themes', verbose_name="종목")
    reason = models.TextField(verbose_name="편입 사유", blank=True, null=True)

    class Meta:
        db_table = 'theme_stock'
        verbose_name = "테마 편입 종목"
        verbose_name_plural = "테마 편입 종목 목록"

    def __str__(self):
        return f"{self.theme.name} - {self.stock.name}"
