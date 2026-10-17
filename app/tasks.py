# Patrón de rendimiento: Queue-Based Load Leveling.
from datetime import datetime

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app import models
from app.cache import invalidar_cache_animales
from app.reglas_negocio import liberar_temporales_vencidos


def procesar_solicitud_adopcion(
    trabajo_id: str,
    animal_id: int,
    interesado_email: str,
    tipo: str,
    fecha_fin_temporal: datetime | None,
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

        usuario = (
            db.query(models.Usuario)
            .filter_by(email=interesado_email)
            .with_for_update()
            .first()
        )
        if usuario is None:
            raise ValueError("Usuario no encontrado")

        hogar = (
            db.query(models.HogarTransitorio)
            .filter_by(usuario_email=interesado_email)
            .with_for_update()
            .first()
        )
        if hogar is None:
            raise ValueError("Primero tenés que registrar tu hogar")

        animal = (
            db.query(models.Animal)
            .filter_by(id=animal_id)
            .with_for_update()
            .first()
        )
        if animal is None:
            raise ValueError("Animal no encontrado")

        liberar_temporales_vencidos(db)
        db.flush()

        if animal.estado != models.EstadoAnimal.DISPONIBLE:
            raise ValueError("El animal no está disponible para adopción")

        pendiente = (
            db.query(models.Solicitud)
            .filter(
                models.Solicitud.interesado_email == interesado_email,
                models.Solicitud.estado == models.EstadoSolicitud.PENDIENTE,
            )
            .first()
        )
        if pendiente:
            raise ValueError(
                "Ya tenés una solicitud pendiente de resolución"
            )

        hogar_ocupado = (
            db.query(models.Solicitud)
            .join(
                models.Animal,
                models.Solicitud.animal_id == models.Animal.id,
            )
            .filter(
                models.Solicitud.hogar_id == hogar.id,
                models.Solicitud.estado == models.EstadoSolicitud.APROBADA,
                models.Animal.estado.in_([
                    models.EstadoAnimal.ADOPTADO,
                    models.EstadoAnimal.ALOJADO_TEMPORALMENTE,
                ]),
            )
            .first()
        )
        if hogar_ocupado:
            raise ValueError("Tu hogar ya tiene un animal alojado")

        tipo_enum = models.TipoAdopcion(tipo)

        if tipo_enum == models.TipoAdopcion.TEMPORAL:
            if (
                fecha_fin_temporal is None
                or fecha_fin_temporal <= datetime.utcnow()
            ):
                raise ValueError(
                    "La adopción temporal requiere una fecha futura"
                )
        elif fecha_fin_temporal is not None:
            raise ValueError(
                "Una adopción definitiva no debe tener fecha de finalización"
            )

        solicitud = models.Solicitud(
            trabajo_id=trabajo_id,
            animal_id=animal.id,
            hogar_id=hogar.id,
            interesado_email=interesado_email,
            tipo=tipo_enum,
            fecha_fin_temporal=fecha_fin_temporal,
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
