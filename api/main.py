"""
Provides a FastAPI backend for processing natural language queries 
about hotel revenue data.
This API receives a user's natural language query and a property ID,
generates an SQL query using an LLM, executes it against the database,
and returns a natural language answer along with the executed SQL query.
The API includes a caching mechanism to store 
the results of the last 100 unique queries,
significantly reducing the need for repeated LLM calls and database queries,
thereby saving computational resources and improving response times.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from functools import lru_cache
from models import QueryRequest, QueryResponse

# Import your colleague's functions
# from llm.agent import generate_sql_from_text, generate_natural_answer

load_dotenv()

app = FastAPI(title="Hotel Revenue Intelligence API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db_connection():
    """Establishes a connection to the PostgreSQL database 
    using credentials from environment variables.
    """
    db_url = os.getenv("DATABASE_URL")
    return psycopg2.connect(db_url)

# Apply a cache to remember the last 100 unique queries.
# This saves LLM compute and database electricity.
@lru_cache(maxsize=100)
def process_and_cache_query(user_prompt: str, property_id: int):
    """Processes the user's natural language query by generating an SQL query, 
    executing it against the database, 
    and formatting the results into a natural language answer.
    """
    conn = None
    try:
        # Get SQL from LLM
        # sql_query = generate_sql_from_text(user_prompt, property_id)
        sql_query = "SELECT * FROM reservations LIMIT 5;" # Mock
        
        # STRICT GUARDRAIL: Only allow SELECT statements
        if not sql_query.strip().upper().startswith("SELECT"):
            raise ValueError("Security block: Only SELECT queries are permitted.")
        
        # Execute efficient DB query
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(sql_query)
        raw_results = cursor.fetchall()
        cursor.close()
        
        # Get final formatted text from LLM
        # final_answer = generate_natural_answer(user_prompt, raw_results)
        final_answer = f"I found {len(raw_results)} results." # Mock
        
        return final_answer, sql_query
        
    except Exception as e:
        raise e
    finally:
        if conn is not None:
            conn.close()

@app.post("/api/query", response_model=QueryResponse)
def process_revenue_query(request: QueryRequest):
    """Endpoint to process a natural language query about hotel revenue data.
    It returns a natural language answer and the executed SQL query."""
    try:
        # Call the cached function
        final_answer, sql_query = process_and_cache_query(
            request.user_prompt, 
            request.property_id
        )
        
        return QueryResponse(
            answer=final_answer,
            generated_sql=sql_query
        )
        
    except Exception as e:
        return QueryResponse(
            answer="An error occurred while processing the request.",
            error=str(e)
        )
