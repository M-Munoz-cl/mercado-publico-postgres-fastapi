from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from time import perf_counter
from zoneinfo import ZoneInfo

import requests
from sqlalchemy.orm import Session

from app.config import BASE_URL, HEADERS
from app.crud import (
    guardar_o_actualizar_compra,
    obtener_compras_pendientes_ofertas,
    guardar_total_ofertas,
    registrar_fallo_actualizacion,
    obtener_codigos_publicados_hoy_region,
    marcar_compras_no_publicadas
)
from app.regiones import REGIONES
from app.cliente_buscador import ClienteBuscador

from app.models import CompraAgil

ZONA_CHILE = ZoneInfo("America/Santiago")

TAMANO_PAGINA = 50
MAX_WORKERS = 20
TTL_POR_DEFECTO_HORAS = 2

MAX_WORKERS_OFERTAS = 6
LIMITE_OFERTAS_POR_CICLO = 500

cliente_buscador = ClienteBuscador()


def calcular_ttl(dias: int | None = None, horas: int | None = None) -> int:
    """
    Convierte una ventanada de dias u horas a milisegundos

    Se debe enviar solo uno de los dos parametros
    """

    if dias is not None and horas is not None:
        raise ValueError("No se pueden enviar dias y horas al mismo tiempo")

    if horas is not None:
        horas = max(1, min(horas, 168))
        return horas * 60 * 60 * 1000

    if dias is not None:
        dias = max(1, min(dias, 365))
        return dias * 24 * 60 * 60 * 1000

    return TTL_POR_DEFECTO_HORAS * 60 * 60 * 1000

def obtener_pagina(
    region_id: int,
    numero_pagina: int,
    horas: int
) -> tuple[list, dict]:

    ahora_chile = datetime.now(ZONA_CHILE)
    desde_chile = ahora_chile - timedelta(hours=horas)

    cambio_desde = desde_chile.strftime("%Y-%m-%dT%H:%M:%SZ")
    cambio_hasta = ahora_chile.strftime("%Y-%m-%dT%H:%M:%SZ")

    response = requests.get(
        f"{BASE_URL}/v2/compra-agil",
        headers=HEADERS,
        params={
            "cambio_desde": cambio_desde,
            "cambio_hasta": cambio_hasta,
            "tamano_pagina": TAMANO_PAGINA,
            "numero_pagina": numero_pagina,
            "estado": "publicada",
            "region": region_id
        },
        timeout=30
    )

    if response.status_code != 200:
        print(
            f"Error HTTP {response.status_code} "
            f"en región {region_id}, página {numero_pagina}"
        )

        return [], {}

    data = response.json()
    payload = data.get("payload")

    if not payload:
        print(
            f"La API respondió sin payload "
            f"en región {region_id}, página {numero_pagina}"
        )

        return [], {}

    print(
        f"DEBUG región={region_id}, "
        f"página={numero_pagina}, "
        f"desde={cambio_desde}, "
        f"hasta={cambio_hasta}, "
        f"items={len(payload.get('items', []))}, "
        f"paginacion={payload.get('paginacion', {})}"
    )

    return (
        payload.get("items", []),
        payload.get("paginacion", {})
    )


def obtener_pagina_reconciliacion(
    region_id: int,
    numero_pagina: int,
    dias: int
) -> tuple[list, dict, bool]:
    """
    Obtiene las compras que siguen publicadas desde hoy
    a las 00:00 hasta el momento actual, en horario de Chile.
    """

    ahora_chile = datetime.now(ZONA_CHILE)

    inicio_hoy_chile = ahora_chile - timedelta(days=dias)

    cambio_desde = inicio_hoy_chile.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    cambio_hasta = ahora_chile.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    try:
        response = requests.get(
            f"{BASE_URL}/v2/compra-agil",
            headers=HEADERS,
            params={
                "cambio_desde": cambio_desde,
                "cambio_hasta": cambio_hasta,
                "tamano_pagina": TAMANO_PAGINA,
                "numero_pagina": numero_pagina,
                "estado": "publicada",
                "region": region_id
            },
            timeout=30
        )

    except requests.RequestException as error:
        print(
            f"Error de conexión en reconciliación: "
            f"región={region_id}, "
            f"página={numero_pagina}, "
            f"error={error}"
        )

        return [], {}, False

    if response.status_code != 200:
        print(
            f"Error HTTP {response.status_code} "
            f"en reconciliación: "
            f"región={region_id}, "
            f"página={numero_pagina}"
        )

        return [], {}, False

    try:
        data = response.json()
    except ValueError:
        print(
            f"Respuesta JSON inválida en reconciliación: "
            f"región={region_id}, "
            f"página={numero_pagina}"
        )

        return [], {}, False

    payload = data.get("payload")

    if not payload:
        print(
            f"Reconciliación sin payload: "
            f"región={region_id}, "
            f"página={numero_pagina}"
        )

        return [], {}, False

    items = payload.get("items", [])
    paginacion = payload.get("paginacion", {})

    if not paginacion:
        print(
            f"Reconciliación sin paginación: "
            f"región={region_id}, "
            f"página={numero_pagina}"
        )

        return [], {}, False

    print(
        f"RECONCILIACIÓN región={region_id}, "
        f"página={numero_pagina}, "
        f"desde={cambio_desde}, "
        f"hasta={cambio_hasta}, "
        f"items={len(items)}"
    )

    return items, paginacion, True



def convertir_fecha_publicacion(fecha_texto: str | None):
    """
    Convierte fechas como:
    2026-07-21 15:30
    """

    if not fecha_texto:
        return None

    try:
        return datetime.strptime(
            fecha_texto,
            "%Y-%m-%d %H:%M"
        )

    except ValueError:
        return None


def convertir_fecha_iso(fecha_texto: str | None):
    """
    Conversion ISO normal: interpreta Z como UTC
    """

    if not fecha_texto:
        return None

    try:
        return datetime.fromisoformat(
            fecha_texto.replace("Z", "+00:00")
        )

    except (ValueError, TypeError):
        return None

def convertir_fecha_segundo_llamado(fecha_texto: str | None):
    """
    La API entrega el segundo llamado terminado en Z,
    pero la hora coincide con la hora local mostrada en el portal.
    """

    if not fecha_texto:
        return None

    try:
        texto = fecha_texto.strip()

        if texto.endswith("Z"):
            texto = texto[:-1]

        fecha = datetime.fromisoformat(texto)

        return fecha.replace(tzinfo=ZONA_CHILE)

    except (ValueError, TypeError):
        return None

def transformar_item(
    item: dict,
    region_id: int,
    region_nombre: str
) -> dict | None:

    codigo = item.get("codigo")
    nombre = item.get("nombre")

    if not codigo or not nombre:
        return None

    institucion = item.get("institucion") or {}
    montos = item.get("montos") or {}
    convocatoria = item.get("convocatoria") or {}
    fechas = item.get("fechas") or {}
    estado = item.get("estado") or {}


    if codigo == "799512-980-COT26":
        print("FECHA CRUDA PRIMER:", fechas.get("fecha_cierre_primer_llamado"))
        print("FECHA CRUDA SEGUNDO:", fechas.get("fecha_cierre_segundo_llamado"))


    monto = montos.get("monto_disponible_clp")

    if monto is not None:
        try:
            monto = int(monto)
        except (TypeError, ValueError):
            monto = None



    fecha_segundo_cruda = fechas.get(
        "fecha_cierre_segundo_llamado"
    )

    fecha_segundo_convertida = convertir_fecha_segundo_llamado(
        fecha_segundo_cruda
    )

    

    return {
        "codigo": codigo,
        "nombre": nombre,
        "organismo": institucion.get("organismo_comprador"),

        "region_id": region_id,
        "region_nombre": region_nombre,

        "monto_disponible_clp": monto,

        "estado_convocatoria": convocatoria.get(
            "estado_convocatoria"
        ),

        "estado_codigo": estado.get("codigo"),

        "fecha_publicacion": convertir_fecha_publicacion(
            fechas.get("fecha_publicacion")
        ),

        "fecha_cierre_primer_llamado": convertir_fecha_segundo_llamado(
            fechas.get("fecha_cierre_primer_llamado")
        ),

        "fecha_cierre_segundo_llamado": fecha_segundo_convertida

    }


def sincronizar_region(
    db: Session,
    region_id: int,
    region_nombre: str,
    dias: int | None = None,
    horas: int | None = TTL_POR_DEFECTO_HORAS
) -> dict:

    if dias is not None:
        horas_consulta = dias * 24
    else:
        horas_consulta = horas or TTL_POR_DEFECTO_HORAS

    items_primera_pagina, paginacion = obtener_pagina(
        region_id=region_id,
        numero_pagina=1,
        horas=horas_consulta
    )

    if not paginacion:
        return {
            "region_id": region_id,
            "region_nombre": region_nombre,
            "procesadas": 0,
            "omitidas": 0,
            "error": "No se pudo obtener la paginación"
        }

    total_paginas = paginacion.get("total_paginas", 1)

    print(
        f"Región {region_nombre}: "
        f"{total_paginas} páginas encontradas"
    )

    todos_los_items = list(items_primera_pagina)

    if total_paginas > 1:

        with ThreadPoolExecutor(
            max_workers=MAX_WORKERS
        ) as executor:

            resultados = executor.map(
                obtener_pagina,
                [region_id] * (total_paginas - 1),
                range(2, total_paginas + 1),
                [horas_consulta] * (total_paginas - 1)
            )

            for items_pagina, _ in resultados:
                todos_los_items.extend(items_pagina)
    
    codigos_encontrados = [
        item.get("codigo")
        for item in todos_los_items
        if item.get("codigo")
    ]

    print(
        f"Región {region_nombre}: "
        f"{len(codigos_encontrados)} compras encontradas "
        f"en las ultimas {horas_consulta} horas"
    )

    if codigos_encontrados:
        print(
            f"Códigos encontrados en {region_nombre}: "
            f"{codigos_encontrados}"
        )

    procesadas = 0
    omitidas = 0

    try:
        for item in todos_los_items:

            datos_compra = transformar_item(
                item=item,
                region_id=region_id,
                region_nombre=region_nombre
            )

            if datos_compra is None:
                omitidas += 1
                continue

            guardar_o_actualizar_compra(
                db=db,
                datos_compra=datos_compra
            )

            procesadas += 1

        db.commit()

    except Exception:
        db.rollback()
        raise

    return {
        "region_id": region_id,
        "region_nombre": region_nombre,
        "paginas": total_paginas,
        "encontradas": len(codigos_encontrados),
        "codigos_encontrados": codigos_encontrados,
        "procesadas": procesadas,
        "omitidas": omitidas
    }


def actualizar_ofertas_compra(
    db: Session,
    codigo: str
) -> dict | None:

    compra = (
        db.query(CompraAgil)
        .filter(CompraAgil.codigo == codigo)
        .first()
    )

    if compra is None:
        return None

    try:
        total = cliente_buscador.obtener_total_ofertas_manual(
            codigo
        )

        if total is None:
            raise ValueError(
                "La ficha no entregó total_ofertas_recibidas"
            )

        guardar_total_ofertas(
            db=db,
            compra=compra,
            total_ofertas=int(total)
        )

        db.commit()
        db.refresh(compra)

        return {
            "codigo": compra.codigo,
            "total_ofertas_reales":
                compra.total_ofertas_reales,
            "fecha_actualizacion_ofertas":
                compra.fecha_actualizacion_ofertas
        }

    except Exception:
        db.rollback()
        raise


def actualizar_ofertas_reales(
    db: Session,
    limite: int = LIMITE_OFERTAS_POR_CICLO
) -> dict:

    pendientes = obtener_compras_pendientes_ofertas(
        db=db,
        limite=limite
    )

    if not pendientes:
        return {
            "pendientes": 0,
            "actualizadas": 0,
            "fallidas": 0
        }

    print(
        f"Iniciando actualización de ofertas: "
        f"{len(pendientes)} compras pendientes"
    )

    compras_por_codigo = {
        compra.codigo: compra
        for compra in pendientes
    }

    codigos = list(compras_por_codigo.keys())

    resultados = {}

    def consultar_ofertas(codigo: str):
        try:
            total = cliente_buscador.obtener_total_ofertas(
                codigo
            )

            if total is None:
                raise ValueError(
                    "La ficha no entregó total_ofertas_recibidas"
                )

            return codigo, int(total), None

        except Exception as error:
            return codigo, None, str(error)

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS_OFERTAS
    ) as executor:

        for codigo, total, error in executor.map(
            consultar_ofertas,
            codigos
        ):
            resultados[codigo] = {
                "total": total,
                "error": error
            }

    actualizadas = 0
    fallidas = 0

    try:
        for codigo, resultado in resultados.items():

            compra = compras_por_codigo[codigo]

            if resultado["error"] is None:

                guardar_total_ofertas(
                    db=db,
                    compra=compra,
                    total_ofertas=resultado["total"]
                )

                actualizadas += 1

            else:
                registrar_fallo_actualizacion(
                    compra=compra
                )

                fallidas += 1

                print(
                    f"Error obteniendo ofertas de {codigo}: "
                    f"{resultado['error']}"
                )

        db.commit()

    except Exception:
        db.rollback()
        raise

    return {
        "pendientes": len(pendientes),
        "actualizadas": actualizadas,
        "fallidas": fallidas
    }


def sincronizar_todas_las_regiones(
    db: Session,
    dias: int | None = None,
    horas: int | None = TTL_POR_DEFECTO_HORAS,
    region_id: int | None = None
) -> dict:

    inicio = perf_counter()

    resultado_regiones = []

    compras_procesadas = 0
    compras_omitidas = 0
    paginas_recorridas = 0

    if region_id is not None:
        regiones_a_procesar = [
            (id_region, nombre_region)
            for id_region, nombre_region in REGIONES
            if id_region == region_id
        ]
    else:
        regiones_a_procesar = REGIONES

    for region_id, region_nombre in regiones_a_procesar:
        print(f"Iniciando sincronización: {region_nombre}")

        resultado = sincronizar_region(
            db=db,
            region_id=region_id,
            region_nombre=region_nombre,
            dias=dias,
            horas=horas
        )

        resultado_regiones.append(resultado)

        compras_procesadas += resultado.get("procesadas", 0)

        compras_omitidas += resultado.get("omitidas", 0)

        paginas_recorridas += resultado.get("paginas", 0)


    tiempo_segundos = round(perf_counter() - inicio, 2)

    return {
        "regiones": len(regiones_a_procesar),
        "compras_procesadas": compras_procesadas,
        "compras_omitidas": compras_omitidas,
        "paginas_recorridas": paginas_recorridas,
        "tiempo_segundos": tiempo_segundos,
        "detalle_regiones": resultado_regiones
    }    


def reconciliar_todas_las_regiones(
    db: Session,
    dias: int = 1
) -> dict:

    inicio = perf_counter()

    total_marcadas = 0
    total_api = 0
    total_bd = 0
    regiones_reconciliadas = 0
    regiones_omitidas = 0

    detalle_regiones = []

    for region_id, region_nombre in REGIONES:

        print(
            f"Iniciando reconciliación diaria: "
            f"{region_nombre}"
        )

        try:
            (
                items_primera_pagina,
                paginacion,
                primera_pagina_correcta
            ) = obtener_pagina_reconciliacion(
                region_id=region_id,
                numero_pagina=1,
                dias=dias
            )

            if not primera_pagina_correcta:
                regiones_omitidas += 1

                detalle_regiones.append({
                    "region_id": region_id,
                    "region_nombre": region_nombre,
                    "reconciliada": False,
                    "error": "Falló la primera página"
                })

                continue

            total_paginas = paginacion.get(
                "total_paginas",
                1
            )

            todos_los_items = list(
                items_primera_pagina
            )

            region_completa = True

            if total_paginas > 1:

                with ThreadPoolExecutor(
                    max_workers=MAX_WORKERS
                ) as executor:

                    resultados = executor.map(
                        obtener_pagina_reconciliacion,
                        [region_id] * (total_paginas - 1),
                        range(2, total_paginas + 1),
                        [dias] * (total_paginas - 1)
                    )

                    for (
                        items_pagina,
                        _,
                        pagina_correcta
                    ) in resultados:

                        if not pagina_correcta:
                            region_completa = False
                            continue

                        todos_los_items.extend(
                            items_pagina
                        )

            # Seguridad principal:
            # si falló aunque sea una página, no se compara
            # ni se modifica ninguna compra de la región.
            if not region_completa:
                regiones_omitidas += 1

                detalle_regiones.append({
                    "region_id": region_id,
                    "region_nombre": region_nombre,
                    "reconciliada": False,
                    "paginas": total_paginas,
                    "error": (
                        "Falló una o más páginas. "
                        "No se modificó la región."
                    )
                })

                continue

            codigos_api = {
                item.get("codigo")
                for item in todos_los_items
                if item.get("codigo")
            }

            codigos_bd = (
                obtener_codigos_publicados_hoy_region(
                    db=db,
                    region_id=region_id,
                    dias=dias
                )
            )

            codigos_cancelados = (
                codigos_bd - codigos_api
            )

            marcadas = marcar_compras_no_publicadas(
                db=db,
                region_id=region_id,
                codigos=codigos_cancelados
            )

            db.commit()

            regiones_reconciliadas += 1
            total_marcadas += marcadas
            total_api += len(codigos_api)
            total_bd += len(codigos_bd)

            print(
                f"{region_nombre}: "
                f"API hoy={len(codigos_api)}, "
                f"BD hoy={len(codigos_bd)}, "
                f"no publicadas={marcadas}"
            )

            if codigos_cancelados:
                print(
                    f"Códigos marcados como no_publicada "
                    f"en {region_nombre}: "
                    f"{sorted(codigos_cancelados)}"
                )

            detalle_regiones.append({
                "region_id": region_id,
                "region_nombre": region_nombre,
                "reconciliada": True,
                "paginas": total_paginas,
                "codigos_api_hoy": len(codigos_api),
                "codigos_bd_hoy": len(codigos_bd),
                "marcadas_no_publicadas": marcadas,
                "codigos_marcados": sorted(
                    codigos_cancelados
                )
            })

        except Exception as error:
            db.rollback()

            regiones_omitidas += 1

            print(
                f"Error reconciliando {region_nombre}: "
                f"{error}"
            )

            detalle_regiones.append({
                "region_id": region_id,
                "region_nombre": region_nombre,
                "reconciliada": False,
                "error": str(error)
            })

    tiempo_segundos = round(
        perf_counter() - inicio,
        2
    )

    return {
        "regiones_totales": len(REGIONES),
        "regiones_reconciliadas":
            regiones_reconciliadas,
        "regiones_omitidas": regiones_omitidas,
        "compras_api_hoy": total_api,
        "compras_bd_hoy": total_bd,
        "marcadas_no_publicadas":
            total_marcadas,
        "tiempo_segundos": tiempo_segundos,
        "detalle_regiones": detalle_regiones
    }