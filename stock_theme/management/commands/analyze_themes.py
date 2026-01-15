from django.core.management.base import BaseCommand
from stock_theme.services import ThemeAnalyzeService
import asyncio

class Command(BaseCommand):
    help = 'Analyzes daily stock themes using News and KIS data via Upstage LLM'

    def handle(self, *args, **options):
        self.stdout.write("Starting Theme Analysis...")
        service = ThemeAnalyzeService()
        
        # Django Command는 기본적으로 동기이므로 async 메서드를 실행하기 위해 loop 사용
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(service.analyze_and_save_themes())
            self.stdout.write(self.style.SUCCESS('Successfully completed theme analysis.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error occurred: {e}'))
        finally:
            loop.close()
