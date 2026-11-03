
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from threading import Lock
import os
import time
import uuid

app = FastAPI(
    title="NYCTUS API",
    description="API del sistema de monitoreo de ganado",
    version="2.0"
)

# ============================================================
# CARPETAS
# ============================================================

CARPETA_VIDEOS = "videos"
CARPETA_PROCESADOS = os.path.join(CARPETA_VIDEOS, "procesados")

os.makedirs(CARPETA_VIDEOS, exist_ok=True)
os.makedirs(CARPETA_PROCESADOS, exist_ok=True)

EXTENSIONES_PERMITIDAS = {".mp4", ".mov", ".avi", ".mkv"}

# ============================================================
# ESTADO GENERAL
# ============================================================

lock = Lock()

ultimo_analisis = {
    "ganado": 0,
    "personas": 0,
    "video": None,
    "labels": None,
    "duracion": 0,
    "fecha": None
}

historial = []

analisis_pendiente = False
video_recibido = False
ultimo_video = None

estado_analisis = {
    "estado": "inactivo",
    "progreso": 0,
    "mensaje": "No hay ningún análisis en curso",
    "fecha_inicio": None,
    "fecha_actualizacion": None,
    "error": None
}

worker = {
    "online": False,
    "ultimo_contacto": 0
}

TIEMPO_LIMITE_WORKER = 30


def actualizar_estado(estado=None, progreso=None, mensaje=None, error=None):
    with lock:
        if estado is not None:
            estado_analisis["estado"] = estado

        if progreso is not None:
            estado_analisis["progreso"] = max(0, min(100, int(progreso)))

        if mensaje is not None:
            estado_analisis["mensaje"] = mensaje

        if error is not None:
            estado_analisis["error"] = error

        estado_analisis["fecha_actualizacion"] = datetime.now().isoformat()


def analisis_activo():
    return estado_analisis["estado"] in {
        "pendiente",
        "grabando",
        "subiendo",
        "esperando_ia",
        "procesando",
        "comprimiendo"
    }


def worker_conectado():
    conectado = time.time() - worker["ultimo_contacto"] <= TIEMPO_LIMITE_WORKER
    worker["online"] = conectado
    return conectado


def nombre_seguro(nombre):
    return os.path.basename(nombre)


# ============================================================
# MODELOS PARA ACTUALIZAR ESTADOS
# ============================================================

class ActualizacionEstado(BaseModel):
    estado: Optional[str] = None
    progreso: Optional[int] = None
    mensaje: Optional[str] = None
    error: Optional[str] = None


# ============================================================
# INICIO
# ============================================================

@app.get("/")
def inicio():
    return {
        "mensaje": "NYCTUS API funcionando",
        "estado": "online",
        "version": "2.0"
    }


# ============================================================
# ESTADO PARA FLUTTER
# ============================================================

@app.get("/estado")
def obtener_estado():
    with lock:
        resultado = dict(estado_analisis)

    resultado["worker_online"] = worker_conectado()
    resultado["worker_ultimo_contacto"] = (
        datetime.fromtimestamp(worker["ultimo_contacto"]).isoformat()
        if worker["ultimo_contacto"] else None
    )

    return resultado


@app.post("/estado/actualizar")
def cambiar_estado(datos: ActualizacionEstado):
    estados_validos = {
        "pendiente",
        "grabando",
        "subiendo",
        "esperando_ia",
        "procesando",
        "comprimiendo",
        "completado",
        "error"
    }

    if datos.estado is not None and datos.estado not in estados_validos:
        raise HTTPException(status_code=400, detail="Estado no válido")

    actualizar_estado(
        estado=datos.estado,
        progreso=datos.progreso,
        mensaje=datos.mensaje,
        error=datos.error
    )

    return {"mensaje": "Estado actualizado", **estado_analisis}


@app.post("/estado/error")
def informar_error(datos: ActualizacionEstado):
    actualizar_estado(
        estado="error",
        mensaje=datos.mensaje or "Ocurrió un error durante el análisis",
        error=datos.error or datos.mensaje or "Error desconocido"
    )

    return {"mensaje": "Error registrado"}


# ============================================================
# HEARTBEAT DE LA COMPUTADORA CON YOLO
# ============================================================

@app.post("/worker/heartbeat")
def heartbeat_worker():
    worker["ultimo_contacto"] = time.time()
    worker["online"] = True

    return {
        "mensaje": "Worker conectado",
        "online": True
    }


@app.get("/worker/estado")
def estado_worker():
    return {"online": worker_conectado()}


# ============================================================
# ÚLTIMO ANÁLISIS
# ============================================================

@app.get("/analisis")
def obtener_analisis():
    return ultimo_analisis


# ============================================================
# HISTORIAL
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
    global video_recibido
    global ultimo_video

    with lock:
        if analisis_activo():
            raise HTTPException(
                status_code=409,
                detail="Ya existe un análisis en curso"
            )

        analisis_pendiente = True
        video_recibido = False
        ultimo_video = None

        estado_analisis.update({
            "estado": "pendiente",
            "progreso": 0,
            "mensaje": "Solicitud recibida. Esperando a la Raspberry Pi",
            "fecha_inicio": datetime.now().isoformat(),
            "fecha_actualizacion": datetime.now().isoformat(),
            "error": None
        })

    return {
        "mensaje": "Nuevo análisis solicitado",
        "estado": "pendiente"
    }


# ============================================================
# RASPBERRY: CONSULTAR ORDEN
# ============================================================

@app.get("/pendientes")
def comprobar_pendiente():
    if analisis_pendiente:
        return {"accion": "analizar"}

    return {"accion": "esperar"}


# ============================================================
# RASPBERRY: CONFIRMAR ORDEN
# ============================================================

@app.post("/pendientes/confirmar")
def confirmar_pendiente():
    global analisis_pendiente

    analisis_pendiente = False

    return {"mensaje": "Orden confirmada"}


# ============================================================
# RASPBERRY: SUBIR VIDEO ORIGINAL
# ============================================================

@app.post("/subir-video")
async def subir_video(file: UploadFile = File(...)):
    global video_recibido
    global ultimo_video

    if not file.filename:
        raise HTTPException(status_code=400, detail="No se recibió ningún archivo")

    extension = os.path.splitext(file.filename)[1].lower()

    if extension not in EXTENSIONES_PERMITIDAS:
        raise HTTPException(status_code=400, detail="Formato de video no permitido")

    nombre_video = "video_nyctus" + extension
    ruta_video = os.path.join(CARPETA_VIDEOS, nombre_video)

    try:
        with open(ruta_video, "wb") as archivo:
            while True:
                contenido = await file.read(1024 * 1024)
                if not contenido:
                    break
                archivo.write(contenido)
    finally:
        await file.close()

    video_recibido = True
    ultimo_video = nombre_video

    actualizar_estado(
        estado="esperando_ia",
        progreso=15,
        mensaje="Video recibido. Esperando que la computadora lo procese"
    )

    print("VIDEO RECIBIDO:", nombre_video)

    return {
        "mensaje": "Video recibido correctamente",
        "video": nombre_video,
        "estado": "recibido"
    }


# ============================================================
# WORKER: CONSULTAR VIDEO PENDIENTE
# ============================================================

@app.get("/video-pendiente")
def consultar_video():
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
# WORKER: CONFIRMAR QUE TOMÓ EL VIDEO
# ============================================================

@app.post("/video-pendiente/confirmar")
def confirmar_video_pendiente():
    global video_recibido

    video_recibido = False

    actualizar_estado(
        estado="procesando",
        progreso=20,
        mensaje="La computadora comenzó el análisis con inteligencia artificial"
    )

    return {"mensaje": "Video marcado como tomado por la IA"}


# ============================================================
# WORKER: DESCARGAR VIDEO ORIGINAL
# ============================================================

@app.get("/descargar-video")
def descargar_video():
    if ultimo_video is None:
        raise HTTPException(status_code=404, detail="No hay ningún video disponible")

    ruta_video = os.path.join(CARPETA_VIDEOS, nombre_seguro(ultimo_video))

    if not os.path.exists(ruta_video):
        raise HTTPException(status_code=404, detail="El archivo de video no existe")

    return FileResponse(
        path=ruta_video,
        media_type="video/mp4",
        filename=nombre_seguro(ultimo_video)
    )


# ============================================================
# WORKER: SUBIR RESULTADO PROCESADO
# ============================================================

@app.post("/subir-analisis")
async def subir_analisis(
    ganado: int = Form(...),
    personas: int = Form(0),
    duracion: float = Form(0),
    fecha: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    global ultimo_analisis
    global historial

    if fecha is None:
        fecha = datetime.now().isoformat()

    nombre_video_procesado = None

    if file is not None and file.filename:
        extension = os.path.splitext(file.filename)[1].lower()

        if extension not in EXTENSIONES_PERMITIDAS:
            raise HTTPException(status_code=400, detail="Formato de video no permitido")

        identificador = uuid.uuid4().hex[:8]
        nombre_video_procesado = f"analisis_{identificador}{extension}"
        ruta_procesado = os.path.join(CARPETA_PROCESADOS, nombre_video_procesado)

        try:
            with open(ruta_procesado, "wb") as archivo:
                while True:
                    contenido = await file.read(1024 * 1024)
                    if not contenido:
                        break
                    archivo.write(contenido)
        finally:
            await file.close()

    resultado = {
        "ganado": ganado,
        "personas": personas,
        "video": nombre_video_procesado,
        "duracion": duracion,
        "fecha": fecha
    }

    ultimo_analisis = resultado
    historial.insert(0, resultado)

    actualizar_estado(
        estado="completado",
        progreso=100,
        mensaje="Análisis terminado correctamente",
        error=None
    )

    print("ANÁLISIS COMPLETADO")
    print("Ganado:", ganado)
    print("Video:", nombre_video_procesado)

    return {
        "mensaje": "Análisis recibido correctamente",
        "resultado": resultado
    }


# ============================================================
# FLUTTER: DESCARGAR VIDEO PROCESADO
# ============================================================

@app.get("/video-analisis/{nombre}")
def descargar_video_analisis(nombre: str):
    nombre = nombre_seguro(nombre)
    ruta = os.path.join(CARPETA_PROCESADOS, nombre)

    if not os.path.exists(ruta):
        raise HTTPException(status_code=404, detail="El video procesado no existe")

    return FileResponse(
        path=ruta,
        media_type="video/mp4",
        filename=nombre
    )
