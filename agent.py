import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

def generate_sql(user_question):
    # This is the blueprint we hand to the AI
    system_prompt = """
    You are an expert MySQL data analyst.
    Your job is to write a SQL query to answer the user's question.
    
    RULES:
    - Return ONLY the raw SQL query. No explanations.
    - Do not use markdown formatting like ```sql.
    - Only use the tables and columns provided in the schema below.
    
    SCHEMA:
    CREATE TABLE employees (
      id INT PRIMARY KEY,
      name VARCHAR(100),
      department VARCHAR(50),
      salary INT
    );
    """

    # We send both the system prompt (the rules) and the user's question
    response = client.chat.completions.create(
        model="mixtral-8x7b-32768",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_question}
        ]
    )
    
    return response.choices[0].message.content

# Let's test it!
question = "Who are the top 3 highest paid employees in the IT department?"
print("Question:", question)
print("Generated SQL:\n", generate_sql(question))