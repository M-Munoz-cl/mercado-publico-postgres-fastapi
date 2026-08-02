from dotenv import load_dotenv
import os

load_dotenv()

TICKET = os.getenv("TICKET")

if not TICKET:
    raise ValueError("No se encontró TICKET en las variables de entorno")

BASE_URL = "https://api2.mercadopublico.cl"

HEADERS = {'ticket': TICKET}