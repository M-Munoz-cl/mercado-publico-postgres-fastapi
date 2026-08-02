import time
import threading

import requests
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN_URL = "https://servicios-prd.mercadopublico.cl/v1/auth/publico"
FICHA_URL = "https://api.buscador.mercadopublico.cl/compra-agil"
API_KEY = os.getenv("API_KEY")

if not API_KEY:
    raise ValueError("No se encontró API_KEY en el archivo .env")


class ClienteBuscador:
    def __init__(self):
        self.token = None
        self.token_expira_en = 0
        self.lock_token = threading.Lock()

        # Cada worker tendrá su propia Session
        self.sesiones_por_hilo = threading.local()

    def obtener_session(self):
        if not hasattr(self.sesiones_por_hilo, "session"):
            session = requests.Session()

            session.headers.update({
                "x-api-key": API_KEY,
                "Accept": "application/json",
                "Origin": "https://buscador.mercadopublico.cl",
                "Referer": "https://buscador.mercadopublico.cl/",
            })

            self.sesiones_por_hilo.session = session

        return self.sesiones_por_hilo.session

    def obtener_token(self, forzar=False):
        ahora = time.time()

        if (
            not forzar
            and self.token
            and ahora < self.token_expira_en - 300
        ):
            return self.token

        with self.lock_token:
            ahora = time.time()

            if (
                not forzar
                and self.token
                and ahora < self.token_expira_en - 300
            ):
                return self.token

            response = requests.get(
                TOKEN_URL,
                timeout=(3, 5)
            )

            response.raise_for_status()

            payload = response.json().get("payload") or {}

            token = payload.get("access_token")
            expires_in = int(payload.get("expires_in", 3600))

            if not token:
                raise ValueError(
                    "La API de autenticación no entregó access_token"
                )

            self.token = token
            self.token_expira_en = ahora + expires_in

            return self.token

    def obtener_total_ofertas(self, codigo):
        token = self.obtener_token()
        session = self.obtener_session()

        response = session.get(
            FICHA_URL,
            headers={
                "Authorization": f"Bearer {token}"
            },
            params={
                "action": "ficha",
                "code": codigo,
            },
            timeout=(3, 8)
        )

        if response.status_code == 401:
            token = self.obtener_token(forzar=True)

            response = session.get(
                FICHA_URL,
                headers={
                    "Authorization": f"Bearer {token}"
                },
                params={
                    "action": "ficha",
                    "code": codigo,
                },
                timeout=(3, 8)
            )

        response.raise_for_status()

        payload = response.json().get("payload") or {}

        return payload.get("total_ofertas_recibidas")


    def obtener_total_ofertas_manual(self, codigo):
        token = self.obtener_token()
        session = self.obtener_session()
    
        response = session.get(
            FICHA_URL,
            headers={
                "Authorization": f"Bearer {token}"
            },
            params={
                "action": "ficha",
                "code": codigo,
            },
            timeout=(3, 30)
        )
    
        if response.status_code == 401:
            token = self.obtener_token(forzar=True)
    
            response = session.get(
                FICHA_URL,
                headers={
                    "Authorization": f"Bearer {token}"
                },
                params={
                    "action": "ficha",
                    "code": codigo,
                },
                timeout=(3, 30)
            )
    
        response.raise_for_status()
    
        payload = response.json().get("payload") or {}
    
        return payload.get("total_ofertas_recibidas")