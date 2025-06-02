import requests
from datetime import datetime, timedelta
from collections import Counter
from typing import List, Dict, Optional
import json
from sqlalchemy.orm import Session
from sqlalchemy import func
import sys
import os

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.models import Vacancy
from config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_API_URL, ANALYTICS_PROMPT

class DeepseekAnalyzer:
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }

    def analyze_vacancies(self, db: Session) -> str:
        """
        Анализирует вакансии с помощью DeepSeek AI
        """
        # Получаем данные за последнюю неделю
        week_ago = datetime.now() - timedelta(days=7)
        current_vacancies = db.query(Vacancy).filter(
            Vacancy.created_at >= week_ago
        ).all()

        # Получаем данные за предыдущую неделю для сравнения
        two_weeks_ago = datetime.now() - timedelta(days=14)
        previous_vacancies = db.query(Vacancy).filter(
            Vacancy.created_at >= two_weeks_ago,
            Vacancy.created_at < week_ago
        ).all()

        # Подготавливаем данные для анализа
        tech_stats = self._calculate_tech_stats(current_vacancies)
        regional_stats = self._calculate_regional_stats(current_vacancies)
        changes = self._calculate_changes(current_vacancies, previous_vacancies)

        # Форматируем данные для промпта
        prompt_data = ANALYTICS_PROMPT.format(
            vacancies=self._format_vacancies(current_vacancies[:10]),  # Первые 10 вакансий для примера
            tech_stats=json.dumps(tech_stats, ensure_ascii=False, indent=2),
            regional_stats=json.dumps(regional_stats, ensure_ascii=False, indent=2),
            changes=json.dumps(changes, ensure_ascii=False, indent=2)
        )

        # Отправляем запрос к DeepSeek
        response = self._send_to_deepseek(prompt_data)
        return response

    def _calculate_tech_stats(self, vacancies: List[Vacancy]) -> Dict[str, int]:
        """Подсчитывает упоминания технологий"""
        tech_counter = Counter()
        for vacancy in vacancies:
            if vacancy.tech_stack:
                techs = [t.strip().lower() for t in vacancy.tech_stack.split(',')]
                tech_counter.update(techs)
        return dict(tech_counter.most_common())

    def _calculate_regional_stats(self, vacancies: List[Vacancy]) -> Dict[str, int]:
        """Подсчитывает распределение по регионам"""
        region_counter = Counter()
        for vacancy in vacancies:
            if vacancy.city:
                region_counter[vacancy.city] += 1
        return dict(region_counter.most_common())

    def _calculate_changes(self, current: List[Vacancy], previous: List[Vacancy]) -> Dict:
        """Вычисляет изменения между периодами"""
        current_tech_stats = self._calculate_tech_stats(current)
        previous_tech_stats = self._calculate_tech_stats(previous)
        
        return {
            "total_vacancies": {
                "current": len(current),
                "previous": len(previous),
                "change_percent": ((len(current) - len(previous)) / len(previous) * 100) if previous else 0
            },
            "avg_salary": self._calculate_salary_changes(current, previous),
            "top_techs_current": dict(sorted(current_tech_stats.items(), key=lambda x: x[1], reverse=True)[:10]),
            "top_techs_previous": dict(sorted(previous_tech_stats.items(), key=lambda x: x[1], reverse=True)[:10])
        }

    def _calculate_salary_changes(self, current: List[Vacancy], previous: List[Vacancy]) -> Dict:
        """Вычисляет изменения в зарплатах"""
        def avg_salary(vacancies):
            salaries_from = [v.salary_from for v in vacancies if v.salary_from]
            salaries_to = [v.salary_to for v in vacancies if v.salary_to]
            return {
                "from": sum(salaries_from) / len(salaries_from) if salaries_from else 0,
                "to": sum(salaries_to) / len(salaries_to) if salaries_to else 0
            }

        current_avg = avg_salary(current)
        previous_avg = avg_salary(previous)

        return {
            "current": current_avg,
            "previous": previous_avg,
            "change_percent_from": ((current_avg["from"] - previous_avg["from"]) / previous_avg["from"] * 100) 
                if previous_avg["from"] else 0,
            "change_percent_to": ((current_avg["to"] - previous_avg["to"]) / previous_avg["to"] * 100)
                if previous_avg["to"] else 0
        }

    def _format_vacancies(self, vacancies: List[Vacancy]) -> str:
        """Форматирует вакансии для промпта"""
        formatted = []
        for v in vacancies:
            formatted.append(
                f"Название: {v.title}\n"
                f"Компания: {v.company}\n"
                f"Город: {v.city}\n"
                f"Технологии: {v.tech_stack}\n"
                f"Зарплата: {v.salary_from}-{v.salary_to} {v.currency}\n"
                f"---"
            )
        return "\n".join(formatted)

    def _send_to_deepseek(self, prompt: str) -> str:
        """Отправляет запрос к DeepSeek API"""
        try:
            data = {
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }

            response = requests.post(
                DEEPSEEK_API_URL,
                headers=self.headers,
                json=data
            )
            response.raise_for_status()
            
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Ошибка при получении аналитики: {str(e)}" 