from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from database_crud import users_db_crud as db_crud
from schemas import UserSignUp
from sqlalchemy.orm import Session
from database import get_db
from fastapi_sso.sso.facebook import FacebookSSO
from starlette.requests import Request
from authentication import create_access_token, SESSION_COOKIE_NAME
from dotenv import load_dotenv
from pathlib import Path
import os


directory_path = Path(__file__).parent
env_file_path = directory_path.parent / '.env'

load_dotenv()
FACEBOOK_CLIENT_ID =  os.getenv("FACEBOOK_CLIENT_ID")
FACEBOOK_CLIENT_SECRET =  os.getenv("FACEBOOK_CLIENT_SECRET")

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

facebook_sso = FacebookSSO(
    FACEBOOK_CLIENT_ID,
    FACEBOOK_CLIENT_SECRET, 
    "http://localhost:9999/v1/facebook/callback",
    allow_insecure_http=True
)

router = APIRouter(prefix="/v1/facebook")


@router.get("/login", tags=['Facebook SSO'])
async def facebook_login():
    return await facebook_sso.get_login_redirect()


@router.get("/callback", tags=['Facebook SSO'])
async def facebook_callback(request: Request, db: Session = Depends(get_db)):
    """Process login response from Facebook and return user info"""

    try:
        user = await facebook_sso.verify_and_process(request)
        username = user.email
        user_stored = db_crud.get_user(db, username, user.provider)
        if not user_stored:
            user_to_add = UserSignUp(
                username=username,
                fullname=user.display_name
            )
            user_stored = db_crud.add_user(db, user_to_add, provider=user.provider)
        access_token = create_access_token(username=user_stored.username, provider=user.provider)
        response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        response.set_cookie(SESSION_COOKIE_NAME, access_token)
        return response
    except db_crud.DuplicateError as e:
        raise HTTPException(status_code=403, detail=f"{e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"{e}")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred. Report this message to support: {e}")