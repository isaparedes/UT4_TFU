"""
Componente Adopciones.

"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from redis.exceptions import RedisError
from rq.job import Job
from rq.exceptions import NoSuchJobError
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import validar_token, requerir_rol
from app import models, schemas
from app.queue import adopciones_queue, redis_queue
from app.tasks import procesar_solicitud_adopcion
from app.cache import invalidar_cache_animales

router = APIRouter(prefix="/adopciones", tags=["Adopciones"])


@router.post(
    "",
    response_model=schemas.SolicitudEncolada,
    status_code=status.HTTP_202_ACCEPTED,
)
def crear_solicitud(
    datos: schemas.SolicitudCreate,
    usuario: dict = Depends(requerir_rol(models.Rol.ADOPTANTE)),
):
    # Patrón de rendimiento: Queue-Based Load Leveling
    trabajo_id = uuid.uuid4().hex

    try:
        job = adopciones_queue.enqueue_call(
            func=procesar_solicitud_adopcion,
            args=(
                trabajo_id,
                datos.animal_id,
                usuario["email"],
            ),
            job_id=trabajo_id,
            meta={"requester_email": usuario["email"]},
            timeout=60,
            result_ttl=86400,
            failure_ttl=604800,
        )

        return {
            "job_id": job.id,
            "estado": "encolada",
            "mensaje": "Solicitud aceptada para procesamiento",
        }

    except RedisError:
        raise HTTPException(
            status_code=503,
            detail="No se pudo encolar la solicitud. Intentá nuevamente.",
        )


@router.get("/trabajos/{job_id}", response_model=schemas.EstadoTrabajo)
def consultar_trabajo(
    job_id: str,
    usuario: dict = Depends(validar_token),
):
    try:
        job = Job.fetch(job_id, connection=redis_queue)

        es_admin = usuario.get("rol") == models.Rol.ADMIN.value
        es_solicitante = (
            job.meta.get("requester_email") == usuario.get("email")
        )

        if not es_admin and not es_solicitante:
            raise HTTPException(
                status_code=403,
                detail="No tenés permiso para consultar este trabajo",
            )

        estado = job.get_status(refresh=True)
        estado = estado.value if hasattr(estado, "value") else str(estado)

        estados_visibles = {
            "queued": "encolada",
            "started": "procesando",
            "finished": "completado",
            "failed": "fallido",
            "deferred": "diferido",
            "scheduled": "programado",
        }

        if estado == "finished":
            resultado = job.result or {}
            return {
                "job_id": job.id,
                "estado": "completado",
                "solicitud_id": resultado.get("solicitud_id"),
                "mensaje": "Solicitud registrada correctamente",
            }

        if estado == "failed":
            return {
                "job_id": job.id,
                "estado": "fallido",
                "mensaje": "No se pudo procesar la solicitud",
            }

        return {
            "job_id": job.id,
            "estado": estados_visibles.get(estado, estado),
            "mensaje": "El trabajo todavía no terminó",
        }

    except NoSuchJobError:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    except RedisError:
        raise HTTPException(
            status_code=503,
            detail="No se pudo consultar la cola",
        )


@router.get("", response_model=list[schemas.SolicitudOut])
def listar_solicitudes(
    db: Session = Depends(get_db),
    usuario: dict = Depends(validar_token),
):
    rol = usuario.get("rol")

    if rol == models.Rol.ADOPTANTE.value:
        return (
            db.query(models.Solicitud)
            .filter_by(interesado_email=usuario["email"])
            .all()
        )

    if rol in (models.Rol.ADMIN.value, models.Rol.VOLUNTARIO.value):
        return db.query(models.Solicitud).all()

    raise HTTPException(status_code=403, detail="No tenés permiso")


@router.post("/{solicitud_id}/aprobar", response_model=schemas.SolicitudOut)
def aprobar_solicitud(
    solicitud_id: int,
    db: Session = Depends(get_db),
    _usuario: dict = Depends(requerir_rol(models.Rol.ADMIN)),
):
    try:
        referencia = db.get(models.Solicitud, solicitud_id)

        if referencia is None:
            raise HTTPException(
                status_code=404,
                detail="Solicitud no encontrada"
            )

        animal = (
            db.query(models.Animal)
            .filter(models.Animal.id == referencia.animal_id)
            .with_for_update()
            .first()
        )

        if animal is None:
            raise HTTPException(
                status_code=404,
                detail="Animal no encontrado"
            )

        solicitud = (
            db.query(models.Solicitud)
            .filter(models.Solicitud.id == solicitud_id)
            .with_for_update()
            .first()
        )

        if solicitud is None:
            raise HTTPException(
                status_code=404,
                detail="Solicitud no encontrada"
            )

        if solicitud.estado != models.EstadoSolicitud.PENDIENTE:
            raise HTTPException(
                status_code=409,
                detail="La solicitud ya fue procesada"
            )

        if animal.estado != models.EstadoAnimal.DISPONIBLE:
            raise HTTPException(
                status_code=409,
                detail="El animal ya no está disponible para adopción"
            )

        animal.estado = models.EstadoAnimal.ADOPTADO
        solicitud.estado = models.EstadoSolicitud.APROBADA

        (
            db.query(models.Solicitud)
            .filter(
                models.Solicitud.animal_id == animal.id,
                models.Solicitud.id != solicitud.id,
                models.Solicitud.estado == models.EstadoSolicitud.PENDIENTE,
            )
            .update(
                {"estado": models.EstadoSolicitud.RECHAZADA},
                synchronize_session=False,
            )
        )

        db.commit()
        db.refresh(solicitud)

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise

    # Patrón de rendimiento: Caché-Aside
    invalidar_cache_animales(animal.id)

    return solicitud


@router.post("/{solicitud_id}/rechazar", response_model=schemas.SolicitudOut)
def rechazar_solicitud(
    solicitud_id: int,
    db: Session = Depends(get_db),
    _usuario: dict = Depends(requerir_rol(models.Rol.ADMIN)),
):
    solicitud = db.get(models.Solicitud, solicitud_id)

    if solicitud is None:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    if solicitud.estado != models.EstadoSolicitud.PENDIENTE:
        raise HTTPException(
            status_code=409,
            detail="La solicitud ya fue procesada",
        )

    solicitud.estado = models.EstadoSolicitud.RECHAZADA
    db.commit()
    db.refresh(solicitud)
    return solicitud