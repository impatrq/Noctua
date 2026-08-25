from fastapi import FastAPI

app = FastAPI()

@app.get("/analisis")
def obtener_analisis():
    return {
        "ganado": 200,
        "personas": 2
    }
