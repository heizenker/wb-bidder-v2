from __future__ import annotations

from typing import Any, Dict, List

from wb_bidder.core.client import WildberriesClient
from wb_bidder.analytics.feedback_rules import FeedbackRules


class FeedbackBot:
    """
    Бот для ответов на отзывы.

    Работает в двух режимах:
    - SAFE MODE: просто генерирует и выводит ответы (не отправляет в WB)
    - LIVE MODE: отправляет ответы через client.reply_feedback
    """

    def __init__(self, client: WildberriesClient | None = None, safe_mode: bool = True):
        self.client = client or WildberriesClient.from_env()
        self.safe_mode = safe_mode

    # --------------------------------------------------------------

    def fetch_unanswered(self, article_id: int, limit: int = 200) -> List[Dict[str, Any]]:
        """
        Забираем все неотвеченные отзывы по артикулу.
        """
        rows = self.client.get_feedbacks(
            article_id=article_id,
            is_answered=False,
            take=limit,
            skip=0,
        )
        return rows

    # --------------------------------------------------------------

    def process_feedbacks(self, article_id: int) -> List[Dict[str, Any]]:
        """
        Обрабатываем все неотвеченные отзывы:
        генерируем ответ, а в SAFE MODE только выводим/возвращаем.
        """
        rows = self.fetch_unanswered(article_id)

        results = []

        for fb in rows:
            text = FeedbackRules.make_reply(fb)

            item = {
                "feedback_id": fb.get("id"),
                "name": FeedbackRules._extract_name(fb),
                "rating": fb.get("productValuation"),
                "text": fb.get("text"),
                "reply": text,
            }

            results.append(item)

            if self.safe_mode:
                print(f"\n--- Отзыв #{fb.get('id')} ---")
                print(f"Оценка: {fb.get('productValuation')}")
                print(f"Текст: {fb.get('text')}")
                print(f"Ответ: {text}")
                print("--------------------------")

            else:
                # Боевой режим — отправка ответа
                self.client.reply_feedback(
                    feedback_id=fb.get("id"),
                    text=text,
                )

        return results


# Мини-тест
if __name__ == "__main__":
    bot = FeedbackBot(safe_mode=True)

    # Пример: обработать отзывы по одному артикулу
    # ЗАМЕНИ на свой артикул!
    ARTICLE_ID = 12345678

    print(f"Обработка неотвеченных отзывов по артикулу {ARTICLE_ID}...")
    bot.process_feedbacks(ARTICLE_ID)


