import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

ZONA_CHILE = ZoneInfo("America/Santiago")


class FormatterChile(logging.Formatter):

    def formatTime(self, record, datefmt=None):
        fecha = datetime.fromtimestamp(
            record.created,
            ZONA_CHILE
        )

        if datefmt:
            return fecha.strftime(datefmt)

        return fecha.isoformat()


LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)


def crear_logger(nombre: str, archivo: str) -> logging.Logger:
    logger = logging.getLogger(nombre)

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    formato = FormatterChile(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    handler_archivo = RotatingFileHandler(
        LOGS_DIR / archivo,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    handler_archivo.setFormatter(formato)

    handler_consola = logging.StreamHandler()
    handler_consola.setFormatter(formato)

    logger.addHandler(handler_archivo)
    logger.addHandler(handler_consola)

    return logger


logger_compras = crear_logger(
    nombre="compras",
    archivo="compras.log"
)

logger_ofertas = crear_logger(
    nombre="ofertas",
    archivo="ofertas.log"
)

logger_errores = crear_logger(
    nombre="errores",
    archivo="errores.log"
)