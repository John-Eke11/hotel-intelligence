from pydantic import BaseModel, Field
from typing import Optional

class QueryRequest(BaseModel):
    user_prompt: str = Field(..., description="The natural language query from the user.")
    property_id: int = Field(default=1, description="The ID of the property being queried.")

class QueryResponse(BaseModel):
    answer: str = Field(..., description="The final natural language answer.")
    generated_sql: Optional[str] = Field(default=None, description="The executed SQL query.")
    error: Optional[str] = Field(default=None, description="Error message if the process failed.")