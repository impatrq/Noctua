from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="NYCTUS API",
    description="API del sistema de monitoreo de ganado",
    version="1.0"
)


# ============================================================
# VARIABLES TEMPORALES
# ============================================================

# Último análisis recibido
ultimo_analisis = {

    "ganado": 0,

    "personas": 0,

    "video": None,

    "labels": None,

    "duracion": 0,

    "fecha": None
}


# Historial de análisis
historial = []


# Indica si existe una orden pendiente
analisis_pendiente = False


# ============================================================
# MODELO DE DATOS
# ============================================================

class ResultadoAnalisis(BaseModel):

    ganado: int

    personas: int = 0

    video: Optional[str] = None

    labels: Optional[str] = None

    duracion: float = 0

    fecha: Optional[str] = None


# ============================================================
# RUTA PRINCIPAL
# ============================================================

@app.get("/")
def inicio():

    return {
        "mensaje": "NYCTUS API funcionando",
        "estado": "online"
    }


# ============================================================
# OBTENER ÚLTIMO ANÁLISIS
# ============================================================

@app.get("/analisis")
def obtener_analisis():

    return ultimo_analisis


# ============================================================
# OBTENER HISTORIAL
# ============================================================

@app.get("/historial")
def obtener_historial():

    return historial


# ============================================================
# SOLICITAR NUEVO ANÁLISIS
# ============================================================

@app.post("/nuevo-analisis")
def nuevo_analisis():

    global analisis_pendiente

    analisis_pendiente = True

    return {

        "mensaje": "Nuevo análisis solicitado",

        "estado": "pendiente"
    }


# ============================================================
# CONSULTAR SI EXISTE UNA ORDEN
# ============================================================

@app.get("/pendientes")
def comprobar_pendiente():

    global analisis_pendiente

    if analisis_pendiente:

        return {

            "accion": "analizar"
        }

    return {

        "accion": "esperar"
    }


# ============================================================
# CONFIRMAR QUE LA RASPBERRY TOMÓ LA ORDEN
# ============================================================

@app.post("/pendientes/confirmar")
def confirmar_pendiente():

    global analisis_pendiente

    analisis_pendiente = False

    return {

        "mensaje": "Orden confirmada"
    }


# ============================================================
# RECIBIR RESULTADO DE LA IA
# ============================================================

@app.post("/subir-analisis")
def subir_analisis(
    datos: ResultadoAnalisis
):

    global ultimo_analisis
    global historial

    # --------------------------------------------------------
    # Fecha
    # --------------------------------------------------------

    fecha = datos.fecha

    if fecha is None:

        fecha = datetime.now().isoformat()

    # --------------------------------------------------------
    # Crear resultado
    # --------------------------------------------------------

    resultado = {

        "ganado": datos.ganado,

        "personas": datos.personas,

        "video": datos.video,

        "labels": datos.labels,

        "duracion": datos.duracion,

        "fecha": fecha
    }

    # --------------------------------------------------------
    # Actualizar último análisis
    # --------------------------------------------------------

    ultimo_analisis = resultado

    # --------------------------------------------------------
    # Agregar al historial
    # --------------------------------------------------------

    historial.insert(
        0,
        resultado
    )

    return {

        "mensaje": "Análisis recibido correctamente",

        "resultado": resultado
    }
