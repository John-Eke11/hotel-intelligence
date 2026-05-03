import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from models import QueryRequest, QueryResponse

# Load environment variables
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
    """Securely connects to Supabase using the environment URL."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL is not set in the .env file.")
    return psycopg2.connect(db_url)

# ==========================================
# PLACEHOLDER FOR LLM FOLDER LOGIC
# In the real app, import this from your colleague's LLM module
# ==========================================
def mock_llm_logic(user_prompt: str, property_id: int) -> str:
    """Mocks the LLM translating text to SQL."""
    return f"SELECT * FROM reservations WHERE property_id = {property_id} LIMIT 5;"

def mock_llm_format(raw_data: list) -> str:
    """Mocks the LLM turning DB results into a human sentence."""
    return f"I found {len(raw_data)} recent reservations matching your criteria."

# ==========================================
# API ENDPOINT
# ==========================================
@app.post("/api/query", response_model=QueryResponse)
async def process_revenue_query(request: QueryRequest):
    conn = None
    try:
        # 1. Get SQL from LLM
        sql_query = mock_llm_logic(request.user_prompt, request.property_id)
        
        # 2. Connect to Supabase and execute
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(sql_query)
        raw_results = cursor.fetchall()
        cursor.close()
        
        # 3. Format final answer
        final_answer = mock_llm_format(raw_results)
        
        return QueryResponse(
            answer=final_answer,
            generated_sql=sql_query
        )
        
    except Exception as e:
        return QueryResponse(
            answer="An error occurred while processing the request.",
            error=str(e)
        )
    finally:
        if conn is not None:
            conn.close()
