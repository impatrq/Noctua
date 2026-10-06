from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import os


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="NYCTUS API",
    description="API del sistema de monitoreo de ganado",
    version="1.0"
)


# ============================================================
# CARPETA DE VIDEOS
# ============================================================

CARPETA_VIDEOS = "videos"

os.makedirs(CARPETA_VIDEOS, exist_ok=True)


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


# Indica si actualmente hay un video recibido
video_recibido = False


# Nombre del último video recibido
ultimo_video = None


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
# SUBIR VIDEO DESDE LA RASPBERRY
# ============================================================

@app.post("/subir-video")
async def subir_video(
    file: UploadFile = File(...)
):

    global video_recibido
    global ultimo_video

    # --------------------------------------------------------
    # Comprobar que sea un video
    # --------------------------------------------------------

    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail="No se recibió ningún archivo"
        )

    # --------------------------------------------------------
    # Comprobar extensión
    # --------------------------------------------------------

    extension = os.path.splitext(
        file.filename
    )[1].lower()

    extensiones_permitidas = [
        ".mp4",
        ".mov",
        ".avi",
        ".mkv"
    ]

    if extension not in extensiones_permitidas:

        raise HTTPException(
            status_code=400,
            detail="Formato de video no permitido"
        )

    # --------------------------------------------------------
    # Nombre seguro para el servidor
    # --------------------------------------------------------

    nombre_video = "video_nyctus" + extension

    ruta_video = os.path.join(
        CARPETA_VIDEOS,
        nombre_video
    )

    # --------------------------------------------------------
    # Guardar archivo
    # --------------------------------------------------------

    with open(ruta_video, "wb") as archivo:

        while True:

            contenido = await file.read(1024 * 1024)

            if not contenido:
                break

            archivo.write(contenido)

    # --------------------------------------------------------
    # Actualizar estado
    # --------------------------------------------------------

    video_recibido = True

    ultimo_video = nombre_video

    print()
    print("========================================")
    print("       VIDEO RECIBIDO - NYCTUS")
    print("========================================")
    print("Archivo:", nombre_video)
    print("Ruta:", ruta_video)
    print("========================================")
    print()

    return {

        "mensaje": "Video recibido correctamente",

        "video": nombre_video,

        "estado": "recibido"
    }


# ============================================================
# CONSULTAR SI HAY UN VIDEO RECIBIDO
# ============================================================

@app.get("/video-pendiente")
def consultar_video():

    global video_recibido
    global ultimo_video

    if video_recibido and ultimo_video:

        return {

            "estado": "disponible",

            "video": ultimo_video
        }

    return {

        "estado": "esperar",

        "video": None
    }


# ============================================================
# DESCARGAR EL VIDEO
# ============================================================

@app.get("/descargar-video")
def descargar_video():

    global ultimo_video

    if ultimo_video is None:

        raise HTTPException(
            status_code=404,
            detail="No hay ningún video disponible"
        )

    ruta_video = os.path.join(
        CARPETA_VIDEOS,
        ultimo_video
    )

    if not os.path.exists(ruta_video):

        raise HTTPException(
            status_code=404,
            detail="El archivo de video no existe"
        )

    return FileResponse(

        path=ruta_video,

        media_type="video/mp4",

        filename=ultimo_video
    )


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
