"""
Componente Animales.
Expone IAnimales (REST) y, para uso interno de Adopciones, las funciones
reservar_animal() / liberar_animal() (equivalentes a IReservarAnimal).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import validar_token
from app import models, schemas

# Patrón de rendimiento: Caché-Aside
from app.cache import obtener_cache, guardar_cache, invalidar_cache_animales

router = APIRouter(prefix="/animales", tags=["Animales"])


@router.post("", response_model=schemas.AnimalOut, status_code=201)
def crear_animal(datos: schemas.AnimalCreate, db: Session = Depends(get_db),
                  _usuario: dict = Depends(validar_token)):
    animal = models.Animal(nombre=datos.nombre, especie=datos.especie)
    db.add(animal)
    db.commit()
    db.refresh(animal)

    # Patrón de rendimiento: Caché-Aside
    invalidar_cache_animales()

    return animal


@router.get("", response_model=list[schemas.AnimalOut])
def listar_animales(
    db: Session = Depends(get_db),
    _usuario: dict = Depends(validar_token)
):
    # Patrón de rendimiento: Caché-Aside
    clave = "animales:list"
    datos = obtener_cache(clave)

    if datos is not None:
        return datos  # Cache HIT

    # Cache MISS
    animales = db.query(models.Animal).all()

    resultado = [
        schemas.AnimalOut.model_validate(
            animal, from_attributes=True
        ).model_dump(mode="json")
        for animal in animales
    ]

    guardar_cache(clave, resultado, ttl=30)

    return resultado


@router.get("/{animal_id}", response_model=schemas.AnimalOut)
def obtener_animal(
    animal_id: int,
    db: Session = Depends(get_db),
    _usuario: dict = Depends(validar_token)
):
    # Patrón de rendimiento: Caché-Aside
    clave = f"animal:{animal_id}"
    datos = obtener_cache(clave)

    if datos is not None:
        return datos  # Cache HIT

    # Cache MISS
    animal = db.get(models.Animal, animal_id)

    if not animal:
        raise HTTPException(
            status_code=404,
            detail="Animal no encontrado"
        )

    resultado = schemas.AnimalOut.model_validate(
        animal, from_attributes=True
    ).model_dump(mode="json")

    guardar_cache(clave, resultado, ttl=60)

    return resultado

def reservar_animal(db: Session, animal_id: int) -> models.Animal:
    animal = db.get(models.Animal, animal_id)
    if not animal:
        raise ValueError("Animal no encontrado")
    if animal.estado != models.EstadoAnimal.DISPONIBLE:
        raise ValueError("El animal no está disponible")
    animal.estado = models.EstadoAnimal.RESERVADO
    db.add(animal)
    return animal


def liberar_animal(db: Session, animal_id: int) -> None:
    animal = db.get(models.Animal, animal_id)
    if animal and animal.estado == models.EstadoAnimal.RESERVADO:
        animal.estado = models.EstadoAnimal.DISPONIBLE
        db.add(animal)
