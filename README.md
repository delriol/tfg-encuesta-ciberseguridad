# Encuesta de conciencia en ciberseguridad – TFG UNPAZ

Aplicación web desarrollada como producción técnica del Trabajo Final de Grado
**"Evaluación de la conciencia en Ciberseguridad en los estudiantes de la
Universidad Nacional de José Clemente Paz"**, de la Licenciatura en Gestión de
Tecnologías de la Información (UNPAZ).

Autor: Leandro Del Rio.

La aplicación tiene dos partes:

- **Encuesta pública y anónima**, por la que los estudiantes respondieron el
  cuestionario del TFG desde el celular o la computadora.
- **Panel del investigador**, con acceso por usuario y clave, para seguir la
  recolección, descargar los datos y publicar o pausar la encuesta.

La encuesta estuvo publicada en <https://tfg-encuesta-ciberseguridad.onrender.com>
y cerró el lunes 16/11/2026 a las 23:59 (hora argentina).

## Contenido

1. [Funcionamiento](#funcionamiento)
2. [Tecnologías](#tecnologías)
3. [Estructura del proyecto](#estructura-del-proyecto)
4. [Modelo de datos](#modelo-de-datos)
5. [Cálculo de índices](#cálculo-de-índices)
6. [Seguridad y privacidad](#seguridad-y-privacidad)
7. [Cómo ejecutarlo en una computadora](#cómo-ejecutarlo-en-una-computadora)
8. [Pruebas automáticas](#pruebas-automáticas)
9. [Despliegue y operación](#despliegue-y-operación)

## Funcionamiento

### Recorrido de quien responde

1. Entra a la portada desde el enlace difundido. El enlace lleva una etiqueta
   de origen (`?origen=whatsapp` o `?origen=facebook`); sin etiqueta, la
   respuesta se cuenta como "directo".
2. Indica si tiene 18 años o más y acepta participar. Si es menor o no acepta,
   se registra solo el motivo (sin ningún otro dato) y no se continúa.
3. Completa el cuestionario, que se muestra de a una sección con una barra de
   progreso. Las preguntas obligatorias se controlan en el navegador y otra vez
   en el servidor.
4. Al enviar ve un agradecimiento. Si vuelve a entrar desde el mismo
   navegador, se le avisa que ya respondió.

### Estados de la encuesta

| Estado  | Qué significa |
|---------|---------------|
| prueba  | Todavía no se publicó. Funciona igual, pero lo que se cargue se borra al publicar. |
| abierta | Publicada y recibiendo respuestas. |
| cerrada | Pasó la fecha de cierre o se pausó desde el panel. |

### Panel del investigador (`/panel`)

- Métricas: respuestas enviadas, empezadas sin enviar, enviadas por origen,
  rechazos (no aceptó / menor de 18), mediana del tiempo de respuesta,
  enviadas por día y días de publicación.
- Descarga de dos archivos CSV:
  - **respuestas.csv**: respuestas en crudo, una fila por persona.
  - **puntajes.csv**: datos generales e índices calculados, una fila por persona.
- Publicación de la encuesta (una sola vez, borrando los datos de prueba) y
  opción de pausarla o reanudarla.
- Enlaces de difusión con la etiqueta de cada red social.

Los CSV usan punto y coma como separador, coma decimal y UTF-8 con BOM, para
abrirse directamente en Excel configurado en español.

## Tecnologías

| Capa | Tecnología |
|------|------------|
| Lenguaje | Python 3.13 |
| Framework web | Flask 3 |
| Acceso a datos | SQLAlchemy 2 (Flask-SQLAlchemy) y migraciones con Alembic (Flask-Migrate) |
| Base de datos | PostgreSQL (servicio Neon) |
| Formularios | Flask-WTF (protección CSRF) |
| Interfaz | Plantillas Jinja2, HTML, CSS, JavaScript sin dependencias y Bootstrap 5 (copia local) |
| Servidor | Gunicorn en Render |
| Pruebas | pytest, ejecutadas también en GitHub Actions |

## Estructura del proyecto

```
├── wsgi.py                  Punto de entrada (Gunicorn y comandos de Flask)
├── app/
│   ├── __init__.py          Crea la aplicación, cabeceras de seguridad y /salud
│   ├── config.py            Configuración (producción y pruebas)
│   ├── models.py            Tablas de la base
│   ├── catalogo.py          Carga del cuestionario desde el JSON y datos iniciales
│   ├── estado.py            Estado de la encuesta (prueba, abierta, cerrada)
│   ├── encuesta.py          Rutas públicas: portada, consentimiento, cuestionario
│   ├── validacion.py        Validación de las respuestas en el servidor
│   ├── panel.py             Panel del investigador
│   ├── puntajes.py          Cálculo de puntajes e índices
│   ├── exportar.py          Exportación a CSV
│   ├── cli.py               Comandos de consola (preparar-base, crear-admin)
│   ├── templates/           Páginas HTML (Jinja2)
│   └── static/              Estilos, JavaScript y Bootstrap
├── data/
│   └── cuestionario_v03.json   Preguntas, opciones y clave de corrección
├── migrations/              Migraciones de la base (Alembic)
├── tests/                   Pruebas automáticas
├── .github/workflows/       Pruebas en cada cambio y backup diario de la base
├── render.yaml              Configuración del servicio en Render
├── requirements.txt         Dependencias de la aplicación
└── requirements-dev.txt     Dependencias para las pruebas
```

Las preguntas no están escritas en el código: se definen en
`data/cuestionario_v03.json`, que reproduce el cuestionario del TFG, y se
cargan en la base con `flask --app wsgi preparar-base`.

## Modelo de datos

| Tabla | Contenido |
|-------|-----------|
| `origen` | Canales de difusión: whatsapp, facebook, directo. |
| `item` | Preguntas del cuestionario, con su tipo y clave de corrección. |
| `opcion` | Opciones de cada pregunta. |
| `respuesta` | Una participación: origen, fecha de inicio y de envío. |
| `detalle_respuesta` | Cada opción elegida (o el texto de la pregunta abierta). |
| `rechazo` | Personas que no aceptaron participar o son menores de 18 (solo motivo, origen y fecha). |
| `configuracion` | Una sola fila con las fechas de publicación y cierre y si está abierta. |
| `usuario_admin` | Usuario del panel (solo el hash de la clave). |

Una participación que se empezó y no se envió queda con la fecha de envío
vacía; se cuenta en las métricas pero no se exporta en los CSV.

## Cálculo de índices

Se implementa en `app/puntajes.py` según la clave de corrección del
cuestionario. Cada ítem se lleva a un puntaje de 0 a 1:

- **Q1** (términos conocidos): términos de seguridad marcados / 15.
- **Q2 y K1 a K10**: 1 si es correcta, 0 si es incorrecta o "No sé".
- **Escalas A (actitud) y B (comportamiento)**, de 1 a 5: `(valor − 1) / 4`;
  en los ítems invertidos se usa `6 − valor`. A6 y B4 son descriptivos y no suman.

Índices (de 0 a 100):

- **IC** (conocimiento) = promedio de Q1, Q2 y K1 a K10 × 100.
- **IA** (actitud) = promedio de A1 a A9, sin A6, × 100.
- **IB** (comportamiento) = promedio de B1 a B10, sin B4, × 100.
- **ICC** (conciencia en ciberseguridad) = 0,3·IC + 0,2·IA + 0,5·IB
  (Kruger y Kearney, 2006). Nivel: bueno ≥ 80, medio 60 a 79, bajo < 60.
- **Subescalas** Reconocer, Enfrentar y Mitigar: promedio de sus ítems × 100.

## Seguridad y privacidad

- **Anonimato**: no se guardan nombres, correos ni direcciones IP. Para evitar
  respuestas repetidas se usa un identificador al azar en una cookie del
  navegador, sin relación con la persona.
- **Consentimiento**: solo se crea el registro después de confirmar la mayoría
  de edad y aceptar participar.
- **Validación en el servidor** de todas las respuestas, y un campo oculto
  ("honeypot") que descarta envíos automáticos.
- **Formularios protegidos** contra CSRF y cookies con las marcas `Secure`,
  `HttpOnly` y `SameSite`.
- **Cabeceras HTTP de seguridad**: HSTS, Content-Security-Policy,
  X-Frame-Options, X-Content-Type-Options y Referrer-Policy.
- **Panel**: claves guardadas como hash, bloqueo de 15 minutos tras 5 intentos
  fallidos y sesión que vence a las 2 horas.
- **Secretos fuera del código**: la clave de la aplicación y la conexión a la
  base se cargan como variables de entorno.
- **Copia de seguridad diaria** de la base, cifrada con AES-256.

## Cómo ejecutarlo en una computadora

Requisitos: Python 3.13 y una base PostgreSQL (local o en Neon).

```bash
# 1. Crear y activar un entorno virtual
python -m venv .venv
source .venv/bin/activate          # En Windows: .venv\Scripts\activate

# 2. Instalar las dependencias
pip install -r requirements-dev.txt

# 3. Configurar las variables de entorno
cp .env.example .env               # y completar SECRET_KEY y DATABASE_URL

# 4. Crear las tablas y cargar el cuestionario
flask --app wsgi db upgrade
flask --app wsgi preparar-base

# 5. Crear el usuario del panel (pide la clave por teclado)
flask --app wsgi crear-admin leandro

# 6. Iniciar la aplicación
flask --app wsgi run
```

La aplicación queda en <http://127.0.0.1:5000> y el panel en
<http://127.0.0.1:5000/panel/ingresar>.

Nota: la configuración de producción marca la cookie de sesión como `Secure`,
así que el panel solo permite ingresar por HTTPS. Para probarlo sin HTTPS en la
computadora se puede usar la configuración de pruebas o un túnel HTTPS.

## Pruebas automáticas

```bash
pytest -q
```

Las pruebas usan una base SQLite en memoria, así que no necesitan PostgreSQL
ni variables de entorno. Cubren el recorrido completo de la encuesta, la
validación, el panel, la exportación CSV, el cálculo de índices (con un caso
resuelto a mano) y la carga del cuestionario. Se ejecutan automáticamente en
GitHub Actions con cada cambio.

## Despliegue y operación

- **Render** (`render.yaml`): en cada cambio de la rama `main` instala las
  dependencias, aplica las migraciones, corre `preparar-base` e inicia
  Gunicorn. Las variables `SECRET_KEY` y `DATABASE_URL` se cargan en el panel
  de Render.
- **Neon**: base PostgreSQL administrada.
- **Monitoreo**: la ruta `/salud` responde 200 solo si la base contesta; la
  consultan Render y UptimeRobot.
- **Backup diario** (`.github/workflows/backup.yml`): vuelca la base, la
  comprime y la cifra; la copia queda guardada 30 días. Necesita los secretos
  `DATABASE_URL` y `BACKUP_PASSPHRASE` en GitHub. Para restaurarla:

  ```bash
  gpg -d backup.sql.gz.gpg | gunzip | psql "<cadena de conexión>"
  ```
