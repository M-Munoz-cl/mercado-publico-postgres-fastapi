from datetime import datetime, timezone, time, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.models import CompraAgil
from zoneinfo import ZoneInfo


def guardar_o_actualizar_compra(db: Session, datos_compra: dict) -> CompraAgil:

    compra = (db.query(CompraAgil)
              .filter(CompraAgil.codigo == datos_compra["codigo"])
              .first()
              )

    if compra is None:
        compra = CompraAgil(**datos_compra)
        db.add(compra)

    else:
        compra.nombre = datos_compra["nombre"]
        compra.organismo = datos_compra.get("organismo")

        compra.region_id = datos_compra["region_id"]
        compra.region_nombre = datos_compra["region_nombre"]

        compra.monto_disponible_clp = datos_compra.get(
            "monto_disponible_clp"
        )

        compra.estado_convocatoria = datos_compra.get(
            "estado_convocatoria"
        )

        compra.estado_codigo = datos_compra.get(
            "estado_codigo"
        )

        compra.fecha_publicacion = datos_compra.get(
            "fecha_publicacion"
        )

        compra.fecha_cierre_primer_llamado = datos_compra.get(
            "fecha_cierre_primer_llamado"
        )

        compra.fecha_cierre_segundo_llamado = datos_compra.get(
            "fecha_cierre_segundo_llamado"
        )

        compra.fecha_actualizacion = datetime.now(timezone.utc)

    return compra


def obtener_codigos_publicados_abiertos_region(
    db: Session,
    region_id: int
) -> set[str]:
    """
    Devuelve los códigos que la base considera publicados
    y que todavía están abiertos en una región.
    """

    ahora = datetime.now(timezone.utc)

    resultados = (
        db.query(CompraAgil.codigo)
        .filter(
            CompraAgil.region_id == region_id,
            CompraAgil.estado_codigo == "publicada",
            or_(
                and_(
                    CompraAgil.estado_convocatoria == 1,
                    CompraAgil.fecha_cierre_primer_llamado.is_not(None),
                    CompraAgil.fecha_cierre_primer_llamado > ahora
                ),
                and_(
                    CompraAgil.estado_convocatoria == 2,
                    CompraAgil.fecha_cierre_segundo_llamado.is_not(None),
                    CompraAgil.fecha_cierre_segundo_llamado > ahora
                )
            )
        )
        .all()
    )

    return {
        codigo
        for (codigo,) in resultados
        if codigo
    }


def obtener_codigos_publicados_hoy_region(
    db: Session,
    region_id: int,
    dias: int = 1
) -> set[str]:
    """
    Devuelve los códigos que la base tiene como publicados
    y cuya fecha de publicación corresponde al día de hoy
    en horario de Chile.
    """

    ahora_chile = datetime.now(
        ZoneInfo("America/Santiago")
    ).replace(tzinfo=None)

    inicio_hoy = ahora_chile - timedelta(days=dias)
    fin_hoy = ahora_chile

    resultados = (
        db.query(CompraAgil.codigo)
        .filter(
            CompraAgil.region_id == region_id,
            CompraAgil.estado_codigo == "publicada",
            CompraAgil.fecha_publicacion.is_not(None),
            CompraAgil.fecha_publicacion >= inicio_hoy,
            CompraAgil.fecha_publicacion < fin_hoy
        )
        .all()
    )

    return {
        codigo
        for (codigo,) in resultados
        if codigo
    }


def marcar_compras_no_publicadas(
    db: Session,
    region_id: int,
    codigos: set[str]
) -> int:

    if not codigos:
        return 0

    ahora = datetime.now(timezone.utc)

    cantidad = (
        db.query(CompraAgil)
        .filter(
            CompraAgil.region_id == region_id,
            CompraAgil.estado_codigo == "publicada",
            CompraAgil.codigo.in_(codigos),
            or_(
                and_(
                    CompraAgil.estado_convocatoria == 1,
                    CompraAgil.fecha_cierre_primer_llamado.is_not(None),
                    CompraAgil.fecha_cierre_primer_llamado > ahora
                ),
                and_(
                    CompraAgil.estado_convocatoria == 2,
                    CompraAgil.fecha_cierre_segundo_llamado.is_not(None),
                    CompraAgil.fecha_cierre_segundo_llamado > ahora
                )
            )
        )
        .update(
            {
                CompraAgil.estado_codigo: "no_publicada",
                CompraAgil.fecha_actualizacion:
                    datetime.now(timezone.utc)
            },
            synchronize_session=False
        )
    )

    return cantidad


def obtener_compras(
    db: Session,
    region_id: int | None = None,
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
    estado_convocatoria: int | None = None,
    buscar: str | None = None,
    limite: int = 100,
    offset: int = 0
):

    consulta = db.query(CompraAgil)

    if buscar and buscar.strip():

        texto = buscar.strip()

        consulta = consulta.filter(
            or_(
                CompraAgil.codigo.ilike(f"%{texto}%"),
                CompraAgil.nombre.ilike(f"%{texto}%")
            )
        )
    
    if region_id is not None:
        consulta = consulta.filter(
            CompraAgil.region_id == region_id
        )

    if fecha_inicio is not None:
        inicio = datetime.combine(
            fecha_inicio,
            time.min
        )

        consulta = consulta.filter(
            CompraAgil.fecha_publicacion >= inicio
        )

    if fecha_fin is not None:
        fin_exclusivo = datetime.combine(
            fecha_fin,
            time.max
        )

        consulta = consulta.filter(
            CompraAgil.fecha_publicacion <= fin_exclusivo
        )

    if estado_convocatoria is not None:
        consulta = consulta.filter(
            CompraAgil.estado_convocatoria == estado_convocatoria
        )


    ahora = datetime.now(timezone.utc)

    consulta = consulta.filter(
        CompraAgil.estado_codigo == "publicada"
    )

    consulta = consulta.filter(
        or_(
            and_(
                CompraAgil.estado_convocatoria == 1,
                CompraAgil.fecha_cierre_primer_llamado > ahora,
            ),
            and_(
                CompraAgil.estado_convocatoria == 2,
                CompraAgil.fecha_cierre_segundo_llamado > ahora,
            ),
        )
    )

    compras = (
        consulta
        .order_by(CompraAgil.fecha_publicacion.desc(),
                  CompraAgil.id.asc())
        .offset(offset)
        .limit(limite)
        .all()
    )

    return compras


def guardar_total_ofertas(db: Session, compra: CompraAgil, total_ofertas: int):
    compra.total_ofertas_reales = total_ofertas
    compra.fecha_actualizacion_ofertas = datetime.now(timezone.utc)
    compra.intentos_actualizacion_ofertas = 0





