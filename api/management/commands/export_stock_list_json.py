from django.core.management.base import BaseCommand
from api.models import StockInfo
import json
from pathlib import Path

class Command(BaseCommand):
    help = 'Export all stock names and short codes to a JSON file for frontend autocomplete.'

    def add_arguments(self, parser):
        parser.add_argument('--output', type=str, default='api/static/api/stock_list.json', help='Output JSON file path')

    def handle(self, *args, **options):
        output_path = Path(options['output'])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        stocks = StockInfo.objects.all().values('name', 'short_code')
        data = {"results": list(stocks)}
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.stdout.write(self.style.SUCCESS(f"Exported {len(data['results'])} stocks to {output_path}"))
