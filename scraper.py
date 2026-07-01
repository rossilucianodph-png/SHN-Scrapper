#!/usr/bin/env python3
"""
Scraper de Alturas Horarias de Marea del Servicio de Hidrografía Naval (SHN) de Argentina.
Autor: Ingeniero de Datos
Licencia: MIT (100% gratuito)
"""

import os
import sys
import json
import datetime
import argparse
import unicodedata
import requests
from bs4 import BeautifulSoup
import pandas as pd

# Configuración de Headers y User-Agent para evitar bloqueos
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": "https://www.hidro.gov.ar/oceanografia/AlturasHorarias.asp"
}

# Lista predefinida de puertos (fallback si la página principal falla en parsearse o está caída)
DEFAULT_PORTS = {
    "PTBL": "Puerto Belgrano",
    "MAGA": "Martín García",
    "SFER": "San Fernando",
    "BSAS": "Buenos Aires",
    "PNOR": "Pilote Norden",
    "LPLA": "La Plata",
    "ATAL": "Atalaya",
    "OYAR": "Oyarvide",
    "SCLE": "San Clemente",
    "MDPL": "Mar del Plata",
    "USHU": "Ushuaia"
}

def sanitize_name(text):
    """
    Normaliza el nombre del puerto eliminando acentos y caracteres especiales,
    y reemplaza los espacios por guiones bajos.
    Ejemplo: 'Martín García' -> 'Martin_Garcia'
    """
    nfkd_form = unicodedata.normalize('NFKD', text)
    only_ascii = nfkd_form.encode('ASCII', 'ignore').decode('ASCII')
    sanitized = ''.join(c if c.isalnum() else '_' for c in only_ascii)
    while '__' in sanitized:
        sanitized = sanitized.replace('__', '_')
    return sanitized.strip('_')

def get_available_ports():
    """
    Extrae dinámicamente los códigos y nombres de los puertos desde la página principal del SHN.
    Si hay algún fallo, retorna la lista predefinida como fallback.
    """
    url = "https://www.hidro.gov.ar/oceanografia/AlturasHorarias.asp"
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
    except Exception as e:
        print(f"[Advertencia] No se pudo acceder a la página de puertos ({url}): {e}.")
        print("[Información] Usando lista de puertos por defecto.")
        return DEFAULT_PORTS

    try:
        soup = BeautifulSoup(response.text, 'html.parser')
        ports = {}
        # Buscamos los elementos 'openmodal' que contienen la metadata de los puertos
        elements = soup.find_all(class_="openmodal")
        for elem in elements:
            code = elem.get("data-estacion")
            name = elem.get("data-nombre")
            if code and name:
                ports[code.strip().upper()] = name.strip()
        
        if not ports:
            raise ValueError("No se encontraron elementos con clase 'openmodal' en el HTML.")
        
        return ports
    except Exception as e:
        print(f"[Advertencia] Error al parsear los puertos en el HTML: {e}.")
        print("[Información] Usando lista de puertos por defecto.")
        return DEFAULT_PORTS

def scrape_port_data(code, name, target_date, output_dir):
    """
    Consulta la API interna del SHN para un puerto específico y una fecha dada.
    Combina las predicciones astronómicas y las lecturas medidas en un DataFrame
    y lo guarda en formato CSV.
    """
    # Formato requerido por la API: YYYYMMDDHHmm
    fecha_api = target_date.strftime("%Y%m%d%H%M")
    date_filename = target_date.strftime("%Y-%m-%d")
    
    url = f"https://www.hidro.gob.ar/api/v1/AlturasHorarias/{code}/{fecha_api}"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"[Error] Error al consultar la API para {name} ({code}): {e}")
        return False

    astronomica = data.get("astronomica", [])
    lecturas = data.get("lecturas", [])

    if not astronomica and not lecturas:
        print(f"[Advertencia] No se obtuvieron datos (vacío) para {name} ({code}).")
        return False

    # Crear DataFrames
    df_astro = pd.DataFrame(astronomica)
    df_lect = pd.DataFrame(lecturas)

    if not df_astro.empty:
        df_astro = df_astro.rename(columns={"altura": "altura_astronomica_m"})
        df_astro["fecha"] = pd.to_datetime(df_astro["fecha"])
    else:
        df_astro = pd.DataFrame(columns=["fecha", "altura_astronomica_m"])

    if not df_lect.empty:
        df_lect = df_lect.rename(columns={"altura": "altura_medida_m"})
        df_lect["fecha"] = pd.to_datetime(df_lect["fecha"])
    else:
        df_lect = pd.DataFrame(columns=["fecha", "altura_medida_m"])

    # Combinación externa (outer join) sobre el campo fecha para alinear los datos
    df_merged = pd.merge(df_astro, df_lect, on="fecha", how="outer")
    df_merged = df_merged.sort_values(by="fecha")

    # Formatear la fecha para la presentación en CSV
    df_merged["fecha"] = df_merged["fecha"].dt.strftime("%Y-%m-%dT%H:%M:%S")

    # Naming convention: [Nombre_del_Puerto]_[Tipo_de_Dato]_[YYYY-MM-DD].csv
    sanitized_port_name = sanitize_name(name)
    filename = f"{sanitized_port_name}_Mareas_{date_filename}.csv"
    filepath = os.path.join(output_dir, filename)

    try:
        os.makedirs(output_dir, exist_ok=True)
        # Guardar en UTF-8 y sin índice numérico
        df_merged.to_csv(filepath, index=False, encoding="utf-8")
        print(f"[Éxito] Datos guardados en: {filepath}")
        return True
    except Exception as e:
        print(f"[Error] No se pudo guardar el archivo {filepath}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Extrae alturas horarias del Servicio de Hidrografía Naval (SHN) de Argentina."
    )
    parser.add_argument(
        "--ports", 
        type=str, 
        default="PTBL", 
        help="Códigos de puerto a extraer separados por coma. Ejemplo: PTBL,BSAS (Por defecto: PTBL - Puerto Belgrano)"
    )
    parser.add_argument(
        "--all", 
        action="store_true", 
        help="Extrae información de todos los puertos disponibles automáticamente."
    )
    parser.add_argument(
        "--date", 
        type=str, 
        help="Fecha de consulta en formato YYYY-MM-DD. Por defecto: Fecha actual de Argentina (UTC-3)"
    )
    parser.add_argument(
        "--output-dir", 
        type=str, 
        default="data", 
        help="Carpeta de destino para guardar los archivos CSV (Por defecto: data/)"
    )

    args = parser.parse_args()

    # Configurar zona horaria de Argentina (UTC-3)
    tz_ar = datetime.timezone(datetime.timedelta(hours=-3))
    
    if args.date:
        try:
            # Parsear fecha personalizada (asumiendo mediodía para la consulta)
            base_date = datetime.datetime.strptime(args.date, "%Y-%m-%d")
            # Se consulta a la hora actual de ejecución para obtener las últimas lecturas
            now_ar = datetime.datetime.now(tz_ar)
            target_date = base_date.replace(hour=now_ar.hour, minute=now_ar.minute, tzinfo=tz_ar)
        except ValueError:
            print("[Error] Formato de fecha inválido. Utilice YYYY-MM-DD.")
            sys.exit(0)
    else:
        target_date = datetime.datetime.now(tz_ar)

    print(f"=== Iniciando Extracción SHN para la fecha: {target_date.strftime('%Y-%m-%d %H:%M:%S %Z')} ===")

    # Obtener puertos disponibles (dinámico + fallback)
    available_ports = get_available_ports()

    # Seleccionar qué puertos procesar
    ports_to_process = {}
    if args.all:
        ports_to_process = available_ports
        print(f"Modo: Todos los puertos ({len(ports_to_process)} encontrados).")
    else:
        selected_codes = [code.strip().upper() for code in args.ports.split(",")]
        for code in selected_codes:
            if code in available_ports:
                ports_to_process[code] = available_ports[code]
            else:
                print(f"[Advertencia] El código de puerto '{code}' no es reconocido. Saltando...")
        
        if not ports_to_process:
            print("[Error] No se seleccionaron puertos válidos para procesar.")
            sys.exit(0)
        print(f"Modo: Puertos específicos -> {', '.join(ports_to_process.values())}")

    # Ejecutar extracción
    success_count = 0
    for code, name in ports_to_process.items():
        success = scrape_port_data(code, name, target_date, args.output_dir)
        if success:
            success_count += 1

    print(f"\n=== Proceso Finalizado: {success_count}/{len(ports_to_process)} puertos procesados con éxito ===")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[Fallo Crítico] Ocurrió un error inesperado durante la ejecución: {e}")
        # Salida limpia tal como fue requerida
        sys.exit(0)
