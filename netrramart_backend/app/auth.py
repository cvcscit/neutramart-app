from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from google.oauth2 import id_token
from google.auth.transport import requests

GOOGLE_CLIENT_ID = "1002409619791-66n3jv66p121t7g0qmasukau0r6tc6i1.apps.googleusercontent.com"

security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = id_token.verify_oauth2_token(
            credentials.credentials,
            requests.Request(),
            GOOGLE_CLIENT_ID,
        )
        return {"email": payload["email"], "name": payload.get("given_name", "")}
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
