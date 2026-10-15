"""Esquemas Pydantic (entrada/salida de la API REST) por componente."""
from pydantic import BaseModel, EmailStr
from app.models import Rol, EstadoAnimal, EstadoSolicitud


# ---- Autenticación ----
class UsuarioCreate(BaseModel):
    email: EmailStr
    password: str
    rol: Rol = Rol.VOLUNTARIO


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---- Animales ----
class AnimalCreate(BaseModel):
    nombre: str
    especie: str


class AnimalOut(BaseModel):
    id: int
    nombre: str
    especie: str
    estado: EstadoAnimal

    class Config:
        from_attributes = True


# ---- Hogares Transitorios ----
class HogarCreate(BaseModel):
    responsable: str
    direccion: str


class HogarOut(BaseModel):
    id: int
    responsable: str
    direccion: str
    disponible: bool

    class Config:
        from_attributes = True


# ---- Adopciones ----
class SolicitudCreate(BaseModel):
    animal_id: int
    interesado_email: EmailStr
    asignar_hogar: bool = True


class SolicitudOut(BaseModel):
    id: int
    animal_id: int
    hogar_id: int | None
    interesado_email: str
    estado: EstadoSolicitud

    class Config:
        from_attributes = True
