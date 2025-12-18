from fastapi import APIRouter, Depends, HTTPException, status

from src.app.api.schemas import AuthRegisterRequest, AuthLoginRequest, AuthTokenResponse
from src.app.api.deps import get_auth_service
from src.app.services.auth_service import AuthService


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthTokenResponse)
def register(
    req: AuthRegisterRequest,
    svc: AuthService = Depends(get_auth_service),
):
    """
    Регистрация пользователя + создание аккаунта + выдача access_token.
    """
    try:
        token = svc.register(email=req.email, password=req.password, account_name=req.account_name)
        return AuthTokenResponse(access_token=token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/login", response_model=AuthTokenResponse)
def login(
    req: AuthLoginRequest,
    svc: AuthService = Depends(get_auth_service),
):
    """
    Логин пользователя и выдача access_token.
    """
    try:
        token = svc.login(email=req.email, password=req.password)
        return AuthTokenResponse(access_token=token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))