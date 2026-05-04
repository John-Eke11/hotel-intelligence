"""
This module defines the data models for the API using Pydantic.
The QueryRequest model represents the structure of the incoming request,
while the QueryResponse model defines the structure of the response sent back to the client.
"""
from pydantic import BaseModel, Field
from typing import Optional

class QueryRequest(BaseModel):
    user_prompt: str = Field(..., description="The natural language query from the user.")
    property_id: int = Field(default=1, description="The ID of the property being queried.")

class QueryResponse(BaseModel):
    answer: str = Field(..., description="The final natural language answer.")
    generated_sql: Optional[str] = Field(default=None, description="The executed SQL query.")
    error: Optional[str] = Field(default=None, description="Error message if the process failed.")