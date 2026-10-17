"""
Componente Autenticación.

"""
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from authlib.integrations.starlette_client import OAuth

from app.database import get_db
from app import models, schemas
from app.settings import settings

SECRET_KEY = settings.JWT_SECRET # Patrón de facilidad de modificación y despliegue: External Configuration Store
ALGORITHM = settings.JWT_ALGORITHM # Patrón de facilidad de modificación y despliegue: External Configuration Store
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES # Patrón de facilidad de modificación y despliegue: External Configuration Store

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = HTTPBearer()

router = APIRouter(prefix="/auth", tags=["Autenticación"])

# Patrón de seguridad: Federated Identity
oauth = OAuth()

oauth.register(
    name="google",
    client_id=settings.GOOGLE_CLIENT_ID, # Patrón de facilidad de modificación y despliegue: External Configuration Store
    client_secret=settings.GOOGLE_CLIENT_SECRET, # Patrón de facilidad de modificación y despliegue: External Configuration Store
    server_metadata_url=(
        "https://accounts.google.com/.well-known/openid-configuration"
    ),
    client_kwargs={"scope": "openid email profile"},
)


def crear_token(usuario: models.Usuario) -> str:
    payload = {
        "sub": usuario.email,
        "rol": usuario.rol.value,
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES), 
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ---- IValidarToken: dependencia que consumen Animales, Hogares y Adopciones ----
def validar_token(
    credenciales=Depends(oauth2_scheme)
) -> dict:
    token = credenciales.credentials

    credenciales_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        email = payload.get("sub")

        if email is None:
            raise credenciales_invalidas

        return {"email": email, "rol": payload.get("rol")}

    except JWTError:
        raise credenciales_invalidas

def requerir_rol(*roles: models.Rol):
    roles_permitidos = {rol.value for rol in roles}

    def verificar(usuario: dict = Depends(validar_token)) -> dict:
        if usuario.get("rol") not in roles_permitidos:
            raise HTTPException(
                status_code=403,
                detail="No tenés permisos para realizar esta operación",
            )
        return usuario

    return verificar


def requerir_admin(usuario: dict = Depends(validar_token)) -> dict:
    if usuario["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Requiere rol admin")
    return usuario


# ---- IAutenticacion: registro y login ----
@router.post("/registro", response_model=schemas.Token, status_code=201)
def registrar(datos: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    if db.query(models.Usuario).filter_by(email=datos.email).first():
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    usuario = models.Usuario(
        email=datos.email,
        password_hash=pwd_context.hash(datos.password),
        rol=models.Rol(datos.rol),
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return schemas.Token(access_token=crear_token(usuario))


@router.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter_by(email=form_data.username).first()
    if not usuario or not pwd_context.verify(form_data.password, usuario.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    return schemas.Token(access_token=crear_token(usuario))


@router.get("/google/login", tags=["Autenticación"])
async def login_google(request: Request):
    """Inicia el flujo de autenticación federada con Google."""

    client_id = settings.GOOGLE_CLIENT_ID # Patrón de facilidad de modificación y despliegue: External Configuration Store
    client_secret = settings.GOOGLE_CLIENT_SECRET # Patrón de facilidad de modificación y despliegue: External Configuration Store

    if not client_id or not client_secret:
        raise HTTPException(
            status_code=500,
            detail="Faltan las credenciales de Google en la configuración",
        )

    redirect_uri = settings.GOOGLE_REDIRECT_URI # Patrón de facilidad de modificación y despliegue: External Configuration Store

    return await oauth.google.authorize_redirect(
        request,
        redirect_uri,
    )

# Patrón de seguridad: Federated Identity
@router.get("/google/callback", response_model=schemas.Token, tags=["Autenticación"])
async def callback_google(
    request: Request,
    db: Session = Depends(get_db),
):

    try:
        token_google = await oauth.google.authorize_access_token(request)
    except Exception as exc:
        raise HTTPException(
            status_code=401,
            detail="No se pudo completar la autenticación con Google",
        ) from exc

    usuario_google = token_google.get("userinfo")

    if not usuario_google:
        raise HTTPException(
            status_code=401,
            detail="Google no proporcionó información de identidad válida",
        )

    google_sub = usuario_google.get("sub")
    email = usuario_google.get("email")
    email_verificado = usuario_google.get("email_verified")

    if not google_sub or not email or email_verificado is not True:
        raise HTTPException(
            status_code=401,
            detail="La identidad o el email de Google no están verificados",
        )

    email = email.strip().lower()

    usuario = (
        db.query(models.Usuario)
        .filter(models.Usuario.google_sub == google_sub)
        .first()
    )

    if usuario is None:
        usuario = (
            db.query(models.Usuario)
            .filter(models.Usuario.email == email)
            .first()
        )

        if usuario is not None:
            if usuario.google_sub and usuario.google_sub != google_sub:
                raise HTTPException(
                    status_code=409,
                    detail="La cuenta ya está vinculada a otra identidad de Google",
                )

            usuario.google_sub = google_sub

        else:
            password_aleatoria = secrets.token_urlsafe(32)

            usuario = models.Usuario(
                email=email,
                password_hash=pwd_context.hash(password_aleatoria),
                rol=models.Rol.ADOPTANTE,
                google_sub=google_sub,
            )

            db.add(usuario)

        try:
            db.commit()
            db.refresh(usuario)
        except Exception as exc:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail="No se pudo guardar el usuario autenticado",
            ) from exc

    return schemas.Token(access_token=crear_token(usuario))
