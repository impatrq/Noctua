import os

DATASET_FINAL = "C:/Users/juanc/OneDrive/Desktop/DATASET_FINAL"  # Cambiá si la ruta es diferente

for split in ["train", "valid", "test"]:
    ruta = os.path.join(DATASET_FINAL, split, "images")
    if os.path.exists(ruta):
        cantidad = len(os.listdir(ruta))
        print(f"{split}: {cantidad} imágenes")