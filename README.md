Autonomous Text-to-SQL Query Agent

An autonomous, self-healing Text-to-SQL agent built with Django REST Framework that translates unstructured English queries into executable MySQL commands.

This project goes beyond basic prompt engineering by implementing an Agentic Self-Correction Loop and a Multi-Layer Security Gateway, allowing users to safely query any relational database using natural language without being tied to fixed schemas.

🚀 Key Features

Dynamic Schema Grounding: Automatically extracts live table blueprints and schema metadata on-the-fly. This decouples the agent from fixed schemas, allowing plug-and-play connections to any external relational database.

Multi-Turn Agentic Self-Correction Loop: Implements a robust Generate → Execute → Observe → Repair cycle. If a generated SQL query throws an execution exception, the runtime error trace is intercepted and fed back to the LLM (Llama 3.3) for automated query refinement.

Multi-Layer Query Safety Gateway: Ensures absolute database safety by combining:

AST Validation: Uses sqlparse to analyze the Abstract Syntax Tree of the generated SQL, sanitizing prompts and systematically blocking destructive DDL/DML mutations (e.g., DROP, DELETE, UPDATE, INSERT).

Role-Based Access Control: Executes all queries using dedicated read-only database credentials.

RESTful API Interface: Fully accessible via standard HTTP requests managed by Django REST Framework, making it easy to integrate into frontend applications or enterprise dashboards.

🛠️ Technology Stack

Backend: Python, Django, Django REST Framework (DRF)

Database: MySQL

LLM Integration: Groq API (powered by Llama 3.3)

SQL Parsing & Security: sqlparse

Environment Management: python-dotenv

Version Control: Git

🏗️ Architecture & Workflow

Input: User submits a natural language question via the REST API.

Introspection: The agent dynamically connects to the target MySQL database and extracts the current schema blueprint.

Generation: The Groq API (Llama 3.3) generates an initial SQL query based on the prompt and live schema.

Validation: The sqlparse gateway inspects the AST to ensure no destructive operations exist.

Execution & Observation: The query is executed using read-only credentials.

Repair (Self-Correction): If execution fails, the exact MySQL error trace is captured and sent back to the LLM to rewrite the query. This repeats until successful execution or a max-retry limit is reached.

Response: The final JSON data payload is returned to the user.

⚙️ Installation & Setup

Prerequisites

Python 3.9+

MySQL Server

Groq API Key

1. Clone the repository

git clone https://github.com/yourusername/autonomous-text-to-sql-agent.git
cd autonomous-text-to-sql-agent


2. Set up a virtual environment

python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`


3. Install dependencies

pip install -r requirements.txt


4. Configure Environment Variables

Create a .env file in the root directory and add your credentials:

# Groq API Configuration
GROQ_API_KEY=your_groq_api_key_here

# Django Settings
SECRET_KEY=your_django_secret_key
DEBUG=True

# Read-Only Database Target Credentials (The DB you want to query)
DB_HOST=localhost
DB_PORT=3306
DB_NAME=your_target_database
DB_USER=your_read_only_user
DB_PASSWORD=your_read_only_password


5. Run the application

python manage.py migrate
python manage.py runserver


🔒 Security Note

This application is designed to be highly secure. However, it is strongly recommended that the database credentials provided in the .env file are strictly mapped to a user role with READ-ONLY (SELECT) privileges on the target database at the database engine level, acting as a final failsafe alongside the sqlparse AST validation.

🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the issues page.

📝 License

This project is licensed under the MIT License.
