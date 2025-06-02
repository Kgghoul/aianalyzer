from sqlalchemy import Column, Integer, String, Float, DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()

class Vacancy(Base):
    """Модель вакансии"""
    __tablename__ = 'vacancies'

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    city = Column(String)
    tech_stack = Column(String)  # Stored as comma-separated values
    salary_from = Column(Float)
    salary_to = Column(Float)
    currency = Column(String)
    url = Column(String, unique=True, nullable=False)
    source = Column(String, nullable=False)  # e.g., 'hh.ru', 'djinni'
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Vacancy(id={self.id}, title='{self.title}', company='{self.company}')>" 