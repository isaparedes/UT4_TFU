"""
Componente Autenticación.
Expone IAutenticacion (registro/login) e IValidarToken (usada por los demás
componentes como dependencia de FastAPI). Usa JWT: el token lleva toda la
información necesaria, así que validar una request NO requiere consultar
a este componente ni guardar sesión en ningún lado -> servicio sin estado.
"""
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

SECRET_KEY = os.getenv("JWT_SECRET", "cambiar-en-produccion")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

router = APIRouter(prefix="/auth", tags=["Autenticación"])


def crear_token(usuario: models.Usuario) -> str:
    payload = {
        "sub": usuario.email,
        "rol": usuario.rol.value,
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ---- IValidarToken: dependencia que consumen Animales, Hogares y Adopciones ----
def validar_token(token: str = Depends(oauth2_scheme)) -> dict:
    credenciales_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credenciales_invalidas
        return {"email": email, "rol": payload.get("rol")}
    except JWTError:
        raise credenciales_invalidas


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
        rol=datos.rol,
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
