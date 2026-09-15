from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


ultimo_analisis = {
    "ganado": 0,
    "video": None
}

class Analisis(BaseModel):
    ganado: int
    personas: int
    video: str | None = None

@app.post("/subir-analisis")
def subir_analisis(datos: Analisis):
    global ultimo_analisis
    ultimo_analisis = datos.dict()
    return {"mensaje": "Análisis recibido"}

@app.get("/analisis")
def obtener_analisis():
    return ultimo_analisis
