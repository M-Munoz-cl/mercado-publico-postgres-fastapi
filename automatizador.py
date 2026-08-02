import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from app.logger import logger_compras, logger_ofertas, logger_errores

from app.database import SessionLocal
from app.sincronizador import (
    actualizar_ofertas_reales,
    sincronizar_todas_las_regiones,
    reconciliar_todas_las_regiones
)
import os
from dotenv import load_dotenv

load_dotenv()

ZONA_CHILE = ZoneInfo("America/Santiago")


INTERVALO_COMPRAS_DIA = int(os.getenv("INTERVALO_COMPRAS_DIA", 240))         # 4 minutos
INTERVALO_COMPRAS_NOCHE_TEMPRANA = int(os.getenv("INTERVALO_COMPRAS_NOCHE_TEMPRANA", 900))   # 15 minutos
INTERVALO_COMPRAS_MADRUGADA = int(os.getenv("INTERVALO_COMPRAS_MADRUGADA", 1200))  # 20 minutos

INTERVALO_OFERTAS = int(os.getenv("INTERVALO_OFERTAS", 300))   # 5 minutos

HORAS_VENTANA = int(os.getenv("HORAS_VENTANA", 2))

HORA_RECONCILIACION = int(os.getenv("HORA_RECONCILIACION", 23))
MINUTO_RECONCILIACION = int(os.getenv("MINUTO_RECONCILIACION", 30))


def ejecutar_sincronizacion_compras():
    db = SessionLocal()

    try:
        inicio = datetime.now(ZONA_CHILE)

        print(
            f"\n[{inicio:%Y-%m-%d %H:%M:%S}] "
            "[COMPRAS] Iniciando sincronización automática"
        )
        logger_compras.info("Iniciando sincronización")

        resultado = sincronizar_todas_las_regiones(
            db=db,
            dias=None,
            horas=HORAS_VENTANA,
            region_id=None
        )

        fin = datetime.now(ZONA_CHILE)
        duracion = (fin - inicio).total_seconds()

        print(
            f"[{fin:%Y-%m-%d %H:%M:%S}] "
            f"[COMPRAS] Sincronización terminada "
            f"en {duracion:.2f} segundos"
        )
        logger_compras.info(
            "Sincronización terminada en %.2f segundos",
            duracion
        )


        print(f"[COMPRAS] Resultado: {resultado}")
        logger_compras.info("Resultado: %s", resultado)

    except Exception as error:
        db.rollback()

        print(
            f"[{datetime.now(ZONA_CHILE):%Y-%m-%d %H:%M:%S}] "
            f"[COMPRAS] Error en sincronización: {error}"
        )
        logger_errores.exception("Error en la sincronización de compras")

    finally:
        db.close()


def ejecutar_actualizacion_ofertas():
    db = SessionLocal()

    try:
        inicio = datetime.now(ZONA_CHILE)

        print(
            f"\n[{inicio:%Y-%m-%d %H:%M:%S}] "
            "[OFERTAS] Iniciando actualización"
        )
        logger_ofertas.info("Iniciando actualización de ofertas")

        resultado = actualizar_ofertas_reales(
            db=db
        )

        fin = datetime.now(ZONA_CHILE)
        duracion = (fin - inicio).total_seconds()

        print(
            f"[{fin:%Y-%m-%d %H:%M:%S}] "
            f"[OFERTAS] Actualización terminada "
            f"en {duracion:.2f} segundos"
        )
        logger_ofertas.info("Actualización terminada en %.2f segundos", duracion)

        print(f"[OFERTAS] Resultado: {resultado}")
        logger_ofertas.info("Resultado: %s", resultado)

    except Exception as error:
        db.rollback()

        print(
            f"[{datetime.now(ZONA_CHILE):%Y-%m-%d %H:%M:%S}] "
            f"[OFERTAS] Error en actualización: {error}"
        )
        logger_errores.exception("Error en la actualización de ofertas")

    finally:
        db.close()


def ejecutar_reconciliacion():
    db = SessionLocal()

    try:
        inicio = datetime.now(ZONA_CHILE)

        print(
            f"\n[{inicio:%Y-%m-%d %H:%M:%S}] "
            "[RECONCILIACION] Iniciando reconciliación diaria"
        )
        logger_compras.info(
            "Iniciando reconciliación diaria"
        )

        resultado = reconciliar_todas_las_regiones(
            db=db
        )

        fin = datetime.now(ZONA_CHILE)
        duracion = (fin - inicio).total_seconds()

        print(
            f"[{fin:%Y-%m-%d %H:%M:%S}] "
            f"[RECONCILIACION] Reconciliación terminada "
            f"en {duracion:.2f} segundos"
        )

        print(
            f"[RECONCILIACION] Resultado: {resultado}"
        )

        logger_compras.info(
            "Reconciliación terminada en %.2f segundos",
            duracion
        )
        logger_compras.info(
            "Resultado reconciliación: %s",
            resultado
        )

    except Exception as error:
        db.rollback()

        print(
            f"[{datetime.now(ZONA_CHILE):%Y-%m-%d %H:%M:%S}] "
            f"[RECONCILIACION] Error: {error}"
        )

        logger_errores.exception(
            "Error en la reconciliación diaria"
        )

    finally:
        db.close()


def obtener_intervalo_compras():
    hora_actual = datetime.now(ZONA_CHILE).hour

    # Desde las 00:00 hasta antes de las 06:00
    if 0 <= hora_actual < 6:
        return INTERVALO_COMPRAS_MADRUGADA

    # Desde las 21:00 hasta antes de las 00:00
    if 21 <= hora_actual < 24:
        return INTERVALO_COMPRAS_NOCHE_TEMPRANA

    # Desde las 06:00 hasta antes de las 21:00
    return INTERVALO_COMPRAS_DIA


def ciclo_compras():
    while True:
        ejecutar_sincronizacion_compras()

        intervalo_compras = obtener_intervalo_compras()
        intervalo_minutos = intervalo_compras // 60

        ahora = datetime.now(ZONA_CHILE)

        print(
            f"[COMPRAS] Hora actual: {ahora:%H:%M}. "
            f"Esperando {intervalo_minutos} minutos "
            "para el próximo recorrido..."
        )

        logger_compras.info(
            "Hora actual: %s. Esperando %s minutos para el próximo recorrido",
            ahora.strftime("%H:%M"),
            intervalo_minutos
        )

        time.sleep(intervalo_compras)


def ciclo_ofertas():
    while True:
        ejecutar_actualizacion_ofertas()

        intervalo_minutos = INTERVALO_OFERTAS // 60

        print(
            f"[OFERTAS] Esperando {intervalo_minutos} minutos "
            "para la próxima actualización..."
        )
        logger_ofertas.info("Esperando %s minutos para la próxima actualización", intervalo_minutos)

        time.sleep(INTERVALO_OFERTAS)


def ciclo_reconciliacion():
    while True:
        ahora = datetime.now(ZONA_CHILE)

        proxima_ejecucion = ahora.replace(
            hour=HORA_RECONCILIACION,
            minute=MINUTO_RECONCILIACION,
            second=0,
            microsecond=0
        )

        if proxima_ejecucion <= ahora:
            proxima_ejecucion += timedelta(days=1)

        segundos_espera = (
            proxima_ejecucion - ahora
        ).total_seconds()

        print(
            "[RECONCILIACION] Próxima ejecución: "
            f"{proxima_ejecucion:%Y-%m-%d %H:%M:%S}"
        )

        logger_compras.info(
            "Próxima reconciliación: %s",
            proxima_ejecucion.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )

        time.sleep(segundos_espera)

        ejecutar_reconciliacion()


def iniciar_automatizador():
    print("Automatizador iniciado")
    logger_compras.info("Automatizador iniciado")
    logger_ofertas.info("Automatizador iniciado")
    print(
        f"Compras: ventana de {HORAS_VENTANA} horas\n"
        f"  06:00–21:00: cada {INTERVALO_COMPRAS_DIA // 60} minutos\n"
        f"  21:00–00:00: cada "
        f"{INTERVALO_COMPRAS_NOCHE_TEMPRANA // 60} minutos\n"
        f"  00:00–06:00: cada "
        f"{INTERVALO_COMPRAS_MADRUGADA // 60} minutos"
    )
    print(
        f"Ofertas: cada {INTERVALO_OFERTAS // 60} minutos"
    )

    print(
        f"Reconciliación diaria: "
        f"{HORA_RECONCILIACION:02d}:{MINUTO_RECONCILIACION:02d}"
    )

    hilo_compras = threading.Thread(
        target=ciclo_compras,
        name="hilo-compras",
        daemon=True
    )

    hilo_ofertas = threading.Thread(
        target=ciclo_ofertas,
        name="hilo-ofertas",
        daemon=True
    )

    hilo_reconciliacion = threading.Thread(
        target=ciclo_reconciliacion,
        name="hilo-reconciliacion",
        daemon=True
    )

    hilo_compras.start()
    hilo_ofertas.start()
    hilo_reconciliacion.start()

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nAutomatizador detenido por el usuario.")
        logger_compras.info("Automatizador detenido por el usuario")
        logger_ofertas.info("Automatizador detenido por el usuario")

if __name__ == "__main__":
    iniciar_automatizador()