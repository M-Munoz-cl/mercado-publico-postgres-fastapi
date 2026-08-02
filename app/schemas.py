from datetime import datetime

from pydantic import BaseModel


class CompraAgilResponse(BaseModel):

    codigo: str
    nombre: str
    organismo: str | None

    region_id: int
    region_nombre: str

    monto_disponible_clp: int | None

    estado_convocatoria: int | None
    estado_codigo: str | None = None

    fecha_publicacion: datetime | None
    fecha_cierre_primer_llamado: datetime | None
    fecha_cierre_segundo_llamado: datetime | None

    total_ofertas_reales: int | None = None
    fecha_actualizacion_ofertas: datetime | None = None

    class Config:
        from_attributes = True
