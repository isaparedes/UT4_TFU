"""
Componente Hogares Transitorios.
Expone IHogares (REST) y, para uso interno de Adopciones, asignar_hogar()
(equivalente a IAsignarHogar).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import validar_token
from app import models, schemas

router = APIRouter(prefix="/hogares", tags=["Hogares Transitorios"])


@router.post("", response_model=schemas.HogarOut, status_code=201)
def crear_hogar(datos: schemas.HogarCreate, db: Session = Depends(get_db),
                 _usuario: dict = Depends(validar_token)):
    hogar = models.HogarTransitorio(responsable=datos.responsable, direccion=datos.direccion)
    db.add(hogar)
    db.commit()
    db.refresh(hogar)
    return hogar


@router.get("", response_model=list[schemas.HogarOut])
def listar_hogares(db: Session = Depends(get_db), _usuario: dict = Depends(validar_token)):
    return db.query(models.HogarTransitorio).all()


# ---- IAsignarHogar: usada solo por el componente Adopciones (no es endpoint HTTP) ----
def asignar_hogar(db: Session, hogar_id: int) -> models.HogarTransitorio:
    hogar = db.get(models.HogarTransitorio, hogar_id)
    if not hogar:
        raise ValueError("Hogar no encontrado")
    if not hogar.disponible:
        raise ValueError("El hogar no está disponible")
    hogar.disponible = False
    db.add(hogar)
    return hogar


def primer_hogar_disponible(db: Session) -> models.HogarTransitorio | None:
    return db.query(models.HogarTransitorio).filter_by(disponible=True).first()
