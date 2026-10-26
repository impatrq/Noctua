from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from typing import Optional
from datetime import datetime
import os


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="NYCTUS API",
    description="API del sistema de monitoreo de ganado",
    version="1.1"
)


# ============================================================
# CARPETAS DE VIDEOS
# ============================================================

CARPETA_VIDEOS = "videos"
CARPETA_PROCESADOS = "videos/procesados"  # videos ya analizados por la IA

os.makedirs(CARPETA_VIDEOS, exist_ok=True)
os.makedirs(CARPETA_PROCESADOS, exist_ok=True)

EXTENSIONES_PERMITIDAS = [".mp4", ".mov", ".avi", ".mkv"]


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


# Indica si existe una orden pendiente (Flutter -> Raspberry)
analisis_pendiente = False


# Indica si actualmente hay un video crudo esperando ser procesado por la IA
video_recibido = False


# Nombre del último video recibido (crudo, de la Raspberry)
ultimo_video = None


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
# CONSULTAR SI EXISTE UNA ORDEN (la consulta la Raspberry)
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

    if extension not in EXTENSIONES_PERMITIDAS:

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
# CONSULTAR SI HAY UN VIDEO CRUDO PENDIENTE DE ANÁLISIS
# (la consulta el worker de IA en la notebook)
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
# CONFIRMAR QUE LA IA YA TOMÓ EL VIDEO CRUDO
# (sin esto, /video-pendiente seguiría devolviendo "disponible"
#  para siempre, aunque ya se haya procesado)
# ============================================================

@app.post("/video-pendiente/confirmar")
def confirmar_video_pendiente():

    global video_recibido

    video_recibido = False

    return {

        "mensaje": "Video marcado como tomado por la IA"
    }


# ============================================================
# DESCARGAR EL VIDEO CRUDO (lo pide el worker de IA)
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
# RECIBIR RESULTADO DE LA IA (datos + video procesado)
# ============================================================

@app.post("/subir-analisis")
async def subir_analisis(
    ganado: int = Form(...),
    personas: int = Form(0),
    duracion: float = Form(0),
    fecha: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):

    global ultimo_analisis
    global historial

    # --------------------------------------------------------
    # Fecha
    # --------------------------------------------------------

    if fecha is None:

        fecha = datetime.now().isoformat()

    # --------------------------------------------------------
    # Guardar el video procesado, si vino uno
    # --------------------------------------------------------

    nombre_video_procesado = None

    if file is not None and file.filename:

        extension = os.path.splitext(
            file.filename
        )[1].lower()

        if extension not in EXTENSIONES_PERMITIDAS:

            raise HTTPException(
                status_code=400,
                detail="Formato de video no permitido"
            )

        # Nombre único por fecha para no pisar análisis anteriores
        nombre_video_procesado = (
            "analisis_" + fecha.replace(":", "-") + extension
        )

        ruta_procesado = os.path.join(
            CARPETA_PROCESADOS,
            nombre_video_procesado
        )

        with open(ruta_procesado, "wb") as archivo:

            while True:

                contenido = await file.read(1024 * 1024)

                if not contenido:
                    break

                archivo.write(contenido)

    # --------------------------------------------------------
    # Crear resultado
    # --------------------------------------------------------

    resultado = {

        "ganado": ganado,

        "personas": personas,

        "video": nombre_video_procesado,

        "duracion": duracion,

        "fecha": fecha
    }

    # --------------------------------------------------------
    # Actualizar último análisis y agregar al historial
    # --------------------------------------------------------

    ultimo_analisis = resultado

    historial.insert(
        0,
        resultado
    )

    print()
    print("========================================")
    print("      ANALISIS RECIBIDO - NYCTUS")
    print("========================================")
    print("Ganado:", ganado)
    print("Video procesado:", nombre_video_procesado)
    print("========================================")
    print()

    return {

        "mensaje": "Análisis recibido correctamente",

        "resultado": resultado
    }


# ============================================================
# DESCARGAR EL VIDEO YA PROCESADO (lo pide Flutter)
# ============================================================

@app.get("/video-analisis/{nombre}")
def descargar_video_analisis(nombre: str):

    # nombre viene de ultimo_analisis["video"] o de un item del historial
    ruta = os.path.join(CARPETA_PROCESADOS, nombre)

    if not os.path.exists(ruta):

        raise HTTPException(
            status_code=404,
            detail="El video procesado no existe"
        )

    return FileResponse(

        path=ruta,

        media_type="video/mp4",

        filename=nombre
    )
