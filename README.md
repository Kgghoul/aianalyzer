# AI Job Market Monitor

AI-powered job market monitoring system that tracks vacancies, startups, and trends across multiple platforms.

## Features

- Real-time monitoring of job platforms (hh.ru, djinni, Upwork, Product Hunt)
- AI-powered analysis of market trends
- Telegram bot for instant notifications
- Detailed analytics and insights

## Project Structure

```
.
├── backend/           # FastAPI backend
├── parsers/          # Platform-specific parsers
├── storage/          # Database models and migrations
├── ai/              # AI analysis and reporting
├── bot/             # Telegram bot implementation
└── config/          # Configuration files
```

## Setup

1. Create virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set up environment variables:

```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Run the application:

```bash
uvicorn backend.main:app --reload
```

## Environment Variables

Create a `.env` file with the following variables:

```
DATABASE_URL=postgresql://user:password@localhost:5432/jobmonitor
TELEGRAM_BOT_TOKEN=your_bot_token
HH_API_KEY=your_hh_api_key
```



venv\Scripts\activate  # Windows   
uvicorn backend.main:app --reload
.\venv\Scripts\activate