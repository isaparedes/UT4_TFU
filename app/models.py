"""
Modelos SQLAlchemy. Cada clase pertenece a un único componente:
- Usuario           -> Autenticación
- Animal            -> Animales
- HogarTransitorio  -> Hogares Transitorios
- Solicitud         -> Adopciones
"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship

from app.database import Base


class Rol(str, enum.Enum):
    VOLUNTARIO = "voluntario"
    ADMIN = "admin"


class EstadoAnimal(str, enum.Enum):
    DISPONIBLE = "disponible"
    RESERVADO = "reservado"
    ADOPTADO = "adoptado"


class EstadoSolicitud(str, enum.Enum):
    PENDIENTE = "pendiente"
    APROBADA = "aprobada"
    RECHAZADA = "rechazada"


# ---- Componente: Autenticación ----
class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    rol = Column(Enum(Rol), nullable=False, default=Rol.VOLUNTARIO)


# ---- Componente: Animales ----
class Animal(Base):
    __tablename__ = "animales"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    especie = Column(String, nullable=False)  # perro / gato
    estado = Column(Enum(EstadoAnimal), nullable=False, default=EstadoAnimal.DISPONIBLE)
    creado_en = Column(DateTime, default=datetime.utcnow)


# ---- Componente: Hogares Transitorios ----
class HogarTransitorio(Base):
    __tablename__ = "hogares_transitorios"

    id = Column(Integer, primary_key=True, index=True)
    responsable = Column(String, nullable=False)
    direccion = Column(String, nullable=False)
    disponible = Column(Boolean, nullable=False, default=True)


# ---- Componente: Adopciones ----
class Solicitud(Base):
    __tablename__ = "solicitudes"

    id = Column(Integer, primary_key=True, index=True)
    animal_id = Column(Integer, ForeignKey("animales.id"), nullable=False)
    hogar_id = Column(Integer, ForeignKey("hogares_transitorios.id"), nullable=True)
    interesado_email = Column(String, nullable=False)
    estado = Column(Enum(EstadoSolicitud), nullable=False, default=EstadoSolicitud.PENDIENTE)
    creada_en = Column(DateTime, default=datetime.utcnow)

    animal = relationship("Animal")
    hogar = relationship("HogarTransitorio")
