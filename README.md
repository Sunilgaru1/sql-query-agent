# Autonomous Text-to-SQL Query Agent

An autonomous, self-healing Text-to-SQL agent built with Django REST Framework that translates unstructured English queries into executable MySQL commands.

This project goes beyond basic prompt engineering by implementing an Agentic Self-Correction Loop and a Multi-Layer Security Gateway, allowing users to safely query any relational database using natural language without being tied to fixed schemas.

## Key Features

- **Dynamic Schema Grounding:** Automatically extracts live table blueprints and schema metadata on-the-fly.
- **Multi-Turn Agentic Self-Correction Loop:** Generate → Execute → Observe → Repair. Runtime MySQL errors are fed back to Llama 3.3 for automated query refinement.
- **Multi-Layer Query Safety Gateway:** `sqlparse` AST validation blocks destructive DDL/DML, and queries run with dedicated read-only credentials.
- **RESTful API Interface:** Django REST Framework endpoints for frontend and dashboard integration.

## Technology Stack

- Backend: Python, Django, Django REST Framework
- Database: MySQL (target), SQLite (Django internals)
- LLM: Groq API (Llama 3.3)
- SQL Parsing & Security: sqlparse
- Environment: python-dotenv

## Architecture & Workflow

1. **Input:** User submits a natural language question via `POST /api/query/`.
2. **Introspection:** The agent connects to the target MySQL database and extracts the current schema.
3. **Generation:** Groq (Llama 3.3) generates an initial SQL query.
4. **Validation:** The sqlparse gateway inspects the AST and blocks destructive operations.
5. **Execution & Observation:** The query is executed with read-only credentials.
6. **Repair:** If execution fails, the MySQL error is sent back to the LLM. Repeats until success or max retries.
7. **Response:** JSON rows are returned to the caller.

## Installation & Setup

### Prerequisites

- Python 3.9+
- MySQL Server
- Groq API Key

### 1. Clone and enter the project

```bash
git clone https://github.com/yourusername/autonomous-text-to-sql-agent.git
cd autonomous-text-to-sql-agent
```

### 2. Virtual environment

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy `.env.example` to `.env` and fill in credentials:

```bash
# Groq API Configuration
GROQ_API_KEY=your_groq_api_key_here

# Django Settings
SECRET_KEY=your_django_secret_key
DEBUG=True

# Read-Only Database Target Credentials
DB_HOST=localhost
DB_PORT=3306
DB_NAME=your_target_database
DB_USER=your_read_only_user
DB_PASSWORD=your_read_only_password
```

Use a MySQL user that has **SELECT-only** privileges on the target database.

### 5. Run the application

```bash
python manage.py migrate
python manage.py runserver
```

## API

### Health

```bash
GET /api/health/
```

### Live schema

```bash
GET /api/schema/
```

### Natural-language query

```bash
POST /api/query/
Content-Type: application/json

{
  "question": "Who are the top 3 highest paid employees in the IT department?"
}
```

Example response:

```json
{
  "question": "Who are the top 3 highest paid employees in the IT department?",
  "sql": "SELECT name, salary FROM employees WHERE department = 'IT' ORDER BY salary DESC LIMIT 3",
  "attempts": 1,
  "repaired": false,
  "repairs": [],
  "row_count": 3,
  "columns": ["name", "salary"],
  "data": [
    {"name": "Ada", "salary": 180000}
  ]
}
```

## Security Note

Map `.env` database credentials to a MySQL role with **READ-ONLY (SELECT)** privileges. That engine-level restriction is the final failsafe alongside sqlparse AST validation.

## License

This project is licensed under the MIT License.
