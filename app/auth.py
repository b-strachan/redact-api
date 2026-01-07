from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
import os

api_key_header = APIKeyHeader(name="Redact-API-Key", auto_error=False)


async def get_api_key(api_key_header: str = Security(api_key_header)):
    # 1. Allow the Demo Key (Matches your index.html)
    if api_key_header == "secret-dev-key":
        return api_key_header

    # 2. Allow the Real Environment Key (For your Pro/Railway settings)
    env_key = os.getenv("API_KEY")
    if env_key and api_key_header == env_key:
        return api_key_header

    # 3. If neither matches, Block access
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Could not validate credentials"
    )