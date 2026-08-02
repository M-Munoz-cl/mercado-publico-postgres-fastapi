from sqlalchemy import BigInteger, Column, DateTime, String, Text, SmallInteger
from sqlalchemy.sql import func
from app.database import Base


class CompraAgil(Base):
    # vinculada a tabla compras agiles
    __tablename__ = "compras_agiles"

    id = Column(BigInteger, primary_key=True, index=True)
    codigo = Column(String(50), unique=True, nullable=False, index=True)
    nombre = Column(Text, nullable=False)
    organismo = Column(String(255), nullable=True)
    region_id = Column(SmallInteger, nullable=False, index=True)
    region_nombre = Column(String(100), nullable=False)
    monto_disponible_clp = Column(BigInteger, nullable=True)
    estado_convocatoria = Column(SmallInteger,nullable=True,index=True)
    estado_codigo = Column(String(40), nullable=True, index=True)
    fecha_publicacion = Column(DateTime, nullable=True)
    fecha_cierre_primer_llamado = Column(DateTime(timezone=True), nullable=True)
    fecha_cierre_segundo_llamado = Column(DateTime(timezone=True),nullable=True)
    fecha_actualizacion = Column(DateTime(timezone=True),server_default=func.now(),nullable=False)
    total_ofertas_reales = Column(SmallInteger, nullable=True)
    fecha_actualizacion_ofertas = Column(DateTime(timezone=True), nullable=True)
    intentos_actualizacion_ofertas = Column(SmallInteger, nullable=False, default=0, server_default="0")
