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

router = APIRouter(prefix="/animales", tags=["Animales"])


@router.post("", response_model=schemas.AnimalOut, status_code=201)
def crear_animal(datos: schemas.AnimalCreate, db: Session = Depends(get_db),
                  _usuario: dict = Depends(validar_token)):
    animal = models.Animal(nombre=datos.nombre, especie=datos.especie)
    db.add(animal)
    db.commit()
    db.refresh(animal)
    return animal


@router.get("", response_model=list[schemas.AnimalOut])
def listar_animales(db: Session = Depends(get_db), _usuario: dict = Depends(validar_token)):
    return db.query(models.Animal).all()


@router.get("/{animal_id}", response_model=schemas.AnimalOut)
def obtener_animal(animal_id: int, db: Session = Depends(get_db),
                    _usuario: dict = Depends(validar_token)):
    animal = db.get(models.Animal, animal_id)
    if not animal:
        raise HTTPException(status_code=404, detail="Animal no encontrado")
    return animal


# ---- IReservarAnimal: usada solo por el componente Adopciones (no es endpoint HTTP) ----
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
