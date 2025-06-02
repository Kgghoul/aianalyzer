import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from collections import Counter
from typing import Dict, List, Optional
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VacancyDataProcessor:
    def __init__(self):
        self.parsed_data_dir = Path("parseddata")
        self.exports_dir = Path("exports")
        self.exports_dir.mkdir(exist_ok=True)
        self.parsed_data_dir.mkdir(exist_ok=True)

    def process_latest_data(self) -> Dict:
        """Обработка последнего файла с вакансиями"""
        latest_file = self._get_latest_file()
        if not latest_file:
            logger.error("No vacancy files found in parseddata directory")
            return {}

        logger.info(f"Processing file: {latest_file}")
        return self._process_file(latest_file)

    def _get_latest_file(self) -> Optional[Path]:
        """Получение последнего файла с вакансиями"""
        files = list(self.parsed_data_dir.glob("vacancies_*.json"))
        if not files:
            return None
        return max(files, key=lambda x: x.stat().st_mtime)

    def _process_file(self, file_path: Path) -> Dict:
        """Обработка файла с вакансиями"""
        with open(file_path, 'r', encoding='utf-8') as f:
            vacancies = json.load(f)

        processed_data = {
            "meta": {
                "total_vacancies": len(vacancies),
                "processed_at": datetime.now().isoformat(),
                "source_file": file_path.name
            },
            "analytics": {
                "tech_distribution": self._analyze_technologies(vacancies),
                "location_distribution": self._analyze_locations(vacancies),
                "salary_insights": self._analyze_salaries(vacancies),
                "experience_distribution": self._analyze_experience(vacancies),
                "company_distribution": self._analyze_companies(vacancies)
            },
            "processed_vacancies": self._prepare_vacancies_for_ai(vacancies)
        }

        # Сохраняем обработанные данные
        output_file = self.exports_dir / f"processed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(processed_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Processed data saved to {output_file}")
        return processed_data

    def _analyze_technologies(self, vacancies: List[Dict]) -> Dict:
        """Анализ используемых технологий"""
        tech_counter = Counter()
        for vacancy in vacancies:
            if tech_stack := vacancy.get('tech_stack'):
                techs = [t.strip().lower() for t in tech_stack.split(',')]
                tech_counter.update(techs)
        
        return {
            "top_technologies": dict(tech_counter.most_common(20)),
            "total_unique_technologies": len(tech_counter)
        }

    def _analyze_locations(self, vacancies: List[Dict]) -> Dict:
        """Анализ географического распределения"""
        location_counter = Counter(v.get('city', 'Unknown') for v in vacancies)
        return {
            "top_locations": dict(location_counter.most_common(10)),
            "total_locations": len(location_counter)
        }

    def _analyze_salaries(self, vacancies: List[Dict]) -> Dict:
        """Анализ зарплат"""
        salaries_from = [v['salary_from'] for v in vacancies if v.get('salary_from')]
        salaries_to = [v['salary_to'] for v in vacancies if v.get('salary_to')]
        
        return {
            "average_from": sum(salaries_from) / len(salaries_from) if salaries_from else 0,
            "average_to": sum(salaries_to) / len(salaries_to) if salaries_to else 0,
            "min_salary": min(salaries_from) if salaries_from else 0,
            "max_salary": max(salaries_to) if salaries_to else 0,
            "salary_ranges": {
                "specified": len([v for v in vacancies if v.get('salary_from') or v.get('salary_to')]),
                "not_specified": len([v for v in vacancies if not v.get('salary_from') and not v.get('salary_to')])
            }
        }

    def _analyze_experience(self, vacancies: List[Dict]) -> Dict:
        """Анализ требований к опыту"""
        # Предполагаем, что опыт может быть в заголовке или описании
        junior_keywords = ['junior', 'джуниор', 'начинающий', 'стажер', 'intern']
        middle_keywords = ['middle', 'миддл']
        senior_keywords = ['senior', 'сеньор', 'ведущий', 'lead']
        
        levels = Counter()
        
        for vacancy in vacancies:
            title = vacancy.get('title', '').lower()
            
            if any(k in title for k in junior_keywords):
                levels['junior'] += 1
            elif any(k in title for k in middle_keywords):
                levels['middle'] += 1
            elif any(k in title for k in senior_keywords):
                levels['senior'] += 1
            else:
                levels['not_specified'] += 1
                
        return dict(levels)

    def _analyze_companies(self, vacancies: List[Dict]) -> Dict:
        """Анализ компаний"""
        company_counter = Counter(v.get('company', 'Unknown') for v in vacancies)
        return {
            "top_companies": dict(company_counter.most_common(20)),
            "total_companies": len(company_counter)
        }

    def _prepare_vacancies_for_ai(self, vacancies: List[Dict]) -> List[Dict]:
        """Подготовка вакансий для анализа через AI"""
        prepared_vacancies = []
        for vacancy in vacancies:
            prepared_vacancy = {
                "title": vacancy.get('title', ''),
                "company": vacancy.get('company', ''),
                "location": vacancy.get('city', ''),
                "technologies": vacancy.get('tech_stack', '').split(',') if vacancy.get('tech_stack') else [],
                "salary_range": {
                    "from": vacancy.get('salary_from'),
                    "to": vacancy.get('salary_to'),
                    "currency": vacancy.get('currency')
                },
                "source": vacancy.get('source', ''),
                "url": vacancy.get('url', '')
            }
            prepared_vacancies.append(prepared_vacancy)
        return prepared_vacancies

if __name__ == "__main__":
    processor = VacancyDataProcessor()
    processed_data = processor.process_latest_data()
    if processed_data:
        print("Data processing completed successfully!")
        print(f"Total vacancies processed: {processed_data['meta']['total_vacancies']}")
        print(f"Output saved to: {processor.exports_dir}") 