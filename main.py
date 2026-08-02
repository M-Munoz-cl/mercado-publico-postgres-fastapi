from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy.orm import Session

from app.crud import obtener_compras
from app.database import obtener_db
from app.schemas import CompraAgilResponse
from app.sincronizador import sincronizar_todas_las_regiones, reconciliar_todas_las_regiones, actualizar_ofertas_compra


app = FastAPI()


@app.post("/sincronizar")
def sincronizar(
    dias: int | None = Query(default=None, ge=1, le=365),
    horas: int | None = Query(default=2, ge=1, le=168),
    region_id: int | None = Query(default=None, ge=1, le=16),
    db: Session = Depends(obtener_db)
):

    if dias is not None:
        horas = None

    return sincronizar_todas_las_regiones(
        db=db,
        dias=dias,
        horas=horas,
        region_id=region_id
    )


@app.post("/reconciliar")
def reconciliar(
    dias: int = Query(default=1, ge=1, le=90),
    db: Session = Depends(obtener_db)
):
    return reconciliar_todas_las_regiones(
        db=db,
        dias=dias
    )


@app.get(
    "/compras",
    response_model=list[CompraAgilResponse]
)
def listar_compras(
    region_id: int | None = None,
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
    estado_convocatoria: int | None = None,
    buscar: str | None = None,
    limite: int = Query(default=20, ge=1, le=9000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(obtener_db)
):

    return obtener_compras(
        db=db,
        region_id=region_id,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        estado_convocatoria=estado_convocatoria,
        buscar=buscar,
        limite=limite,
        offset=offset
    )


@app.post("/compras/{codigo}/actualizar-ofertas")
def actualizar_ofertas_manual(
    codigo: str,
    db: Session = Depends(obtener_db)
):

    try:
        resultado = actualizar_ofertas_compra(
            db=db,
            codigo=codigo
        )

    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"No fue posible consultar las ofertas: {error}"
        )

    if resultado is None:
        raise HTTPException(
            status_code=404,
            detail="Compra no encontrada"
        )

    return resultado