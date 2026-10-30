# publicidad-chb
Auditoría marketing chb

Herramientas locales en Python y SQLite para conservar exportaciones de Google Ads y Google Business Profile, sus revisiones y su evidencia.

## Estado y continuidad — 30 de octubre de 2026

Se recuperaron el importador y el esquema a partir de los cambios del trabajo original. Se adaptaron las pruebas para usar fuentes ficticias reproducibles. El README y el commit inicial de este repositorio se conservan.

**La base original no está en este clon y recuperarla es opcional.** El usuario ha confirmado que el PDF sirve como antecedente y que la auditoría puede hacerse de nuevo con acceso a Google Ads. Su ausencia no impide continuar. Conservar el PDF y los archivos existentes; registrar las nuevas lecturas y exportaciones con su periodo, fecha y procedencia, sin presentarlas como recuperación de las fuentes antiguas.

El enlace compartido del trabajo anterior muestra el código, pero no ofrece los archivos binarios de la base ni las exportaciones originales para descargarlos. Las pruebas y la demostración verifican el funcionamiento del programa; no acreditan haber recuperado los datos históricos.

Este repositorio es público. El informe con métricas internas, las bases, sus fuentes, los respaldos y las credenciales quedan fuera de Git. La carpeta `private/` es local y no se sincroniza al clonar.

## Preparar y comprobar

Requisitos: Git y Python 3.10 o posterior con SQLite y venv. El programa y las pruebas utilizan únicamente la biblioteca estándar: no hay paquetes externos que instalar ni claves API necesarias.

```bash
git clone https://github.com/Publicidadchb/publicidad-chb.git
cd publicidad-chb
python3 scripts/setup.py
```

En Windows, sustituir la última línea por `py -3 scripts/setup.py`.

El preparador crea `.venv`, ejecuta las pruebas y comprueba una base de demostración con datos ficticios. Se detiene ante un entorno existente incompleto y conserva los archivos existentes.

Comandos en macOS/Linux:

```bash
.venv/bin/python audit.py --db private/demo/demo.sqlite check
.venv/bin/python audit.py --db private/demo/demo.sqlite query --sql "SELECT * FROM v_latest_metrics"
.venv/bin/python -m unittest -v test_pipeline
.venv/bin/python scripts/check_public.py
```

En Windows, usar `.venv\Scripts\python.exe` en lugar de `.venv/bin/python`.

## Continuar desde otro ordenador con Codex

Para continuar desde casa y la oficina, seguir [la guía de continuidad](docs/CONTINUAR_EN_CODEX.md). La base original no es un requisito. GitHub conserva el código; el acceso compartido a los documentos y datos privados debe configurarse y comprobarse aparte. La [propuesta anterior de conexión remota](docs/REUNION_CASA_OFICINA.md) se conserva como antecedente opcional.

Clonar este repositorio, abrir su carpeta como proyecto local de Codex y pedirle que siga `AGENTS.md` y [la guía de continuidad](docs/CONTINUAR_EN_CODEX.md). Esa guía contiene un mensaje listo para pegar, instrucciones de recuperación local y el flujo de sincronización sin sobrescrituras forzadas.

Si en el futuro se desea recuperar los originales, el recuperador puede localizar su directorio en el equipo de origen:

```bash
python3 scripts/restore_private.py
```

En Windows: `py -3 scripts/restore_private.py`. Recupera los originales a `private/`, valida SQLite y conserva una base activa existente. Si no hay originales en ese equipo, informa de ello y termina sin inventar un histórico.

## Archivos

| Archivo | Función |
| --- | --- |
| `audit.py`, `schema.sql` | Importación incremental, consultas de solo lectura, validación y respaldo |
| `demo.py`, `test_pipeline.py` | Datos ficticios y pruebas reproducibles |
| `scripts/setup.py` | Preparación del entorno y comprobación |
| `scripts/restore_private.py` | Recuperación local de los originales del equipo de origen |
| `PREPARAR_OFICINA.cmd`, `scripts/prepare_office.py` | Preparación en el Windows original y respaldo privado para la reunión |
| `scripts/check_public.py` | Detección de artefactos privados y patrones habituales de credenciales antes de publicar |
| `docs/CONTINUAR_EN_CODEX.md` | Apertura, recuperación, importación y sincronización |
| `docs/MIGRACION.md` | Procedencia, cambios y límites de esta entrega |

La auditoría conserva alcance parcial. El programa no accede a Google ni cambia campañas, perfiles, etiquetas, presupuestos o publicaciones.
