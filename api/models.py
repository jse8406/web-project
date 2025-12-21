from django.db import models

# Create your models here.

class StockInfo(models.Model):
    short_code = models.CharField(max_length=64, unique=True, db_index=True, verbose_name='단축코드')
    name = models.CharField(max_length=255, verbose_name='종목명')
    market = models.CharField(max_length=16, verbose_name='시장', blank=True, null=True)

    class Meta:
        db_table = 'stock_info'

    def __str__(self):
        return f"{self.name} ({self.short_code})"
