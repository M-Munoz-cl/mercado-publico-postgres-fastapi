import requests
import os 
from dotenv import load_dotenv

load_dotenv()


FASTAPI_URL = os.getenv("FASTAPI_URL", "http://127.0.0.1:8000")


def obtener_datos(
    region,
    llamado,
    fecha_inicio=None,
    fecha_fin=None,
    limite=9000,
    offset=0
):
    parametros = {
        "region_id": region,
        "estado_convocatoria": llamado,
        "limite": limite,
        "offset": offset
    }

    if fecha_inicio is not None:
        parametros["fecha_inicio"] = fecha_inicio.isoformat()

    if fecha_fin is not None:
        parametros["fecha_fin"] = fecha_fin.isoformat()

    try:
        response = requests.get(
            f"{FASTAPI_URL}/compras",
            params=parametros,
            timeout=30
        )

        if response.status_code != 200:
            print("Detalle del error:", response.text)

        response.raise_for_status()

        return response.json()

    except requests.RequestException as error:
        print(f"Error al consultar FastAPI: {error}")
        return []


def actualizar_ofertas_manual(
    codigo: str
) -> dict | None:

    try:
        response = requests.post(
            f"{FASTAPI_URL}/compras/{codigo}/actualizar-ofertas",
            timeout=40
        )

        if response.status_code != 200:
            print(
                "Error al actualizar ofertas:",
                response.text
            )

        response.raise_for_status()

        return response.json()

    except requests.RequestException as error:
        print(
            f"Error al actualizar ofertas de {codigo}: {error}"
        )
        return None