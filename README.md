# Scraper de Mareas del Servicio de Hidrografía Naval (SHN) de Argentina

Este es un proyecto de ingeniería de datos 100% gratuito diseñado para extraer diariamente la información de mareas/alturas horarias del Servicio de Hidrografía Naval de Argentina (SHN) y guardarla automáticamente en el repositorio en formato CSV.

El script está desarrollado en Python y automatizado usando GitHub Actions (cron job gratuito).

---

## 📂 Estructura del Repositorio

```text
SHN/
├── .github/
│   └── workflows/
│       └── scraper.yml         # Automatización de GitHub Actions (se ejecuta diario a las 14:00 ARG / 17:00 UTC)
├── data/
│   └── .gitkeep                # Carpeta contenedora de los datos CSV
├── scraper.py                  # Script principal en Python (Web Scraping y consulta a API)
├── requirements.txt            # Librerías de Python requeridas (pandas, requests, bs4)
└── README.md                   # Esta guía de uso e instrucciones
```

---

## 🛠️ Ejecución Local

Si deseas probar el script en tu propia computadora antes de subirlo:

1. **Instala las dependencias**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Ejecuta el scraper** (por defecto descarga el puerto **Puerto Belgrano**):
   ```bash
   python scraper.py
   ```

3. **Ejecuta para un puerto diferente** (ej. Buenos Aires `BSAS`):
   ```bash
   python scraper.py --ports BSAS
   ```

4. **Ejecuta para descargar TODOS los puertos** de manera iterativa:
   ```bash
   python scraper.py --all
   ```

Los archivos se generarán en la carpeta `data/` con la nomenclatura establecida: `[Nombre_del_Puerto]_Mareas_[AAAA-MM-DD].csv`.

---

## 🚀 Instrucciones Paso a Paso para subirlo a GitHub

Sigue estos pasos sencillos para alojar y automatizar este proyecto en GitHub de forma gratuita:

### Paso 1: Crear un nuevo repositorio en GitHub
1. Abre tu cuenta de [GitHub](https://github.com).
2. Haz clic en el botón **New** (Nuevo) para crear un repositorio.
3. Asígnale un nombre (ejemplo: `shn-tide-scraper`).
4. Déjalo como **Público** (o privado, las GitHub Actions son gratuitas en ambos, pero los repositorios públicos tienen minutos de Actions ilimitados).
5. **IMPORTANTE:** No selecciones ninguna opción de inicialización (NO agregues README, ni .gitignore, ni licencia), déjalo completamente vacío.
6. Haz clic en **Create repository**.

### Paso 2: Subir el código desde tu terminal local
Abre la terminal en la carpeta de este proyecto (`c:/Users/lucia/Desktop/SHN`) y ejecuta los siguientes comandos:

```bash
# 1. Inicializar el repositorio Git local
git init

# 2. Configurar la rama principal como 'main'
git branch -M main

# 3. Vincular todos los archivos locales al área de preparación
git add .

# 4. Crear el primer commit
git commit -m "feat: Initial commit with scraper script and workflow"

# 5. Conectar tu carpeta local con el repositorio de GitHub
# (Reemplaza 'TU_USUARIO' y 'TU_REPOSITORIO' con tus datos reales)
git remote add origin https://github.com/TU_USUARIO/TU_REPOSITORIO.git

# 6. Subir el código a GitHub
git push -u origin main
```

---

### Paso 3: Configurar los permisos de GitHub Actions (CRÍTICO)
Para que el bot de GitHub pueda confirmar e inyectar los archivos CSV dentro de la carpeta `data/` del repositorio, debes otorgarle permisos de escritura:

1. En la página de tu repositorio en GitHub, ve a la pestaña ⚙️ **Settings** (Configuración) en el menú superior.
2. En la barra lateral izquierda, expande la sección **Actions** y haz clic en **General**.
3. Baja hasta la sección inferior llamada **Workflow permissions** (Permisos del flujo de trabajo).
4. Selecciona la opción **Read and write permissions** (Permisos de lectura y escritura).
5. Haz clic en el botón **Save** (Guardar).

---

### Paso 4: Probar que todo funciona (Ejecución Manual)
No tienes que esperar hasta las 14:00 (ARG) para verificar que el scraper funciona. Puedes iniciarlo manualmente ahora mismo:

1. Ve a la pestaña **Actions** en la parte superior de tu repositorio en GitHub.
2. En la columna izquierda, haz clic sobre el flujo de trabajo llamado **SHN Tide Scraper**.
3. A la derecha, verás un botón gris que dice **Run workflow** (Ejecutar flujo de trabajo). Haz clic en él.
4. Presiona el botón verde **Run workflow** que aparece en el desplegable.
5. Espera unos segundos y recarga la página. Verás que se está ejecutando la tarea.
6. Una vez completado (el círculo cambiará a un check verde `✓`), regresa a la pestaña principal **Code** del repositorio.
7. ¡Verás que se habrá creado un nuevo commit automático del bot y que dentro de la carpeta `data/` ya se encuentra el archivo CSV correspondiente al día de hoy!

---

## 📈 Modificaciones Futuras
Si en el futuro deseas que el flujo diario de GitHub Actions extraiga la información de **todos** los puertos en lugar de solo Puerto Belgrano:
1. Abre el archivo `.github/workflows/scraper.yml`.
2. Busca la línea: `python scraper.py --ports PTBL`.
3. Reemplázala por: `python scraper.py --all`.
4. Guarda y sube el cambio a GitHub.
