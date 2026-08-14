#!/usr/bin/env python3
"""
Scraper de Datos Metocean (Viento, Olas y Marea) de Puerto Quequén.
Extrae la información de las últimas 24 horas de la API de puertoquequenmetocean.com,
la convierte a hora local de Argentina, y la guarda en archivos CSV diarios dentro
de subcarpetas en la carpeta 'data/Puerto_Quequen/'.
"""

import os
import sys
import argparse
import requests
import pandas as pd
from datetime import datetime, timezone

# Configuración de URLs de API de Puerto Quequén
API_ENDPOINTS = {
    "viento": "https://server.puertoquequenmetocean.com/wind?cantHours={hours}",
    "olas": "https://server.puertoquequenmetocean.com/wave?cantHours={hours}",
    "marea": "https://server.puertoquequenmetocean.com/tide?cantHours={hours}"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
}

def fetch_data(category, hours):
    """Realiza la petición HTTP GET al API de la categoría seleccionada."""
    url = API_ENDPOINTS[category].format(hours=hours)
    print(f"Descargando datos de {category} desde {url}...")
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[Error] Falló la descarga de {category}: {e}")
        return None

def process_wind(data):
    """Procesa los datos de viento y los unifica."""
    if not data:
        return pd.DataFrame()
    
    df = pd.DataFrame(data)
    if df.empty or "dateTime" not in df.columns:
        return pd.DataFrame()
    
    # Conversión de zona horaria (UTC a Argentina)
    df["fecha_dt"] = pd.to_datetime(df["dateTime"]).dt.tz_convert("America/Argentina/Buenos_Aires").dt.tz_localize(None)
    df["fecha"] = df["fecha_dt"].dt.strftime("%Y-%m-%dT%H:%M:%S")
    df["date_str"] = df["fecha_dt"].dt.strftime("%Y-%m-%d")
    
    # Renombrar y redondear
    df = df.rename(columns={"speed": "velocidad", "direction": "direccion"})
    
    # Completar columnas si faltan
    for col in ["velocidad", "direccion"]:
        if col not in df.columns:
            df[col] = None
        else:
            df[col] = pd.to_numeric(df[col], errors='coerce').round(2)
            
    return df[["fecha", "velocidad", "direccion", "date_str"]]

def process_wave(data):
    """Procesa los datos de olas (conversión de cm a metros, etc.)."""
    if not data:
        return pd.DataFrame()
    
    df = pd.DataFrame(data)
    if df.empty or "dateTime" not in df.columns:
        return pd.DataFrame()
    
    # Conversión de zona horaria (UTC a Argentina)
    df["fecha_dt"] = pd.to_datetime(df["dateTime"]).dt.tz_convert("America/Argentina/Buenos_Aires").dt.tz_localize(None)
    df["fecha"] = df["fecha_dt"].dt.strftime("%Y-%m-%dT%H:%M:%S")
    df["date_str"] = df["fecha_dt"].dt.strftime("%Y-%m-%d")
    
    # Conversión de cm a metros para alturas
    if "height" in df.columns:
        df["altura"] = (pd.to_numeric(df["height"], errors='coerce') / 100.0).round(2)
    else:
        df["altura"] = None
        
    if "maxHeight" in df.columns:
        df["altura_maxima"] = (pd.to_numeric(df["maxHeight"], errors='coerce') / 100.0).round(2)
    else:
        df["altura_maxima"] = None
        
    if "period" in df.columns:
        df["periodo"] = pd.to_numeric(df["period"], errors='coerce').round(2)
    else:
        df["periodo"] = None
        
    if "direction" in df.columns:
        df["direccion"] = pd.to_numeric(df["direction"], errors='coerce').round(2)
    else:
        df["direccion"] = None
        
    return df[["fecha", "altura", "altura_maxima", "periodo", "direccion", "date_str"]]

def process_tide(data):
    """Procesa los datos de niveles de marea."""
    if not data:
        return pd.DataFrame()
    
    df = pd.DataFrame(data)
    if df.empty or "dateTime" not in df.columns:
        return pd.DataFrame()
    
    # Conversión de zona horaria (UTC a Argentina)
    df["fecha_dt"] = pd.to_datetime(df["dateTime"]).dt.tz_convert("America/Argentina/Buenos_Aires").dt.tz_localize(None)
    df["fecha"] = df["fecha_dt"].dt.strftime("%Y-%m-%dT%H:%M:%S")
    df["date_str"] = df["fecha_dt"].dt.strftime("%Y-%m-%d")
    
    df = df.rename(columns={"value": "nivel"})
    if "nivel" not in df.columns:
        df["nivel"] = None
    else:
        df["nivel"] = pd.to_numeric(df["nivel"], errors='coerce').round(3)
        
    return df[["fecha", "nivel", "date_str"]]

def save_category_data(df, category, output_dir):
    """Agrupa los datos por fecha y los guarda de-duplicando con los CSV existentes."""
    if df.empty:
        print(f"No hay datos para guardar en la categoría {category}.")
        return
    
    grouped = df.groupby("date_str")
    
    for date_str, group in grouped:
        cat_dir = os.path.join(output_dir, category)
        os.makedirs(cat_dir, exist_ok=True)
        
        filename = f"{category}_{date_str}.csv"
        filepath = os.path.join(cat_dir, filename)
        
        # Eliminar columna auxiliar de agrupado
        clean_group = group.drop(columns=["date_str"])
        
        if os.path.exists(filepath):
            try:
                # Leer archivo existente
                existing_df = pd.read_csv(filepath)
                # Concatenar
                merged_df = pd.concat([existing_df, clean_group], ignore_index=True)
                # De-duplicar por fecha, manteniendo la última lectura recibida
                merged_df = merged_df.drop_duplicates(subset=["fecha"], keep="last")
                # Ordenar cronológicamente
                merged_df = merged_df.sort_values(by="fecha")
                # Guardar
                merged_df.to_csv(filepath, index=False, encoding="utf-8")
                print(f"   [Fusión] Archivo actualizado: {filepath} ({len(merged_df)} registros totales)")
            except Exception as e:
                print(f"   [Error] Falló la actualización de {filepath}: {e}")
        else:
            try:
                # Ordenar antes de escribir
                sorted_group = clean_group.sort_values(by="fecha")
                sorted_group.to_csv(filepath, index=False, encoding="utf-8")
                print(f"   [Nuevo] Archivo creado: {filepath} ({len(sorted_group)} registros)")
            except Exception as e:
                print(f"   [Error] No se pudo guardar el archivo {filepath}: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Scraper de Datos Metocean (Viento, Olas y Marea) de Puerto Quequén."
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Cantidad de horas a descargar (Por defecto: 24, que es el máximo histórico provisto por la API)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=os.path.join("data", "Puerto_Quequen"),
        help="Directorio base para guardar los CSV (Por defecto: data/Puerto_Quequen)"
    )
    
    args = parser.parse_args()
    
    print(f"=== Iniciando Extracción Metocean Puerto Quequén (Horas a pedir: {args.hours}) ===")
    
    # 1. Viento
    wind_raw = fetch_data("viento", args.hours)
    df_wind = process_wind(wind_raw)
    save_category_data(df_wind, "viento", args.output_dir)
    
    # 2. Olas
    wave_raw = fetch_data("olas", args.hours)
    df_wave = process_wave(wave_raw)
    save_category_data(df_wave, "olas", args.output_dir)
    
    # 3. Marea
    tide_raw = fetch_data("marea", args.hours)
    df_tide = process_tide(tide_raw)
    save_category_data(df_tide, "marea", args.output_dir)
    
    print("=== Extracción Metocean Puerto Quequén Finalizada ===")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[Fallo Crítico] Ocurrió un error inesperado durante la ejecución: {e}")
        sys.exit(0)
