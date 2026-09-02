from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import json
import os

app = FastAPI()

# Archivo donde se guardan los resultados
RESULTADOS_PATH = "resultados.json"

# Modelo de datos
class Analisis(BaseModel):
    fecha: str
    ganado: int
    duracion: str
    video_url: str = ""

# ─── ENDPOINTS ────────────────────────────────────────────────

@app.get("/analisis")
def obtener_ultimo_analisis():
    """Devuelve el último análisis realizado."""
    if not os.path.exists(RESULTADOS_PATH):
        return {"ganado": 0, "duracion": "00:00", "fecha": "", "video_url": ""}
    
    with open(RESULTADOS_PATH, "r") as f:
        resultados = json.load(f)
    
    if not resultados:
        return {"ganado": 0, "duracion": "00:00", "fecha": "", "video_url": ""}
    
    return resultados[-1]  # Devuelve el más reciente

@app.get("/historial")
def obtener_historial():
    """Devuelve todos los análisis guardados."""
    if not os.path.exists(RESULTADOS_PATH):
        return []
    
    with open(RESULTADOS_PATH, "r") as f:
        resultados = json.load(f)
    
    return resultados[::-1]  # Más reciente primero

@app.post("/analisis")
def guardar_analisis(analisis: Analisis):
    """Recibe el resultado desde la PC y lo guarda."""
    resultados = []
    
    if os.path.exists(RESULTADOS_PATH):
        with open(RESULTADOS_PATH, "r") as f:
            resultados = json.load(f)
    
    resultados.append(analisis.dict())
    
    with open(RESULTADOS_PATH, "w") as f:
        json.dump(resultados, f, indent=2)
    
    return {"status": "ok", "ganado": analisis.ganado}
