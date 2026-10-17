"""Esquemas Pydantic (entrada/salida de la API REST) por componente."""
from pydantic import BaseModel, EmailStr
from app.models import Rol, EspecieAnimal, EstadoAnimal, EstadoSolicitud
from typing import Literal

class UsuarioCreate(BaseModel):
    email: EmailStr
    password: str
    rol: Rol = Rol.ADOPTANTE

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class AnimalCreate(BaseModel):
    nombre: str
    especie: EspecieAnimal

class AnimalOut(BaseModel):
    id: int
    nombre: str
    especie: EspecieAnimal
    estado: EstadoAnimal

    class Config:
        from_attributes = True

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

class SolicitudCreate(BaseModel):
    animal_id: int

class SolicitudOut(BaseModel):
    id: int
    animal_id: int
    hogar_id: int | None
    interesado_email: str
    estado: EstadoSolicitud

    class Config:
        from_attributes = True

# Patrón de seguridad: Valet Key
class SolicitudCompartidaOut(BaseModel):
    id: int
    animal_id: int
    hogar_id: int | None
    estado: EstadoSolicitud

    class Config:
        from_attributes = True

# Patrón de rendimiento: Queue-Based Load Leveling
class SolicitudEncolada(BaseModel):
    job_id: str
    estado: str = "encolada"
    mensaje: str


class EstadoTrabajo(BaseModel):
    job_id: str
    estado: str
    solicitud_id: int | None = None
    mensaje: str | None = None


