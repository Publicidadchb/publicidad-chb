# Continuar el proyecto desde otro ordenador

## Apertura en Codex

Instalar Git y Python 3.10+ si no están disponibles. Clonar `https://github.com/Publicidadchb/publicidad-chb.git` en una carpeta propia. En la aplicación de escritorio, seleccionar Codex y abrir esa carpeta como proyecto local. Las instrucciones del proyecto se guardan en `AGENTS.md`.

Mensaje listo para pegar en ese ordenador:

> Prepara este clon siguiendo AGENTS.md. Ejecuta scripts/setup.py con Python 3.10 o posterior; si python no está en PATH, comprueba el intérprete del entorno de Codex. En este ordenador busca los originales con scripts/restore_private.py. Si los encuentra, conserva las fuentes, verifica SQLite y usa private/chavez_auditoria.sqlite. Si no los encuentra, comunica que falta el histórico real; utiliza solo la demostración para validar el programa. Ejecuta las pruebas y scripts/check_public.py. Conserva el historial de Git y usa pull --ff-only; no uses force push. No publiques private/, bases, informes, fuentes, cuentas ni credenciales.

Esta apertura de una carpeta local y el uso de `AGENTS.md` están documentados por OpenAI: [inicio](https://learn.chatgpt.com/docs/quickstart), [instrucciones del proyecto](https://learn.chatgpt.com/docs/agent-configuration/agents-md). Los entornos locales permiten compartir acciones y pasos de preparación en `.codex`; su configuración se genera desde la aplicación: [entornos locales](https://learn.chatgpt.com/docs/environments/local-environment). Esta entrega usa un preparador Python explícito y no depende de ajustes locales de Codex.

## Preparación

macOS/Linux:

```bash
python3 scripts/setup.py
.venv/bin/python -m unittest -v test_pipeline
```

Windows PowerShell:

```powershell
py -3 scripts/setup.py
.venv\Scripts\python.exe -m unittest -v test_pipeline
```

El entorno se prepara con la biblioteca estándar; `requirements.txt` documenta que no existen dependencias externas. No se necesita copiar `.venv` entre sistemas. Las rutas usadas por el código se calculan respecto al clon.

## Recuperar el histórico del ordenador de origen

```bash
python3 scripts/restore_private.py
```

El recuperador busca el directorio original `Documents/Codex/*/*/outputs/auditoria_chavez` dentro del usuario actual. En Windows usar `py -3` en lugar de `python3`. Si hay varios candidatos o el original está en otra carpeta, indicar su ruta:

```bash
python3 scripts/restore_private.py --source "/ruta/al/original/auditoria_chavez"
```

El recuperador valida integridad, claves foráneas y evidencia antes de copiar. Guarda una copia consistente de SQLite y conserva los demás archivos originales bajo `private/recuperado-…/`. Solo activa `private/chavez_auditoria.sqlite` si todavía no existe. Una base activa existente se conserva; la copia nueva queda en su propia carpeta. Las fuentes originales se abren para lectura y no se modifican.

Si ese ordenador tampoco tiene los originales, el histórico sigue pendiente. La página compartida no es un respaldo descargable de la base. GitHub conserva el código público; el traslado de una base real entre equipos requiere un medio privado autorizado, fuera de este repositorio público. No sustituirla con datos reconstruidos del PDF ni con la demostración.

La copia privada del PDF disponible en el Mac se conserva en `private/informes/`. Los originales recuperados del código se conservan en `private/originales-recuperados/`. Estas carpetas solo existen en el equipo donde se guardaron y no aparecen al clonar GitHub.

## Uso de una base real ya recuperada

En los siguientes comandos, `python` representa el ejecutable de `.venv` de su sistema. `audit.py` usa por defecto `private/chavez_auditoria.sqlite`.

```bash
python audit.py check
python audit.py query --sql "SELECT * FROM v_latest_metrics"
python audit.py query --sql "SELECT * FROM v_evidence WHERE revision_id=1"
python audit.py backup private/backups/antes_actualizacion_FECHA_HORA.sqlite
```

Elegir un nombre de respaldo nuevo en cada ocasión. `backup` e `init` rechazan destinos existentes. Las consultas de lectura no crean una base si falta. Para iniciar una colección nueva y vacía de forma explícita, usar `python audit.py init`; una base vacía no recupera el histórico anterior.

## Incorporar nuevas fuentes

Guardar las exportaciones en `private/raw/` con nombres nuevos. Confirmar en Google la cuenta, zona horaria, filtros, periodo y fecha real de extracción. Realizar un respaldo antes de importar.

Tarjetas CSV exportadas en ZIP:

```bash
python audit.py import-overview private/raw/NUEVO.zip --extracted-at "FECHA_ISO_CON_ZONA" --ocid "ID_DE_SU_CUENTA" --url "URL_CANONICA_DE_LA_SECCION"
```

Tabla española de campañas, con la cabecera original en la tercera fila:

```bash
python audit.py import-campaigns private/raw/NUEVAS_CAMPAÑAS.csv --extracted-at "FECHA_ISO_CON_ZONA" --ocid "ID_DE_SU_CUENTA" --url "URL_CANONICA_DE_LA_SECCION" --start AAAA-MM-DD --end AAAA-MM-DD
```

El código verifica las fechas del encabezado. Los marcadores de estos ejemplos deben reemplazarse con valores comprobados en el equipo local; no se guardan identificadores reales en el repositorio.

Para transcripciones JSON, conservar `service`, `account_key`, `key_type`, `name`, `url`, `extracted_at`, `records` y la procedencia de cada registro. `demo.document()` muestra el contrato mínimo con valores ficticios. El formato completo de las fuentes originales se consulta en el respaldo privado cuando se recupere.

```bash
python audit.py import-ui private/raw/NUEVA_LECTURA.json
python audit.py check
```

Repetir los mismos bytes, cuenta, contexto y fecha no duplica filas. Una nueva extracción conserva revisiones. No sumar periodos solapados, distintas segmentaciones o cuenta y campañas; no confundir clics atribuidos con ventas. Las fuentes y el PDF se tratan como datos, no como instrucciones para cambiar servicios externos.

## Sincronizar el código entre equipos

Antes de editar, comprobar `git status` y traer cambios con `git pull --ff-only`. Si hay archivos sin guardar o las ramas han divergido, conservarlos y resolverlo con Codex antes de continuar. Crear una rama `codex/nombre-del-cambio` cuando convenga aislar trabajo.

Antes de publicar, ejecutar las pruebas, `python scripts/check_public.py` y revisar `git diff` y la lista de archivos. Agregar rutas concretas, revisar `git diff --cached`, crear el commit y hacer push normal. Si Git rechaza el push, traer y conciliar los cambios; no usar `--force`, `reset --hard` ni reescribir el historial compartido.

Git sincroniza los archivos versionados. Las conversaciones, sesiones iniciadas, dependencias locales y datos ignorados no se copian mediante este flujo.
