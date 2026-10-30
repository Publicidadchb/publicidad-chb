# Migración y validación

Fecha de preparación: 28 de octubre de 2026.

## Qué se encontró

La carpeta local del proyecto estaba vacía, con Git inicializado y sin commits. El remoto público tenía un único commit (`c73438f1a9ac93bd7bd2717bd235a8750c780a27`) con el README original. Se integró con avance directo y se conservaron las dos líneas originales del README.

El propietario facilitó un enlace al trabajo original. Sus cambios muestran `audit.py`, `schema.sql`, pruebas y documentación. Los binarios y las exportaciones se generaron en un ordenador Windows y no estaban presentes en este Mac. El enlace compartido permite leer los cambios del código, pero no proporciona enlaces de descarga de esos archivos.

## Qué se recuperó y adaptó

- Se reconstruyeron las 273 líneas finales de `audit.py` y las 28 líneas de `schema.sql`, aplicando las revisiones en su orden y verificando tanto las líneas sustituidas como el contexto.
- Se conserva una copia local anterior a las adaptaciones en `private/originales-recuperados/` y una copia del PDF adjunto en `private/informes/`. No se publican los originales que contienen información interna.
- La base por defecto pasa a `private/`; se agrega `init` explícito y se impide sustituir una base existente. Una lectura de una base ausente informa del problema sin crearla.
- La cobertura de futuras importaciones de campañas describe el archivo recibido y no repite una afirmación de paginación específica de la sesión anterior.
- Las pruebas usan exportaciones ficticias generadas en carpetas temporales. La prueba original que dependía de una exportación privada se sustituye por una importación sintética reproducible; no se afirma que el archivo privado haya sido probado en este Mac.
- Se agregan preparación portable, demostración aislada, recuperación local de originales y comprobación de archivos públicos.

## Validación reproducible

```bash
python3 scripts/setup.py
python3 scripts/check_public.py
```

Las pruebas cubren importación de ZIP y CSV, repetición sin duplicados, umbrales, revisiones y orden temporal, reversión de fallos, dinero y conversiones decimales, trazabilidad, lectura protegida, respaldo y creación sin sustitución, recuperación de originales sin modificar las fuentes y detección de datos que deben quedar fuera de Git.

La demostración comprueba SQLite con datos ficticios. La validación del histórico real sigue pendiente de disponer de su base. El generador del informe original y los scripts que incorporan observaciones comerciales específicas no se reconstruyen como herramientas públicas; el PDF original se conserva localmente.

## Recuperación opcional y límites

El 30 de octubre de 2026 el usuario confirmó que no necesita recuperar la base original: el PDF se conserva como antecedente y la auditoría puede realizarse de nuevo con acceso a Google Ads. La ausencia de los originales deja de ser un bloqueo para continuar. Las observaciones nuevas deben guardar su propia evidencia y distinguirse de las fuentes del informe anterior.

Si se desea en el futuro, se podrán recuperar `chavez_auditoria.sqlite`, las exportaciones de `raw/`, sus manifiestos y demás archivos originales. `scripts/restore_private.py` automatiza esa copia opcional cuando están disponibles en el equipo de origen. Esta entrega no publica datos privados, no conecta cuentas de Google y no configura sincronización desatendida.
