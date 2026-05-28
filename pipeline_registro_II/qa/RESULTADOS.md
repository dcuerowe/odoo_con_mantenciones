# Reporte de Resultados de Pruebas — QA Integración Connecteam → Odoo

> Generado el **2026-05-27 19:16:49** a partir de una corrida real de pytest (Python 3.14.0, pytest 9.0.3).
> Este archivo es **evidencia reproducible**: se regenera con los comandos del final.
>
> **Actualización 2026-05-28:** se agregó el test testigo `test_mc_serial_float_no_se_normaliza_obs11`
> (L2, módulo MC) que documenta **OBS-11** (búsqueda exacta del serial sin normalizar). L2 pasa de 46 a 47
> y el total a 78. La capa L1+L2 se reejecutó en verde (59 pruebas, 1.0 s); las cifras L3 son de la corrida
> del 2026-05-27 y **no** se reejecutaron (L3 escribe en staging). Ver [§ Debilidades](#debilidades-cuellos-de-botella-y-aspectos-de-observación-del-pipeline) al final.

## Resumen

- **Estado: TODAS EN VERDE**
- Total: **78** · Pasaron: **78** · Fallaron: **0** · Errores: **0** · Omitidas: **0**
- Duración total: **81.0 s** (corrida completa 2026-05-27) + **1.0 s** (readición L1+L2 del 2026-05-28)

| Nivel | Descripción                           | Pruebas | Pasaron | Fallaron | Omitidas |
| ----- | -------------------------------------- | ------: | ------: | -------: | -------: |
| L1    | Unitario (funciones puras, sin red)    |      12 |      12 |        0 |        0 |
| L2    | Componente (OdooSpy, sin red)          |      47 |      47 |        0 |        0 |
| L3    | Integración (test-Odoo real, staging) |      19 |      19 |        0 |        0 |

## Detalle por nivel y módulo

### L1 · Unitario (funciones puras, sin red)

**check_new_sub (dedup)** — 4/4 (test_check_new_sub.py)

| Prueba                             | Resultado | Tiempo (s) |
| ---------------------------------- | --------- | ---------: |
| `test_db_vacia_todo_es_nuevo`    | PASÓ     |       0.06 |
| `test_filtra_los_ya_procesados`  | PASÓ     |       0.01 |
| `test_nada_nuevo_devuelve_false` | PASÓ     |       0.00 |
| `test_tabla_ausente_se_captura`  | PASÓ     |       0.01 |

**ordenar_respuestas** — 8/8 (test_data_processing.py)

| Prueba                                       | Resultado | Tiempo (s) |
| -------------------------------------------- | --------- | ---------: |
| `test_openended_y_metadatos_base`          | PASÓ     |       0.00 |
| `test_yesno_si_no`                         | PASÓ     |       0.00 |
| `test_grupo_anidado_aplana_titulos`        | PASÓ     |       0.00 |
| `test_datetime_a_santiago`                 | PASÓ     |       0.00 |
| `test_image_devuelve_lista_urls`           | PASÓ     |       0.00 |
| `test_multiplechoice_join_coma`            | PASÓ     |       0.00 |
| `test_hidden_no_genera_columna`            | PASÓ     |       0.00 |
| `test_submission_vacia_da_dataframe_vacio` | PASÓ     |       0.01 |

### L2 · Componente (OdooSpy, sin red)

**CF — Configuración** — 9/9 (test_process_entrys_cf.py)

| Prueba                                            | Resultado | Tiempo (s) |
| ------------------------------------------------- | --------- | ---------: |
| `test_cf_sn_punto_inexistente`                  | PASÓ     |       0.01 |
| `test_cf_sn_con_transferencia`                  | PASÓ     |       0.00 |
| `test_cf_sn_sin_transferencia`                  | PASÓ     |       0.00 |
| `test_cf_equipo_sin_ubicacion`                  | PASÓ     |       0.00 |
| `test_cf_equipo_cambio_ubicacion`               | PASÓ     |       0.00 |
| `test_cf_crear_operativo_si`                    | PASÓ     |       0.00 |
| `test_cf_crear_operativo_no`                    | PASÓ     |       0.00 |
| `test_cf_usa_solicitud_en_proceso_sin_archivar` | PASÓ     |       0.00 |
| `test_cf_proximidad_archiva_anterior`           | PASÓ     |       0.01 |

**I — Instalación** — 9/9 (test_process_entrys_i.py)

| Prueba                                         | Resultado | Tiempo (s) |
| ---------------------------------------------- | --------- | ---------: |
| `test_i_punto_inexistente`                   | PASÓ     |       0.00 |
| `test_i_sn_no_encontrado_no_crea`            | PASÓ     |       0.00 |
| `test_i_ubicacion_false_escribe_punto`       | PASÓ     |       0.00 |
| `test_i_ubicacion_distinta_mueve_y_notifica` | PASÓ     |       0.00 |
| `test_i_ubicacion_coincide_no_mueve`         | PASÓ     |       0.00 |
| `test_i_crear_operativo_si`                  | PASÓ     |       0.00 |
| `test_i_crear_operativo_no`                  | PASÓ     |       0.00 |
| `test_i_actualiza_la_primera_activa`         | PASÓ     |       0.00 |
| `test_i_actualiza_operativo_no_adjunta`      | PASÓ     |       0.00 |

**MC — Correctiva** — 13/13 (test_process_entrys_mc.py)

| Prueba                                                     | Resultado | Tiempo (s) |
| ---------------------------------------------------------- | --------- | ---------: |
| `test_mc_consulta_equipo_por_serial`                     | PASÓ     |       0.00 |
| `test_mc_serial_float_no_se_normaliza_obs11`             | PASÓ     |       0.01 |
| `test_mc_sn_no_encontrado_punto_inexistente`             | PASÓ     |       0.00 |
| `test_mc_sn_no_encontrado_con_transferencia`             | PASÓ     |       0.00 |
| `test_mc_sn_no_encontrado_sin_transferencia`             | PASÓ     |       0.00 |
| `test_mc_equipo_ok_punto_inexistente`                    | PASÓ     |       0.00 |
| `test_mc_equipo_sin_ubicacion_notifica_y_continua`       | PASÓ     |       0.00 |
| `test_mc_equipo_cambio_de_ubicacion_notifica_y_continua` | PASÓ     |       0.00 |
| `test_mc_ubicacion_coincide_no_notifica`                 | PASÓ     |       0.00 |
| `test_mc_crear_operativo_si`                             | PASÓ     |       0.00 |
| `test_mc_crear_operativo_no`                             | PASÓ     |       0.00 |
| `test_mc_actualizar_operativo_si`                        | PASÓ     |       0.00 |
| `test_mc_actualizar_operativo_no`                        | PASÓ     |       0.00 |

**MP — Preventiva** — 9/9 (test_process_entrys_mp.py)

| Prueba                                             | Resultado | Tiempo (s) |
| -------------------------------------------------- | --------- | ---------: |
| `test_mp_sn_punto_inexistente`                   | PASÓ     |       0.00 |
| `test_mp_sn_con_transferencia`                   | PASÓ     |       0.00 |
| `test_mp_sn_sin_transferencia`                   | PASÓ     |       0.00 |
| `test_mp_equipo_sin_ubicacion`                   | PASÓ     |       0.00 |
| `test_mp_equipo_cambio_ubicacion`                | PASÓ     |       0.00 |
| `test_mp_crear_operativo_si_y_registra_sin_plan` | PASÓ     |       0.00 |
| `test_mp_crear_operativo_no`                     | PASÓ     |       0.00 |
| `test_mp_usa_solicitud_en_proceso`               | PASÓ     |       0.00 |
| `test_mp_proximidad_archiva_anterior`            | PASÓ     |       0.00 |

**R — Reemplazo/Extracción** — 7/7 (test_process_entrys_r.py)

| Prueba                                        | Resultado | Tiempo (s) |
| --------------------------------------------- | --------- | ---------: |
| `test_r_consulta_equipo_por_serial_e_y_i`   | PASÓ     |       0.00 |
| `test_r_sn_no_encontrado_no_crea`           | PASÓ     |       0.00 |
| `test_r_punto_inexistente`                  | PASÓ     |       0.00 |
| `test_r_dano_crea_extraccion_e_instalacion` | PASÓ     |       0.00 |
| `test_r_calibracion_lab_mueve_a_593`        | PASÓ     |       0.00 |
| `test_r_calibracion_bodega_mueve_a_594`     | PASÓ     |       0.00 |
| `test_r_followers`                          | PASÓ     |       0.00 |

### L3 · Integración (test-Odoo real, staging)

**E2E escritura — MC** — 1/1 (test_e2e_escritura.py)

| Prueba                                    | Resultado | Tiempo (s) |
| ----------------------------------------- | --------- | ---------: |
| `test_e2e_mc_escribe_solicitud_e_inbox` | PASÓ     |      11.53 |

**E2E escritura — por flujo** — 5/5 (test_e2e_flujos.py)

| Prueba                                       | Resultado | Tiempo (s) |
| -------------------------------------------- | --------- | ---------: |
| `test_e2e_cf_crea_configuracion`           | PASÓ     |       5.79 |
| `test_e2e_mp_crea_preventiva`              | PASÓ     |       4.96 |
| `test_e2e_i_sin_ubicacion_asocia_al_punto` | PASÓ     |       6.04 |
| `test_e2e_i_cambio_de_ubicacion`           | PASÓ     |       7.46 |
| `test_e2e_r_calibracion_mueve_equipos`     | PASÓ     |       8.47 |

**test_e2e_ramas** — 9/9 (test_e2e_ramas.py)

| Prueba                                         | Resultado | Tiempo (s) |
| ---------------------------------------------- | --------- | ---------: |
| `test_e2e_exc_sn_no_encontrado`              | PASÓ     |       2.76 |
| `test_e2e_exc_punto_no_existe`               | PASÓ     |       1.73 |
| `test_e2e_mc_no_operativo_crea_stage3`       | PASÓ     |       3.70 |
| `test_e2e_i_no_operativo_regresion_obs10`    | PASÓ     |       2.88 |
| `test_e2e_cf_no_operativo_crea_stage3`       | PASÓ     |       3.67 |
| `test_e2e_mc_vincula_existente`              | PASÓ     |       4.08 |
| `test_e2e_mp_proximidad_archiva_la_anterior` | PASÓ     |       5.16 |
| `test_e2e_mc_campos_del_request`             | PASÓ     |       4.27 |
| `test_e2e_r_calibracion_bodega_mueve_a_594`  | PASÓ     |       5.62 |

**Smoke (solo lectura)** — 4/4 (test_smoke_test_odoo.py)

| Prueba                                       | Resultado | Tiempo (s) |
| -------------------------------------------- | --------- | ---------: |
| `test_autenticacion`                       | PASÓ     |       0.80 |
| `test_lectura_modelo_base`                 | PASÓ     |       0.46 |
| `test_partners_load_bearing_existen`       | PASÓ     |       0.20 |
| `test_team_y_ubicaciones_metrocal_existen` | PASÓ     |       0.40 |

## Objetos creados en el test-Odoo

Durante la corrida se crearon **42** registros reales en el test-Odoo (staging), vinculados a la prueba que los originó. No se limpian.

| Modelo Odoo             | Tipo                     | Cantidad | IDs                                                                    |
| ----------------------- | ------------------------ | -------: | ---------------------------------------------------------------------- |
| `ir.attachment`       | Adjunto (PDF)            |        6 | 11147, 11148, 11152, 11153, 11154, 11155                               |
| `maintenance.request` | Solicitud de mantención |       17 | 366, 367, 368, 369, 370, 371, 372, 373, 374, 375, 376, 377, 378, 37... |
| `x_inbox_integracion` | Registro de inbox        |       19 | 770, 771, 772, 773, 774, 775, 776, 777, 778, 779, 780, 781, 782, 78... |

**Detalle por prueba:**

| Prueba                                         | Modelo                   |    ID | Referencia                     |
| ---------------------------------------------- | ------------------------ | ----: | ------------------------------ |
| `test_e2e_mc_escribe_solicitud_e_inbox`      | Solicitud de mantención |   366 | Mantenimiento Correctivo       |
| `test_e2e_mc_escribe_solicitud_e_inbox`      | Registro de inbox        |   770 | OT: 990001                     |
| `test_e2e_cf_crea_configuracion`             | Solicitud de mantención |   367 | Configuración                 |
| `test_e2e_cf_crea_configuracion`             | Registro de inbox        |   771 | OT: 990010                     |
| `test_e2e_mp_crea_preventiva`                | Solicitud de mantención |   368 | Mantenimiento Preventivo       |
| `test_e2e_mp_crea_preventiva`                | Registro de inbox        |   772 | OT: 990011                     |
| `test_e2e_i_sin_ubicacion_asocia_al_punto`   | Solicitud de mantención |   369 | Instalación                   |
| `test_e2e_i_sin_ubicacion_asocia_al_punto`   | Registro de inbox        |   773 | OT: 990012                     |
| `test_e2e_i_cambio_de_ubicacion`             | Adjunto (PDF)            | 11147 | informe_OT-990013_1_I_1.pdf    |
| `test_e2e_i_cambio_de_ubicacion`             | Registro de inbox        |   774 | OT: 990013                     |
| `test_e2e_i_cambio_de_ubicacion`             | Adjunto (PDF)            | 11148 | informe_OT-990013_1_I_1.pdf    |
| `test_e2e_i_cambio_de_ubicacion`             | Solicitud de mantención |   370 | Instalación                   |
| `test_e2e_i_cambio_de_ubicacion`             | Registro de inbox        |   775 | OT: 990013                     |
| `test_e2e_r_calibracion_mueve_equipos`       | Solicitud de mantención |   371 | Calibración                   |
| `test_e2e_r_calibracion_mueve_equipos`       | Registro de inbox        |   776 | OT: 990014                     |
| `test_e2e_r_calibracion_mueve_equipos`       | Solicitud de mantención |   372 | Extracción                    |
| `test_e2e_r_calibracion_mueve_equipos`       | Registro de inbox        |   777 | OT: 990014                     |
| `test_e2e_r_calibracion_mueve_equipos`       | Solicitud de mantención |   373 | Instalación                   |
| `test_e2e_r_calibracion_mueve_equipos`       | Registro de inbox        |   778 | OT: 990014                     |
| `test_e2e_exc_sn_no_encontrado`              | Registro de inbox        |   779 | OT: 990201                     |
| `test_e2e_exc_sn_no_encontrado`              | Adjunto (PDF)            | 11152 | informe_OT-990201_1_MC_1.pdf   |
| `test_e2e_exc_punto_no_existe`               | Registro de inbox        |   780 | OT: 990202                     |
| `test_e2e_mc_no_operativo_crea_stage3`       | Solicitud de mantención |   374 | Mantenimiento Correctivo       |
| `test_e2e_mc_no_operativo_crea_stage3`       | Registro de inbox        |   781 | OT: 990203                     |
| `test_e2e_mc_no_operativo_crea_stage3`       | Adjunto (PDF)            | 11153 | informe_OT-990203_1_MC_1.pdf   |
| `test_e2e_i_no_operativo_regresion_obs10`    | Solicitud de mantención |   375 | Instalación                   |
| `test_e2e_i_no_operativo_regresion_obs10`    | Registro de inbox        |   782 | OT: 990204                     |
| `test_e2e_i_no_operativo_regresion_obs10`    | Adjunto (PDF)            | 11154 | informe_OT-990204_1_I_1.pdf    |
| `test_e2e_cf_no_operativo_crea_stage3`       | Solicitud de mantención |   376 | Configuración                 |
| `test_e2e_cf_no_operativo_crea_stage3`       | Registro de inbox        |   783 | OT: 990205                     |
| `test_e2e_cf_no_operativo_crea_stage3`       | Adjunto (PDF)            | 11155 | informe_OT-990205_1_CF_1.pdf   |
| `test_e2e_mc_vincula_existente`              | Solicitud de mantención |   377 | QA seed Mantención Correctiva |
| `test_e2e_mc_vincula_existente`              | Registro de inbox        |   784 | OT: 990206                     |
| `test_e2e_mp_proximidad_archiva_la_anterior` | Solicitud de mantención |   378 | QA seed Mantención Preventiva |
| `test_e2e_mp_proximidad_archiva_la_anterior` | Solicitud de mantención |   379 | QA seed Mantención Preventiva |
| `test_e2e_mp_proximidad_archiva_la_anterior` | Registro de inbox        |   785 | OT: 990207                     |
| `test_e2e_mc_campos_del_request`             | Solicitud de mantención |   380 | Mantenimiento Correctivo       |
| `test_e2e_mc_campos_del_request`             | Registro de inbox        |   786 | OT: 990208                     |
| `test_e2e_r_calibracion_bodega_mueve_a_594`  | Solicitud de mantención |   381 | Extracción                    |
| `test_e2e_r_calibracion_bodega_mueve_a_594`  | Registro de inbox        |   787 | OT: 990209                     |
| `test_e2e_r_calibracion_bodega_mueve_a_594`  | Solicitud de mantención |   382 | Instalación                   |
| `test_e2e_r_calibracion_bodega_mueve_a_594`  | Registro de inbox        |   788 | OT: 990209                     |

## Notas

- **L3 escribe en el test-Odoo (staging):** los E2E ejecutan `process_entrys` de punta a punta y crean registros reales (inbox, solicitudes) y mueven equipos QA. No se limpian; se acumulan al re-ejecutar (OTs 990xxx, equipos QA 1496-1500).
- **Oráculo positivo:** cada prueba afirma un efecto observable (llamada/valor en Odoo o en el spy), no solo la ausencia de excepción.
- Defectos encontrados y su estado: ver [`docs/09_matriz_trazabilidad.md`](docs/09_matriz_trazabilidad.md) §4 (incluye OBS-10, corregido).

## Debilidades, cuellos de botella y aspectos de observación del Pipeline

> Síntesis de QA sobre el SUT (no sobre los tests). Las pruebas están en verde, pero verde
> significa "se comporta como hoy está escrito", no "está libre de riesgo". Esta sección
> consolida lo que QA observó como frágil o crítico. IDs `OBS-*` y riesgos `R*` remiten a
> [`docs/09_matriz_trazabilidad.md`](docs/09_matriz_trazabilidad.md) §3-§4 y
> [`docs/01_estrategia_y_requisitos.md`](docs/01_estrategia_y_requisitos.md) §2.
> Antes de "corregir" cualquiera, **confirmar con negocio**: algunas pueden ser intencionales.

### 1. Punto único de falla — búsqueda exacta del serial (OBS-11) · Severidad **Alta**

Cada módulo (MC/CF/R/MP/I) arranca resolviendo el equipo con una búsqueda **exacta** del serial: `search_read('maintenance.equipment', [['serial_no', '=', serial_X]])` (MC `processor.py:363`, CF `:990`, R `:1749`, etc.). Si ese `=` no calza **exacto** con lo que Odoo tiene en `serial_no`, `equipment_X` viene vacío → el flujo cae al fallback `stock.move.line` → "S/N no encontrado" → inbox, y **la solicitud de mantención nunca se crea ni se actualiza**. Es el verdadero cuello de botella del pipeline: *sin un match de serial, todo lo demás no ocurre.*

Defecto concreto verificado por QA: el bloque "asegurar que el serial pase de float a int" (`processor.py:340-342` en MC; equivalente en cada módulo) corre **después** de capturar  `serial_MC` y solo muta el `dict`, no la variable usada en la búsqueda. Por eso un serial puramente numérico que pandas infiere como `float` (p.ej. `24000.0`) se busca como float contra un campo char `"24000"` → no calza. No hay `.strip()` ni normalización de string. Los serials alfanuméricos (`24000WE0000221`) se salvan solo porque nunca entran a esa conversión.
**Testigo:** `test_mc_serial_float_no_se_normaliza_obs11`.
**Remediación propuesta:** normalizar a string limpio (`str(serial).strip()`, y si es float entero, sin el `.0`) **antes** del `search_read`, en los cinco módulos.

### 2. Errores silenciados (R1) · Severidad **Alta**

`processor.py` envuelve cada equipo/módulo en `try/except + traceback.print_exc() + continue`. Una OT puede "procesarse" sin crear nada en Odoo y **sin alerta**: el fallo solo queda en el log del runner de GitHub Actions, que nadie vigila. No hay un canal de error de negocio (inbox/correo) para fallos inesperados. Por esto **todo el oráculo de QA es positivo** (afirma efectosobservables, nunca "no hubo excepción"); pero el QA no puede sustituir una alerta en producción.

### 3. Parsing de columnas frágil (R5 / OBS-1 / OBS-7) · Severidad **Alta/Media**

- La convención `{punto}.2.{equipo} TIPO (SUB) | Campo` se rompe **en silencio** si Connecteam cambia el formulario (renombre de pregunta, nuevo sufijo, etc.).
- **OBS-1:** un punto de dos dígitos ("10") se detecta como "1" (usa `col[0]`).
- **OBS-7:** en R, `filter(like="… R")` arrastra columnas `R (E)` y `R (I)` y dispara el warning  `DataFrame columns are not unique, some columns will be omitted` (`processor.py:1714`). QA lo reprodujo en esta misma corrida (14 warnings en el módulo R). Riesgo de tomar la columna equivocada al aplanar.

### 4. Selección de la solicitud correcta (R6) · Severidad **Alta**

Cada módulo elige qué `maintenance.request` actualizar/archivar con heurísticas distintas (proximidad temporal en CF/MP, interruptor en MC, primera-activa en I, bifásico daño/calibración en R). Un cambio de datos o de supuestos puede llevar a **actualizar/archivar la solicitud equivocada**. Es lo más difícil de validar fuera de un Odoo real; L2 cubre las ramas pero el juicio de negocio sobre "cuál es la correcta" queda parcialmente fuera de alcance automatizable.

### 5. IDs hardcodeados prod/test (R3 / OBS-4 / OBS-9) · Severidad **Alta/Media**

Followers, etiquetas, tipos de inbox, ubicaciones `593/594`, `team 2`, técnico `5118` está  **incrustados en código**, y los mapas de inbox **difieren entre prod y test** (OBS-4). Al promover/migrar Odoo, estos IDs pueden apuntar a registros distintos → datos mal clasificados **sin error visible**. OBS-9: a hoy los IDs SÍ existen en staging; **revalidar en cada migración**.

### 6. Otros aspectos de observación

- **OBS-6 (zona horaria):** posible doble conversión UTC↔America/Santiago (`ordenar_respuestas`→`detalle_op`) → `close_date`/fecha desfasada un día.
- **OBS-8 (registro perdido):** el registro "sin plan de mantenimiento" (MP) se pierde si falla el feedback de actividad (`continue`); además el texto tiene typo "mantenimiennto".
- **OBS-2/3/5 (Baja):** `check_new_sub` retorna tipos mixtos (`DataFrame`/`False`/`[]`); followers reales ≠ docstring; `id_tipo_de_trabajo` no incluye `'R'`.

### 7. Cuellos de botella operacionales / de rendimiento

- **Escaneo completo de ubicaciones por equipo:** en cada módulo se hace  `search_read('x_maintenance_location', [], fields=['id','x_name'])` (lee **todas** las ubicaciones) y luego un loop en Python para encontrar el match (MC `processor.py:377-388`). Se repite por equipo y por submission → crece linealmente con el catálogo. Conviene filtrar por dominio del lado de Odoo.
- **Monolito de ~3650-4500 líneas:** toda la lógica vive en una sola función `process_entrys` con ramas anidadas; no es unit-testeable pieza por pieza sin refactor (por eso el peso recae en L2 con spy). Eleva el costo de cada cambio y el riesgo de regresión (cf. OBS-10, ya corregido).
- **Estado de dedup acoplado a git (R4):** `form_entries.db` se commitea desde CI; un fallo en el commit-back o un reset reprocesa todo. El dedup es global, no idempotente por registro.
- **Cron sin alerta:** el job corre en GitHub Actions (`0 11 * * 1-6`); si falla la corrida o la autenticación a Odoo, no hay notificación de negocio (se enlaza con R1).

### Priorización

| # | Tema                                    | OBS/R       | Severidad      | Acción                                        |
| - | --------------------------------------- | ----------- | -------------- | ---------------------------------------------- |
| 1 | Normalizar serial antes del search      | OBS-11      | **Alta** | Fix en los 5 módulos + test exige `"24000"` |
| 2 | Alerta de negocio ante error silenciado | R1          | **Alta** | Canal inbox/correo en el `except`            |
| 3 | Filtrar ubicaciones del lado de Odoo    | rendimiento | Media          | Dominio en `search_read`                     |
| 4 | Punto de dos dígitos                   | OBS-1       | Media          | Parsear prefijo numérico completo             |
| 5 | Columnas no únicas en R                | OBS-7       | Media          | Selección de columnas explícita              |
| 6 | Revalidar IDs en migración             | R3/OBS-9    | Media          | Checklist de promoción                        |

## Cómo regenerar este reporte

```bash
PY=/Users/dacm/we/.venv/bin/python
# L1+L2+L3 (incluye escritura en staging):
RUN_ODOO_INTEGRATION=1 $PY -m pytest qa/scaffolding --junitxml=/tmp/qa_run/junit.xml
$PY qa/build_report.py /tmp/qa_run/junit.xml

# Solo L1+L2 (sin tocar Odoo): omitir RUN_ODOO_INTEGRATION y agregar -m "not integration"
```
