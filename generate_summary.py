#!/usr/bin/env python3
"""
Generador de Tabla Resumen de Niveles - Puerto Belgrano
Analiza los CSVs de mareas y genera un reporte HTML con codificación por colores.
Rojo: niveles > 3.50m entre 08:00 y 16:00
Verde: niveles <= 3.50m
"""

import os
import glob
import pandas as pd
from datetime import datetime

# Configuración
DATA_DIR = "data"
PORT_DIR = os.path.join(DATA_DIR, "Puerto_Belgrano")
OUTPUT_FILE = os.path.join(PORT_DIR, "resumen_puerto_belgrano.html")
PAGES_DIR = "docs"
PAGES_OUTPUT = os.path.join(PAGES_DIR, "index.html")
THRESHOLD = 3.50
HOUR_START = 8
HOUR_END = 16
RED_RANGE = 2.0
GREEN_RANGE = 2.5

def load_all_csvs():
    """Carga todos los CSVs de Puerto Belgrano del directorio data/Puerto_Belgrano/"""
    pattern = os.path.join(PORT_DIR, "Puerto_Belgrano_Mareas_*.csv")
    files = sorted(glob.glob(pattern))
    
    if not files:
        print(f"[Advertencia] No se encontraron archivos CSV de Puerto Belgrano en {PORT_DIR}/")
        return pd.DataFrame()
    
    all_data = []
    for f in files:
        try:
            df = pd.read_csv(f)
            if "fecha" in df.columns and "altura_medida_m" in df.columns:
                all_data.append(df)
        except Exception as e:
            print(f"[Error] No se pudo leer {f}: {e}")
    
    if not all_data:
        return pd.DataFrame()
    
    combined = pd.concat(all_data, ignore_index=True)
    combined["fecha"] = pd.to_datetime(combined["fecha"], errors="coerce")
    combined = combined.dropna(subset=["fecha"])
    combined = combined.sort_values("fecha").reset_index(drop=True)
    
    return combined

def _to_rgb(color):
    """Convierte una tupla (r,g,b) o un string hex '#rrggbb' a tupla RGB."""
    if isinstance(color, str):
        color = color.lstrip("#")
        return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))
    return color

def _interp_color(c1, c2, t):
    """Interpola entre dos colores RGB según t en [0,1]. Acepta tuplas o hex."""
    c1 = _to_rgb(c1)
    c2 = _to_rgb(c2)
    t = max(0.0, min(1.0, t))
    r = int(round(c1[0] + (c2[0] - c1[0]) * t))
    g = int(round(c1[1] + (c2[1] - c1[1]) * t))
    b = int(round(c1[2] + (c2[2] - c1[2]) * t))
    return "#{:02x}{:02x}{:02x}".format(r, g, b)

# Paletas de color
RED_LIGHT = (254, 215, 215)   # #fed7d7
RED_DARK = (155, 44, 44)      # #9b2c2c
RED_TEXT_LIGHT = (155, 44, 44)
GREEN_LIGHT = (198, 246, 213) # #c6f6d5
GREEN_DARK = (47, 133, 90)    # #2f855a
GREEN_TEXT_LIGHT = (34, 84, 61)
BADGE_GREEN = (72, 187, 120)  # #48bb78
BADGE_RED = (229, 62, 62)     # #e53e3e

def cell_colors(valor):
    """Devuelve (fondo, texto) para una celda según su valor de nivel.
    Más lejos de 3.50m = color más intenso (verde o rojo)."""
    if valor <= THRESHOLD:
        t = min((THRESHOLD - valor) / GREEN_RANGE, 1.0)
        return _interp_color(GREEN_LIGHT, GREEN_DARK, t), _interp_color(GREEN_TEXT_LIGHT, "#ffffff", t)
    t = min((valor - THRESHOLD) / RED_RANGE, 1.0)
    return _interp_color(RED_LIGHT, RED_DARK, t), _interp_color(RED_TEXT_LIGHT, "#ffffff", t)

def badge_colors(horas):
    """Devuelve (fondo, texto) del rango de alerta según cantidad de horas.
    1 hora = verde, 5 o más = rojo, valores intermedios en el medio."""
    t = min(max((horas - 1) / 4.0, 0.0), 1.0)
    return _interp_color(BADGE_GREEN, BADGE_RED, t), "#ffffff"

def filter_hours(df):
    """Filtra registros entre HOUR_START y HOUR_END"""
    df["hora"] = df["fecha"].dt.hour
    return df[(df["hora"] >= HOUR_START) & (df["hora"] <= HOUR_END)].copy()

def analyze_days(df):
    """Analiza cada día y retorna información de alertas"""
    df["fecha_str"] = df["fecha"].dt.strftime("%Y-%m-%d")
    df["hora_str"] = df["fecha"].dt.strftime("%H:00")
    df["dia_display"] = df["fecha"].dt.strftime("%d/%m/%Y")
    
    results = []
    
    for fecha_str, group in df.groupby("fecha_str"):
        day_data = {
            "fecha": fecha_str,
            "display": group["dia_display"].iloc[0],
            "hours": {},
            "alerta_inicio": None,
            "alerta_fin": None,
            "tiene_alerta": False,
            "horas_alerta": 0
        }
        
        alert_hours = []
        
        for _, row in group.iterrows():
            hora = row["hora"]
            valor = row["altura_medida_m"]
            
            if pd.isna(valor):
                day_data["hours"][hora] = {"valor": None, "alerta": False}
            else:
                is_alert = valor > THRESHOLD
                day_data["hours"][hora] = {"valor": round(valor, 2), "alerta": is_alert}
                if is_alert:
                    alert_hours.append(hora)
        
        if alert_hours:
            day_data["tiene_alerta"] = True
            day_data["horas_alerta"] = len(alert_hours)
            day_data["alerta_inicio"] = f"{min(alert_hours):02d}:00"
            day_data["alerta_fin"] = f"{max(alert_hours) + 1:02d}:00" if max(alert_hours) < 23 else "23:59"
        
        results.append(day_data)
    
    return results

def generate_html(day_results):
    """Genera el archivo HTML con la tabla resumen"""
    hours_range = list(range(HOUR_START, HOUR_END + 1))
    
    if day_results:
        fecha_min = day_results[0]["fecha"]
        fecha_max = day_results[-1]["fecha"]
    else:
        fecha_min = ""
        fecha_max = ""
    
    html = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Resumen Niveles - Puerto Belgrano</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #1a365d 0%, #2c5282 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 {
            font-size: 2rem;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }
        .header p {
            opacity: 0.9;
            font-size: 1rem;
        }
        .legend {
            display: flex;
            justify-content: center;
            gap: 30px;
            padding: 20px;
            background: #f7fafc;
            border-bottom: 1px solid #e2e8f0;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.9rem;
            color: #4a5568;
        }
        .legend-color {
            width: 20px;
            height: 20px;
            border-radius: 4px;
            border: 1px solid #cbd5e0;
        }
        .legend-color.green {
            background: #48bb78;
        }
        .legend-color.red {
            background: #f56565;
        }
        .legend-color.gradient-red {
            background: linear-gradient(90deg, #fed7d7, #9b2c2c);
        }
        .legend-color.gradient-green {
            background: linear-gradient(90deg, #c6f6d5, #2f855a);
        }
        .legend-color.gradient-hours {
            background: linear-gradient(90deg, #48bb78, #e53e3e);
        }
        .table-container {
            padding: 20px;
            overflow-x: auto;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
        }
        th {
            background: #2d3748;
            color: white;
            padding: 12px 8px;
            text-align: center;
            font-weight: 600;
            position: sticky;
            top: 0;
            z-index: 10;
        }
        th:first-child {
            text-align: left;
            min-width: 100px;
        }
        th:last-child {
            min-width: 120px;
        }
        td {
            padding: 10px 8px;
            text-align: center;
            border-bottom: 1px solid #e2e8f0;
            transition: all 0.2s ease;
        }
        td:first-child {
            text-align: left;
            font-weight: 600;
            color: #2d3748;
            background: #f7fafc;
        }
        td:last-child {
            font-size: 0.8rem;
            color: #718096;
        }
        tr:hover td {
            background: #edf2f7;
        }
        tr:hover td:first-child {
            background: #e2e8f0;
        }
        .cell {
            display: inline-block;
            padding: 6px 10px;
            border-radius: 6px;
            font-weight: 600;
            min-width: 60px;
            text-align: center;
        }
        .cell.no-data {
            background: #e2e8f0;
            color: #a0aec0;
        }
        .badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
            color: white;
        }
        .footer {
            padding: 20px;
            text-align: center;
            background: #f7fafc;
            border-top: 1px solid #e2e8f0;
            color: #718096;
            font-size: 0.85rem;
        }
        .stats {
            display: flex;
            justify-content: center;
            gap: 40px;
            padding: 20px;
            background: #ebf8ff;
            border-bottom: 1px solid #bee3f8;
        }
        .stat-item {
            text-align: center;
        }
        .stat-value {
            font-size: 1.5rem;
            font-weight: 700;
            color: #2b6cb0;
        }
        .stat-label {
            font-size: 0.8rem;
            color: #4a5568;
        }
        .filter-panel {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 30px;
            flex-wrap: wrap;
            padding: 20px;
            background: #fffaf0;
            border-bottom: 1px solid #feebc8;
        }
        .filter-toggle {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.95rem;
            color: #4a5568;
            cursor: pointer;
            font-weight: 600;
        }
        .filter-toggle input {
            width: 18px;
            height: 18px;
            cursor: pointer;
            accent-color: #2b6cb0;
        }
        .filter-dates {
            display: flex;
            gap: 15px;
            align-items: center;
        }
        .filter-field {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 0.85rem;
            color: #4a5568;
        }
        .filter-field input {
            padding: 6px 8px;
            border: 1px solid #cbd5e0;
            border-radius: 6px;
            font-size: 0.85rem;
            color: #2d3748;
            background: white;
        }
        .filter-field input:disabled {
            background: #edf2f7;
            color: #a0aec0;
            cursor: not-allowed;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Resumen de Niveles - Puerto Belgrano</h1>
            <p>Monitoreo de niveles entre 08:00 y 16:00 hs | Umbral de alerta: 3.50m</p>
        </div>
        
        <div class="legend">
            <div class="legend-item">
                <div class="legend-color green"></div>
                <span>Nivel ≤ 3.50m (Normal)</span>
            </div>
            <div class="legend-item">
                <div class="legend-color red"></div>
                <span>Nivel > 3.50m (Alerta)</span>
            </div>
            <div class="legend-item">
                <div class="legend-color gradient-green"></div>
                <span>Verde: pálido (cerca de 3.50) → oscuro (nivel bajo)</span>
            </div>
            <div class="legend-item">
                <div class="legend-color gradient-red"></div>
                <span>Rojo: pálido (cerca de 3.50) → oscuro (nivel alto)</span>
            </div>
            <div class="legend-item">
                <div class="legend-color gradient-hours"></div>
                <span>Rango alerta: verde (1 hora) → rojo (5+ horas)</span>
            </div>
        </div>
"""
    
    html += f"""
        <div class="filter-panel">
            <label class="filter-toggle">
                <input type="checkbox" id="fecha-toggle" checked>
                <span>Filtrar por rango de fechas</span>
            </label>
            <div class="filter-dates">
                <div class="filter-field">
                    <label for="fecha-inicio">Desde:</label>
                    <input type="date" id="fecha-inicio" value="{fecha_min}">
                </div>
                <div class="filter-field">
                    <label for="fecha-fin">Hasta:</label>
                    <input type="date" id="fecha-fin" value="{fecha_max}">
                </div>
            </div>
        </div>
"""
    
    total_days = len(day_results)
    alert_days = sum(1 for d in day_results if d["tiene_alerta"])
    normal_days = total_days - alert_days
    
    html += f"""
        <div class="stats">
            <div class="stat-item">
                <div class="stat-value" id="stat-total">{total_days}</div>
                <div class="stat-label">Días analizados</div>
            </div>
            <div class="stat-item">
                <div class="stat-value" id="stat-alerta" style="color: #e53e3e;">{alert_days}</div>
                <div class="stat-label">Días con alerta</div>
            </div>
            <div class="stat-item">
                <div class="stat-value" id="stat-normal" style="color: #38a169;">{normal_days}</div>
                <div class="stat-label">Días sin alerta</div>
            </div>
        </div>
"""
    
    html += """
        <div class="table-container">
            <table id="tabla-resumen">
                <thead>
                    <tr>
                        <th>Fecha</th>
"""
    
    for h in hours_range:
        html += f"                        <th>{h:02d}:00</th>\n"
    
    html += """                        <th>Rango Alerta</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    for day in day_results:
        html += f'                    <tr data-fecha="{day["fecha"]}" data-alerta="{1 if day["tiene_alerta"] else 0}">\n'
        html += f"                        <td>{day['display']}</td>\n"
        
        for h in hours_range:
            if h in day["hours"]:
                info = day["hours"][h]
                if info["valor"] is not None:
                    bg, txt = cell_colors(info["valor"])
                    html += f'                        <td><span class="cell" style="background:{bg};color:{txt};">{info["valor"]:.2f}</span></td>\n'
                else:
                    html += '                        <td><span class="cell no-data">S/D</span></td>\n'
            else:
                html += '                        <td><span class="cell no-data">-</span></td>\n'
        
        if day["tiene_alerta"]:
            bg, txt = badge_colors(day["horas_alerta"])
            html += f'                        <td><span class="badge" style="background:{bg};color:{txt};">{day["alerta_inicio"]} - {day["alerta_fin"]}</span></td>\n'
        else:
            html += '                        <td>-</td>\n'
        
        html += "                    </tr>\n"
    
    html += """
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            <p>Generado automáticamente el """ + datetime.now().strftime("%d/%m/%Y a las %H:%M") + """</p>
            <p>Datos fuente: Servicio de Hidrografía Naval (SHN) de Argentina</p>
        </div>
    </div>
    <script>
        (function() {
            const toggle = document.getElementById('fecha-toggle');
            const inicio = document.getElementById('fecha-inicio');
            const fin = document.getElementById('fecha-fin');
            const filas = document.querySelectorAll('#tabla-resumen tbody tr');
            const statTotal = document.getElementById('stat-total');
            const statAlerta = document.getElementById('stat-alerta');
            const statNormal = document.getElementById('stat-normal');

            function actualizarStats() {
                let total = 0;
                let alertas = 0;
                filas.forEach(function(fila) {
                    if (fila.style.display !== 'none') {
                        total++;
                        if (fila.dataset.alerta === '1') {
                            alertas++;
                        }
                    }
                });
                statTotal.textContent = total;
                statAlerta.textContent = alertas;
                statNormal.textContent = total - alertas;
            }

            function aplicarFiltro() {
                const activo = toggle.checked;
                inicio.disabled = !activo;
                fin.disabled = !activo;

                const desde = activo && inicio.value ? new Date(inicio.value + 'T00:00:00') : null;
                const hasta = activo && fin.value ? new Date(fin.value + 'T23:59:59') : null;

                filas.forEach(function(fila) {
                    let visible = true;
                    if (activo) {
                        const f = new Date(fila.dataset.fecha + 'T00:00:00');
                        if (desde && f < desde) visible = false;
                        if (hasta && f > hasta) visible = false;
                    }
                    fila.style.display = visible ? '' : 'none';
                });

                actualizarStats();
            }

            toggle.addEventListener('change', aplicarFiltro);
            inicio.addEventListener('change', aplicarFiltro);
            fin.addEventListener('change', aplicarFiltro);

            aplicarFiltro();
        })();
    </script>
</body>
</html>
"""
    
    return html

def main():
    print("=== Generador de Tabla Resumen Puerto Belgrano ===")
    
    os.makedirs(PORT_DIR, exist_ok=True)
    
    print("Cargando archivos CSV...")
    df = load_all_csvs()
    
    if df.empty:
        print("[Error] No hay datos disponibles para generar el resumen.")
        return
    
    print(f"Datos cargados: {len(df)} registros")
    
    print("Filtrando horario 08:00 - 16:00...")
    df_filtered = filter_hours(df)
    print(f"Registros en horario objetivo: {len(df_filtered)}")
    
    print("Analizando días...")
    day_results = analyze_days(df_filtered)
    print(f"Días analizados: {len(day_results)}")
    
    alert_days = sum(1 for d in day_results if d["tiene_alerta"])
    print(f"Días con alerta (>3.50m): {alert_days}")
    
    print("Generando HTML...")
    html_content = generate_html(day_results)
    
    for filepath in [OUTPUT_FILE, PAGES_OUTPUT]:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"[Éxito] Tabla resumen generada: {filepath}")

if __name__ == "__main__":
    main()
