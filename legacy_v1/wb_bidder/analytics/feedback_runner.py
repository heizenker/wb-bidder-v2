from __future__ import annotations

import time

from wb_bidder.analytics.feedback_bot import FeedbackBot
from wb_bidder.config import CONTROLLED_ITEMS


class FeedbackRunner:
    """
    Запуск автоответчика по всем артикулам.
    """

    def __init__(self, safe_mode: bool = True, interval_sec: int = 300):
        """
        safe_mode=True  — ответы НЕ отправляются (только вывод)
        safe_mode=False — боевой режим (отправка ответов)
        """
        self.safe_mode = safe_mode
        self.interval_sec = interval_sec
        self.bot = FeedbackBot(safe_mode=safe_mode)

    # ----------------------------------------------------------

    def run_once(self):
        """
        Один цикл обработки всех товаров.
        """
        print("\n=== FEEDBACK RUNNER: START ===\n")

        # CONTROLLED_ITEMS — массив словарей
        # [{'nmId': 12345}, {'nmId': 67890}, ...]
        for item in CONTROLLED_ITEMS:
            nm = item.get("nmId") or item.get("nm") or item.get("id")
            if not nm:
                continue

            print(f"--- Артикул {nm} ---")

            results = self.bot.process_feedbacks(article_id=nm)

            print(f"Обработано отзывов: {len(results)}\n")

        print("=== FEEDBACK RUNNER: END ===\n")

    # ----------------------------------------------------------

    def run_forever(self):
        """
        Бесконечный цикл обработки отзывов раз в interval_sec секунд.
        """
        while True:
            self.run_once()
            time.sleep(self.interval_sec)


# ----------------------------------------------------------
# Ручной запуск
# ----------------------------------------------------------

if __name__ == "__main__":
    # SAFE MODE — ничего не отправляет, только пишет в консоль
    runner = FeedbackRunner(
        safe_mode=True,
        interval_sec=300,  # каждые 5 минут
    )

    runner.run_once()


