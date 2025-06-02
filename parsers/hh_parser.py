import requests
import json
from datetime import datetime
from typing import List, Dict, Optional
import os
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

class HHParser:
    BASE_URL = "https://api.hh.ru/vacancies"
    
    def __init__(self):
        self.headers = {
            "User-Agent": "JobMonitor/1.0 (your@email.com)",
            "HH-User-Agent": "JobMonitor/1.0 (your@email.com)"
        }
        self.api_key = os.getenv("HH_API_KEY")

    def get_vacancies(self, 
                     text: str = "python developer",
                     area: int = 1,  # 1 is Moscow
                     per_page: int = 100,
                     page: int = 0) -> List[Dict]:
        """
        Fetch vacancies from HH.ru API
        """
        params = {
            "text": text,
            "area": area,
            "per_page": per_page,
            "page": page,
            "only_with_salary": True
        }

        try:
            logger.info(f"Fetching vacancies from HH.ru (page {page})")
            response = requests.get(
                self.BASE_URL,
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            data = response.json()
            logger.info(f"Successfully fetched {len(data.get('items', []))} vacancies")
            return data.get("items", [])
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching vacancies: {str(e)}")
            return []

    def parse_vacancy(self, vacancy_data: Dict) -> Dict:
        """
        Parse single vacancy data into our format
        """
        try:
            salary = vacancy_data.get("salary", {})
            
            # Extract tech stack from snippet
            snippet = vacancy_data.get("snippet", {})
            requirement = (snippet.get("requirement") or "").lower() if snippet else ""
            responsibility = (snippet.get("responsibility") or "").lower() if snippet else ""
            
            # Take only first 100 characters of each field
            requirement = requirement[:100]
            responsibility = responsibility[:100]
            
            # Combine text fields for tech detection
            full_text = f"{requirement} {responsibility}"
            tech_stack = []
            
            # Common tech stack keywords
            tech_keywords = [
                # Languages
                "python", "java", "javascript", "typescript", "go", "golang", "rust", "c++", "c#", "php",
                
                # Frontend
                "react", "vue", "angular", "html", "css", "sass", "less", "tailwind", "bootstrap",
                
                # Backend
                "django", "flask", "fastapi", "spring", "node.js", "express", "laravel",
                
                # Databases
                "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "sqlite",
                
                # Cloud & DevOps
                "docker", "kubernetes", "aws", "azure", "gcp", "git",
                
                # AI/ML
                "tensorflow", "pytorch", "pandas", "numpy", "opencv", "keras",
                
                # Testing
                "pytest", "selenium", "cypress", "postman"
            ]
            
            for tech in tech_keywords:
                if tech in full_text:
                    tech_stack.append(tech)

            parsed_data = {
                "title": vacancy_data.get("name"),
                "company": vacancy_data.get("employer", {}).get("name"),
                "city": vacancy_data.get("area", {}).get("name"),
                "tech_stack": ",".join(set(tech_stack)),  # Remove duplicates
                "salary_from": salary.get("from"),
                "salary_to": salary.get("to"),
                "currency": salary.get("currency"),
                "url": vacancy_data.get("alternate_url"),
                "source": "hh.ru"
            }
            
            # Validate required fields
            if not parsed_data["title"] or not parsed_data["company"] or not parsed_data["url"]:
                logger.warning(f"Skipping vacancy due to missing required fields: {parsed_data}")
                return None
                
            return parsed_data
        except Exception as e:
            logger.error(f"Error parsing vacancy: {str(e)}")
            return None

    def get_all_vacancies(self, search_query: str = "python developer") -> List[Dict]:
        """
        Fetch all pages of vacancies
        """
        all_vacancies = []
        page = 0
        
        while True:
            vacancies = self.get_vacancies(text=search_query, page=page)
            if not vacancies:
                break
                
            parsed_vacancies = []
            for v in vacancies:
                parsed = self.parse_vacancy(v)
                if parsed:
                    parsed_vacancies.append(parsed)
            
            all_vacancies.extend(parsed_vacancies)
            
            page += 1
            if page >= 20:  # HH.ru limits to 2000 vacancies (20 pages * 100 items)
                break
                
        logger.info(f"Total vacancies parsed: {len(all_vacancies)}")
        return all_vacancies

if __name__ == "__main__":
    # Test the parser
    parser = HHParser()
    vacancies = parser.get_all_vacancies()
    print(f"Found {len(vacancies)} vacancies")
    if vacancies:
        print("Sample vacancy:", json.dumps(vacancies[0], indent=2, ensure_ascii=False)) 