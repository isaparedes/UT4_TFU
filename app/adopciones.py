"""
Componente Adopciones.
Expone IAdopciones (REST) y orquesta a Animales y Hogares Transitorios
dentro de UNA MISMA transacción de base de datos (ACID): reservar el animal
y asignar el hogar se confirman o se cancelan juntos.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import validar_token
from app import models, schemas, animales, hogares

router = APIRouter(prefix="/adopciones", tags=["Adopciones"])


@router.post("", response_model=schemas.SolicitudOut, status_code=201)
def crear_solicitud(datos: schemas.SolicitudCreate, db: Session = Depends(get_db),
                     _usuario: dict = Depends(validar_token)):
    hogar_id = None
    try:
        # --- Transacción ACID: reservar animal + asignar hogar, todo o nada ---
        animal = animales.reservar_animal(db, datos.animal_id)

        if datos.asignar_hogar:
            hogar = hogares.primer_hogar_disponible(db)
            if hogar is None:
                raise ValueError("No hay hogares transitorios disponibles")
            hogares.asignar_hogar(db, hogar.id)
            hogar_id = hogar.id

        solicitud = models.Solicitud(
            animal_id=animal.id,
            hogar_id=hogar_id,
            interesado_email=datos.interesado_email,
            estado=models.EstadoSolicitud.PENDIENTE,
        )
        db.add(solicitud)
        db.commit()          # <- se confirman animal + hogar + solicitud juntos
        db.refresh(solicitud)
        return solicitud

    except ValueError as e:
        db.rollback()        # <- si algo falla, no queda nada reservado a medias
        raise HTTPException(status_code=409, detail=str(e))


@router.get("", response_model=list[schemas.SolicitudOut])
def listar_solicitudes(db: Session = Depends(get_db), _usuario: dict = Depends(validar_token)):
    return db.query(models.Solicitud).all()


@router.post("/{solicitud_id}/aprobar", response_model=schemas.SolicitudOut)
def aprobar_solicitud(solicitud_id: int, db: Session = Depends(get_db),
                       _usuario: dict = Depends(validar_token)):
    solicitud = db.get(models.Solicitud, solicitud_id)
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    animal = db.get(models.Animal, solicitud.animal_id)
    animal.estado = models.EstadoAnimal.ADOPTADO
    solicitud.estado = models.EstadoSolicitud.APROBADA
    db.add_all([animal, solicitud])
    db.commit()
    db.refresh(solicitud)
    return solicitud
