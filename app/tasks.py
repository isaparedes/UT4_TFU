# Patrón: Queue-Based Load Leveling.

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app import models


def procesar_solicitud_adopcion(
    trabajo_id: str,
    animal_id: int,
    interesado_email: str,
) -> dict:
    db: Session = SessionLocal()

    try:
        existente = (
            db.query(models.Solicitud)
            .filter_by(trabajo_id=trabajo_id)
            .first()
        )

        if existente:
            return {"solicitud_id": existente.id}

        animal = (
            db.query(models.Animal)
            .filter(models.Animal.id == animal_id)
            .with_for_update()
            .first()
        )

        if animal is None:
            raise ValueError("Animal no encontrado")

        existente = (
            db.query(models.Solicitud)
            .filter_by(trabajo_id=trabajo_id)
            .first()
        )

        if existente:
            return {"solicitud_id": existente.id}

        if animal.estado != models.EstadoAnimal.DISPONIBLE:
            raise ValueError("El animal no está disponible para adopción")

        solicitud = models.Solicitud(
            trabajo_id=trabajo_id,
            animal_id=animal.id,
            hogar_id=None,
            interesado_email=interesado_email,
            estado=models.EstadoSolicitud.PENDIENTE,
        )

        db.add(solicitud)
        db.commit()
        db.refresh(solicitud)

        return {"solicitud_id": solicitud.id}

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()