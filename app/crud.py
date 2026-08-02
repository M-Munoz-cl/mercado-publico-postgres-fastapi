from datetime import datetime, timezone, time, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, case
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


def obtener_compras_pendientes_ofertas(
    db: Session,
    limite: int = 500
) -> list[CompraAgil]:

    ahora = datetime.now(timezone.utc)

    # fecha_publicacion está almacenada como TIMESTAMP sin zona horaria.
    ahora_chile = (
        ahora
        .astimezone(ZoneInfo("America/Santiago"))
        .replace(tzinfo=None)
    )

    hace_5_minutos = ahora - timedelta(minutes=5)
    hace_15_minutos = ahora - timedelta(minutes=15)
    hace_30_minutos = ahora - timedelta(minutes=30)
    hace_60_minutos = ahora - timedelta(minutes=60)

    hace_2_horas_publicacion = ahora_chile - timedelta(hours=2)

    en_1_hora = ahora + timedelta(hours=1)
    en_6_horas = ahora + timedelta(hours=6)
    en_24_horas = ahora + timedelta(hours=24)

    fecha_cierre = case(
        (
            CompraAgil.estado_convocatoria == 1,
            CompraAgil.fecha_cierre_primer_llamado
        ),
        (
            CompraAgil.estado_convocatoria == 2,
            CompraAgil.fecha_cierre_segundo_llamado
        ),
        else_=None
    )

    seleccionadas: list[CompraAgil] = []
    codigos_seleccionados: set[str] = set()

    def agregar_grupo(
        nombre_grupo: str,
        filtro_grupo,
        cupo: int
    ) -> None:

        espacios_disponibles = limite - len(seleccionadas)

        if espacios_disponibles <= 0:
            return

        cupo_real = min(cupo, espacios_disponibles)

        consulta = (
            db.query(CompraAgil)
            .filter(CompraAgil.estado_codigo == "publicada")
            .filter(fecha_cierre > ahora)
            .filter(
                or_(
                    CompraAgil.total_ofertas_reales.is_(None),
                    CompraAgil.total_ofertas_reales <= 6
                )
            )
            .filter(filtro_grupo)
        )

        if codigos_seleccionados:
            consulta = consulta.filter(
                ~CompraAgil.codigo.in_(codigos_seleccionados)
            )

        compras = (
            consulta
            .order_by(
                CompraAgil.fecha_actualizacion_ofertas.asc().nullsfirst(),
                fecha_cierre.asc(),
                CompraAgil.intentos_actualizacion_ofertas.asc()
            )
            .limit(cupo_real)
            .all()
        )

        for compra in compras:
            compra.grupo_actualizacion_ofertas = nombre_grupo

            seleccionadas.append(compra)
            codigos_seleccionados.add(compra.codigo)

    # ---------------------------------------------------------
    # 1. Nunca consultadas
    # Cupo: 100
    # ---------------------------------------------------------

    filtro_nuevas = or_(
        CompraAgil.total_ofertas_reales.is_(None),
        CompraAgil.fecha_actualizacion_ofertas.is_(None)
    )

    agregar_grupo(
        nombre_grupo="nuevas",
        filtro_grupo=filtro_nuevas,
        cupo=100
    )

    # ---------------------------------------------------------
    # 2. Publicadas durante las últimas 2 horas
    # Refresco cada 5 minutos
    # Cupo: 200
    #
    # Este grupo evita que una compra recién publicada quede
    # guardada en 0 y no vuelva a revisarse durante mucho tiempo.
    # ---------------------------------------------------------

    filtro_recien_publicadas = and_(
        CompraAgil.fecha_publicacion >= hace_2_horas_publicacion,
        CompraAgil.fecha_publicacion <= ahora_chile,
        CompraAgil.fecha_actualizacion_ofertas <= hace_5_minutos
    )

    agregar_grupo(
        nombre_grupo="publicadas_ultimas_2_horas",
        filtro_grupo=filtro_recien_publicadas,
        cupo=200
    )

    # ---------------------------------------------------------
    # 3. Cierran dentro de una hora
    # Refresco cada 5 minutos
    # Cupo: 100
    # ---------------------------------------------------------

    filtro_criticas = and_(
        fecha_cierre <= en_1_hora,
        CompraAgil.fecha_actualizacion_ofertas <= hace_5_minutos
    )

    agregar_grupo(
        nombre_grupo="cierre_1_hora",
        filtro_grupo=filtro_criticas,
        cupo=100
    )

    # ---------------------------------------------------------
    # 4. Cierran entre 1 y 6 horas
    # Refresco cada 15 minutos
    # Cupo: 50
    # ---------------------------------------------------------

    filtro_proximas = and_(
        fecha_cierre > en_1_hora,
        fecha_cierre <= en_6_horas,
        CompraAgil.fecha_actualizacion_ofertas <= hace_15_minutos
    )

    agregar_grupo(
        nombre_grupo="cierre_1_a_6_horas",
        filtro_grupo=filtro_proximas,
        cupo=50
    )

    # ---------------------------------------------------------
    # 5. Cierran entre 6 y 24 horas
    # Refresco cada 30 minutos
    # Cupo: 30
    # ---------------------------------------------------------

    filtro_medias = and_(
        fecha_cierre > en_6_horas,
        fecha_cierre <= en_24_horas,
        CompraAgil.fecha_actualizacion_ofertas <= hace_30_minutos
    )

    agregar_grupo(
        nombre_grupo="cierre_6_a_24_horas",
        filtro_grupo=filtro_medias,
        cupo=30
    )

    # ---------------------------------------------------------
    # 6. Cierran en más de 24 horas
    # Refresco cada 60 minutos
    # Cupo: 20
    # ---------------------------------------------------------

    filtro_lejanas = and_(
        fecha_cierre > en_24_horas,
        CompraAgil.fecha_actualizacion_ofertas <= hace_60_minutos
    )

    agregar_grupo(
        nombre_grupo="cierre_mas_24_horas",
        filtro_grupo=filtro_lejanas,
        cupo=20
    )

    # ---------------------------------------------------------
    # 7. Relleno automático
    #
    # Los cupos suman 500, pero si algún grupo no los ocupa,
    # los espacios se entregan a otras compras elegibles.
    # ---------------------------------------------------------

    espacios_libres = limite - len(seleccionadas)

    if espacios_libres > 0:

        filtro_general = or_(
            filtro_nuevas,
            filtro_recien_publicadas,
            filtro_criticas,
            filtro_proximas,
            filtro_medias,
            filtro_lejanas
        )

        consulta_relleno = (
            db.query(CompraAgil)
            .filter(CompraAgil.estado_codigo == "publicada")
            .filter(fecha_cierre > ahora)
            .filter(
                or_(
                    CompraAgil.total_ofertas_reales.is_(None),
                    CompraAgil.total_ofertas_reales <= 6
                )
            )
            .filter(filtro_general)
        )

        if codigos_seleccionados:
            consulta_relleno = consulta_relleno.filter(
                ~CompraAgil.codigo.in_(codigos_seleccionados)
            )

        compras_relleno = (
            consulta_relleno
            .order_by(
                CompraAgil.fecha_actualizacion_ofertas.asc().nullsfirst(),
                fecha_cierre.asc(),
                CompraAgil.intentos_actualizacion_ofertas.asc()
            )
            .limit(espacios_libres)
            .all()
        )

        for compra in compras_relleno:
            compra.grupo_actualizacion_ofertas = "relleno"

            seleccionadas.append(compra)
            codigos_seleccionados.add(compra.codigo)

    return seleccionadas


def guardar_total_ofertas(db: Session, compra: CompraAgil, total_ofertas: int):
    compra.total_ofertas_reales = total_ofertas
    compra.fecha_actualizacion_ofertas = datetime.now(timezone.utc)
    compra.intentos_actualizacion_ofertas = 0


def registrar_fallo_actualizacion(compra: CompraAgil):
    compra.intentos_actualizacion_ofertas += 1
    compra.fecha_actualizacion_ofertas = datetime.now(timezone.utc)



