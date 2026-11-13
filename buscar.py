from datetime import datetime
import os
import time
from dotenv import load_dotenv

from config import ConfigStore
from main import executar_busca

load_dotenv()

INTERVALO = int(os.getenv("BUSCA_INTERVALO_MINUTOS", "20"))

store = ConfigStore()

while True:
    print("\nExecutando busca...")
    executar_busca(store)

    print(f"Próxima busca em {INTERVALO} minutos.")
    print(f"[{datetime.now():%d/%m/%Y %H:%M:%S}] - Próxima busca em {INTERVALO} minutos.")
    time.sleep(INTERVALO * 60)