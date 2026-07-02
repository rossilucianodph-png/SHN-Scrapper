#!/usr/bin/env python3
"""
Scraper de Alturas Horarias de Marea del Servicio de Hidrografía Naval (SHN) de Argentina.
Autor: Ingeniero de Datos
Licencia: MIT (100% gratuito)

Este script implementa un patrón robusto de ventana deslizante:
- Descarga los datos completos de AYER realizando dos consultas a la API (12:00 y 23:59)
  para consolidar las 24 horas del día.
- Descarga los datos parciales de HOY hasta el momento de la ejecución.
- Al día siguiente, los datos parciales de hoy se sobrescriben con los datos completos.
"""

import os
import sys
import time
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

def fetch_api_raw(code, dt):
    """
    Realiza la llamada HTTP a la API del SHN para una fecha y hora específicas.
    Retorna el JSON decodificado o None si hay error.
    """
    fecha_api = dt.strftime("%Y%m%d%H%M")
    url = f"https://www.hidro.gob.ar/api/v1/AlturasHorarias/{code}/{fecha_api}"
    time.sleep(3)
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[Error] Falló la API para {code} en {fecha_api}: {e}")
        return None

def scrape_port_data_for_date(code, name, target_date, is_complete, output_dir):
    """
    Descarga y combina los datos para una fecha específica.
    - Si is_complete es True, consulta dos puntos del día (12:00 y 23:59) para armar las 24 horas.
    - Si is_complete es False, consulta el estado parcial hasta la hora del target_date.
    """
    date_filename = target_date.strftime("%Y-%m-%d")
    print(f"-> Procesando {name} ({code}) para el día {date_filename} (Completo={is_complete})...")

    astronomica_list = []
    lecturas_list = []

    if is_complete:
        # Primera mitad: fecha a las 12:00
        dt_half1 = target_date.replace(hour=12, minute=0, second=0, microsecond=0)
        data1 = fetch_api_raw(code, dt_half1)
        if data1:
            astronomica_list.extend(data1.get("astronomica", []))
            lecturas_list.extend(data1.get("lecturas", []))

        # Segunda mitad: fecha a las 23:59
        dt_half2 = target_date.replace(hour=23, minute=59, second=0, microsecond=0)
        data2 = fetch_api_raw(code, dt_half2)
        if data2:
            astronomica_list.extend(data2.get("astronomica", []))
            lecturas_list.extend(data2.get("lecturas", []))
    else:
        # Parcial hasta la hora actual
        data = fetch_api_raw(code, target_date)
        if data:
            astronomica_list.extend(data.get("astronomica", []))
            lecturas_list.extend(data.get("lecturas", []))

    if not astronomica_list and not lecturas_list:
        print(f"   [Advertencia] Sin datos descargados para {name} el {date_filename}.")
        return False

    # Crear DataFrames y eliminar duplicados de fecha
    df_astro = pd.DataFrame(astronomica_list)
    df_lect = pd.DataFrame(lecturas_list)

    if not df_astro.empty:
        df_astro = df_astro.drop_duplicates(subset=["fecha"])
        df_astro = df_astro.rename(columns={"altura": "altura_astronomica_m"})
        df_astro["fecha"] = pd.to_datetime(df_astro["fecha"])
    else:
        df_astro = pd.DataFrame(columns=["fecha", "altura_astronomica_m"])

    if not df_lect.empty:
        df_lect = df_lect.drop_duplicates(subset=["fecha"])
        df_lect = df_lect.rename(columns={"altura": "altura_medida_m"})
        df_lect["fecha"] = pd.to_datetime(df_lect["fecha"])
    else:
        df_lect = pd.DataFrame(columns=["fecha", "altura_medida_m"])

    # Combinación externa (outer join) para alinear mediciones y predicciones
    df_merged = pd.merge(df_astro, df_lect, on="fecha", how="outer")
    df_merged = df_merged.sort_values(by="fecha")

    # Filtrar estrictamente para mantener solo los registros del día target_date
    df_merged["fecha_dt"] = pd.to_datetime(df_merged["fecha"])
    target_date_only = target_date.date()
    df_merged = df_merged[df_merged["fecha_dt"].dt.date == target_date_only]
    df_merged = df_merged.drop(columns=["fecha_dt"])

    if df_merged.empty:
        print(f"   [Advertencia] No quedaron registros para el día {date_filename} después del filtrado.")
        return False

    # Redondear valores numéricos para limpieza visual
    for col in ["altura_astronomica_m", "altura_medida_m"]:
        if col in df_merged.columns:
          df_merged[col] = pd.to_numeric(df_merged[col], errors='coerce')  
          df_merged[col] = df_merged[col].round(2)

    # Formatear la fecha para presentación en CSV
    df_merged["fecha"] = df_merged["fecha"].dt.strftime("%Y-%m-%dT%H:%M:%S")

    # Guardar a CSV
    sanitized_port_name = sanitize_name(name)
    filename = f"{sanitized_port_name}_Mareas_{date_filename}.csv"
    
    # Crear la ruta con una subcarpeta para cada puerto
    port_dir = os.path.join(output_dir, sanitized_port_name)
    filepath = os.path.join(port_dir, filename)

    try:
        os.makedirs(port_dir, exist_ok=True)
        df_merged.to_csv(filepath, index=False, encoding="utf-8")
        print(f"   [Éxito] Archivo guardado: {filepath}")
        return True
    except Exception as e:
        print(f"   [Error] No se pudo guardar el archivo {filepath}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Extrae alturas horarias completas del Servicio de Hidrografía Naval (SHN) de Argentina."
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
        help="Fecha de consulta en formato YYYY-MM-DD. Por defecto: Procesa ayer (completo) y hoy (parcial)."
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
    now_ar = datetime.datetime.now(tz_ar)

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

    # Determinar qué fechas procesar
    jobs = []  # Lista de tuplas (date, is_complete)
    
    if args.date:
        try:
            specified_date = datetime.datetime.strptime(args.date, "%Y-%m-%d").date()
            if specified_date < now_ar.date():
                # Fecha pasada: se puede descargar completa
                target_dt = datetime.datetime.combine(specified_date, datetime.time(12, 0), tzinfo=tz_ar)
                jobs.append((target_dt, True))
            elif specified_date == now_ar.date():
                # Fecha de hoy: solo se puede descargar parcial
                jobs.append((now_ar, False))
            else:
                print("[Error] La fecha especificada es del futuro. No hay datos disponibles.")
                sys.exit(0)
        except ValueError:
            print("[Error] Formato de fecha inválido. Utilice YYYY-MM-DD.")
            sys.exit(0)
    else:
        # Por defecto: AYER (completo) y HOY (parcial)
        yesterday_date = now_ar.date() - datetime.timedelta(days=1)
        yesterday_dt = datetime.datetime.combine(yesterday_date, datetime.time(12, 0), tzinfo=tz_ar)
        
        jobs.append((yesterday_dt, True))  # Ayer completo
        jobs.append((now_ar, False))       # Hoy parcial

    # Ejecutar extracción
    print(f"=== Iniciando Extracción SHN a las {now_ar.strftime('%Y-%m-%d %H:%M:%S %Z')} ===")
    
    success_count = 0
    total_jobs = len(ports_to_process) * len(jobs)
    
    for code, name in ports_to_process.items():
        for target_date, is_complete in jobs:
            success = scrape_port_data_for_date(code, name, target_date, is_complete, args.output_dir)
            if success:
                success_count += 1

    print(f"\n=== Proceso Finalizado: {success_count}/{total_jobs} reportes generados con éxito ===")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[Fallo Crítico] Ocurrió un error inesperado durante la ejecución: {e}")
        # Salida limpia tal como fue requerida
        sys.exit(0)
