# L3 · Integración / E2E contra test-Odoo

> **Estas pruebas ESCRIBEN en Odoo de verdad.** Solo deben correr contra la instancia
> de **test** (bloque `URL_TEST` de `config.py`), nunca productivo. Ver [REQ-ISO-1](../../docs/01_estrategia_y_requisitos.md).

## Cómo correr

```bash
PY=/Users/dacm/we/.venv/bin/python
RUN_ODOO_INTEGRATION=1 $PY -m pytest qa/scaffolding -m integration -v
```

El `.env` real está en `/Users/dacm/we/.env` (tres niveles arriba); `config.py` lo
encuentra vía `load_dotenv()` al subir desde `pipeline_registro_II/`. Define
`URL_TEST/DB_TEST/USER_TEST` y la clave que `config.py` lee como `ODOO_API_KEY`.
Estado verificado al 2026-05-26: autentica contra `...dev.odoo.com` (staging) y los
IDs hardcodeados (partners 5205/172/158/5118, team 2, ubicaciones 593/594) existen.

Sin `RUN_ODOO_INTEGRATION=1`, todos los tests de esta capa se **omiten** (skip).
Además, el fixture `odoo` aborta si `config.ODOO_URL` no coincide con `os.getenv("URL_TEST")`
— una salvaguarda dura para no tocar producción aunque alguien haya cambiado `config.py`.

## E2E de escritura por flujo (`test_e2e_escritura.py`, `test_e2e_flujos.py`)

Ejecutan `process_entrys` de punta a punta y **escriben en el staging**. Un test por
tipo de trabajo; I y R verifican el **movimiento real de `x_studio_location`**:

| Test | Flujo | Verifica | OT |
|------|-------|----------|----|
| `test_e2e_mc_escribe_solicitud_e_inbox` | MC | crea inbox + maintenance.request | 990001 |
| `test_e2e_cf_crea_configuracion` | CF | crea solicitud 'Configuración' | 990010 |
| `test_e2e_mp_crea_preventiva` | MP | crea solicitud 'Mantención Preventiva' | 990011 |
| `test_e2e_i_sin_ubicacion_asocia_al_punto` | I | equipo sin ubicación → punto | 990012 |
| `test_e2e_i_cambio_de_ubicacion` | I | equipo cambia de punto | 990013 |
| `test_e2e_r_calibracion_mueve_equipos` | R | saliente→593, entrante→punto | 990014 |

**Equipos QA dedicados** (creados por la suite, reutilizados por serial; NO son equipos reales):
`QA-E2E-I` (1496), `QA-E2E-R-E` (1497), `QA-E2E-R-I` (1498), `QA-E2E-CF` (1499), `QA-E2E-MP` (1500).
Los tests resetean la ubicación-precondición de estos equipos en cada corrida (repetibles).
Las solicitudes/inbox creados NO se limpian y se acumulan al re-ejecutar (OTs 990xxx).

## Qué cubre (y qué falta calibrar)

- `test_smoke_test_odoo.py`:
  - **Autenticación** contra test-Odoo (smoke de credenciales/red).
  - **Lectura** de un modelo base (`maintenance.equipment`).
  - *(placeholder, skip)* Validación de que los IDs hardcodeados del inbox
    (`x_studio_etiqueta`, `x_studio_e_i`, `x_studio_origen`, ubicaciones `593/594`,
    team `2`, técnico `5118`) **existen** en el test-Odoo — esto es lo único que el
    spy de L2 no puede verificar (riesgo R3). Completar con los modelos/campos reales
    de las tablas de selección de Odoo Studio.

## Datos de prueba (fixtures)

Catálogo de submissions reutilizables (forma de `all_submission()`), generadas con
`form_simulator.py` y guardadas en `../../../simulated_submissions/`:

| Archivo | OT | Contenido | Sirve para |
|---------|----|-----------|-----------|
| `sim_OT-9_*.json` | 9 | submission base generada interactivamente | smoke E2E, regresión de parsing |

PDFs de referencia ya generados (golden names) en `../../../informes_pdf/`:
`informe_OT-145_Pozo_BN6_MP_I_1.pdf`, `informe_OT-203_Lora_Dren_T4_MP_{I,T}_1.pdf`,
`informe_OT-236_Pozo_P7_R_{E,I}_1.pdf`, etc. → ver TC-TR-60..62.

> **Convención sugerida para no inflar el test-Odoo:** usar números de OT con un
> prefijo reservado de QA (p.ej. `9xxxx`) y, cuando sea posible, archivar/unlink los
> registros creados al final del test. `process_entrys` no devuelve los IDs que crea,
> así que la limpieza suele hacerse por `search` del `x_name`/OT y `write(active=False)`.
