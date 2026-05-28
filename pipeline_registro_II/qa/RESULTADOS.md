# Reporte de Resultados de Pruebas — QA Integración Connecteam → Odoo

> Generado el **2026-05-27 19:16:49** a partir de una corrida real de pytest (Python 3.14.0, pytest 9.0.3).
> Este archivo es **evidencia reproducible**: se regenera con los comandos del final.

## Resumen

- **Estado: TODAS EN VERDE**
- Total: **77** · Pasaron: **77** · Fallaron: **0** · Errores: **0** · Omitidas: **0**
- Duración total: **81.0 s**

| Nivel | Descripción | Pruebas | Pasaron | Fallaron | Omitidas |
|-------|-------------|--------:|--------:|---------:|---------:|
| L1 | Unitario (funciones puras, sin red) | 12 | 12 | 0 | 0 |
| L2 | Componente (OdooSpy, sin red) | 46 | 46 | 0 | 0 |
| L3 | Integración (test-Odoo real, staging) | 19 | 19 | 0 | 0 |

## Detalle por nivel y módulo

### L1 · Unitario (funciones puras, sin red)

**check_new_sub (dedup)** — 4/4 (test_check_new_sub.py)

| Prueba | Resultado | Tiempo (s) |
|--------|-----------|-----------:|
| `test_db_vacia_todo_es_nuevo` | PASÓ | 0.06 |
| `test_filtra_los_ya_procesados` | PASÓ | 0.01 |
| `test_nada_nuevo_devuelve_false` | PASÓ | 0.00 |
| `test_tabla_ausente_se_captura` | PASÓ | 0.01 |

**ordenar_respuestas** — 8/8 (test_data_processing.py)

| Prueba | Resultado | Tiempo (s) |
|--------|-----------|-----------:|
| `test_openended_y_metadatos_base` | PASÓ | 0.00 |
| `test_yesno_si_no` | PASÓ | 0.00 |
| `test_grupo_anidado_aplana_titulos` | PASÓ | 0.00 |
| `test_datetime_a_santiago` | PASÓ | 0.00 |
| `test_image_devuelve_lista_urls` | PASÓ | 0.00 |
| `test_multiplechoice_join_coma` | PASÓ | 0.00 |
| `test_hidden_no_genera_columna` | PASÓ | 0.00 |
| `test_submission_vacia_da_dataframe_vacio` | PASÓ | 0.01 |

### L2 · Componente (OdooSpy, sin red)

**CF — Configuración** — 9/9 (test_process_entrys_cf.py)

| Prueba | Resultado | Tiempo (s) |
|--------|-----------|-----------:|
| `test_cf_sn_punto_inexistente` | PASÓ | 0.01 |
| `test_cf_sn_con_transferencia` | PASÓ | 0.00 |
| `test_cf_sn_sin_transferencia` | PASÓ | 0.00 |
| `test_cf_equipo_sin_ubicacion` | PASÓ | 0.00 |
| `test_cf_equipo_cambio_ubicacion` | PASÓ | 0.00 |
| `test_cf_crear_operativo_si` | PASÓ | 0.00 |
| `test_cf_crear_operativo_no` | PASÓ | 0.00 |
| `test_cf_usa_solicitud_en_proceso_sin_archivar` | PASÓ | 0.00 |
| `test_cf_proximidad_archiva_anterior` | PASÓ | 0.01 |

**I — Instalación** — 9/9 (test_process_entrys_i.py)

| Prueba | Resultado | Tiempo (s) |
|--------|-----------|-----------:|
| `test_i_punto_inexistente` | PASÓ | 0.00 |
| `test_i_sn_no_encontrado_no_crea` | PASÓ | 0.00 |
| `test_i_ubicacion_false_escribe_punto` | PASÓ | 0.00 |
| `test_i_ubicacion_distinta_mueve_y_notifica` | PASÓ | 0.00 |
| `test_i_ubicacion_coincide_no_mueve` | PASÓ | 0.00 |
| `test_i_crear_operativo_si` | PASÓ | 0.00 |
| `test_i_crear_operativo_no` | PASÓ | 0.00 |
| `test_i_actualiza_la_primera_activa` | PASÓ | 0.00 |
| `test_i_actualiza_operativo_no_adjunta` | PASÓ | 0.00 |

**MC — Correctiva** — 12/12 (test_process_entrys_mc.py)

| Prueba | Resultado | Tiempo (s) |
|--------|-----------|-----------:|
| `test_mc_consulta_equipo_por_serial` | PASÓ | 0.00 |
| `test_mc_sn_no_encontrado_punto_inexistente` | PASÓ | 0.00 |
| `test_mc_sn_no_encontrado_con_transferencia` | PASÓ | 0.00 |
| `test_mc_sn_no_encontrado_sin_transferencia` | PASÓ | 0.00 |
| `test_mc_equipo_ok_punto_inexistente` | PASÓ | 0.00 |
| `test_mc_equipo_sin_ubicacion_notifica_y_continua` | PASÓ | 0.00 |
| `test_mc_equipo_cambio_de_ubicacion_notifica_y_continua` | PASÓ | 0.00 |
| `test_mc_ubicacion_coincide_no_notifica` | PASÓ | 0.00 |
| `test_mc_crear_operativo_si` | PASÓ | 0.00 |
| `test_mc_crear_operativo_no` | PASÓ | 0.00 |
| `test_mc_actualizar_operativo_si` | PASÓ | 0.00 |
| `test_mc_actualizar_operativo_no` | PASÓ | 0.00 |

**MP — Preventiva** — 9/9 (test_process_entrys_mp.py)

| Prueba | Resultado | Tiempo (s) |
|--------|-----------|-----------:|
| `test_mp_sn_punto_inexistente` | PASÓ | 0.00 |
| `test_mp_sn_con_transferencia` | PASÓ | 0.00 |
| `test_mp_sn_sin_transferencia` | PASÓ | 0.00 |
| `test_mp_equipo_sin_ubicacion` | PASÓ | 0.00 |
| `test_mp_equipo_cambio_ubicacion` | PASÓ | 0.00 |
| `test_mp_crear_operativo_si_y_registra_sin_plan` | PASÓ | 0.00 |
| `test_mp_crear_operativo_no` | PASÓ | 0.00 |
| `test_mp_usa_solicitud_en_proceso` | PASÓ | 0.00 |
| `test_mp_proximidad_archiva_anterior` | PASÓ | 0.00 |

**R — Reemplazo/Extracción** — 7/7 (test_process_entrys_r.py)

| Prueba | Resultado | Tiempo (s) |
|--------|-----------|-----------:|
| `test_r_consulta_equipo_por_serial_e_y_i` | PASÓ | 0.00 |
| `test_r_sn_no_encontrado_no_crea` | PASÓ | 0.00 |
| `test_r_punto_inexistente` | PASÓ | 0.00 |
| `test_r_dano_crea_extraccion_e_instalacion` | PASÓ | 0.00 |
| `test_r_calibracion_lab_mueve_a_593` | PASÓ | 0.00 |
| `test_r_calibracion_bodega_mueve_a_594` | PASÓ | 0.00 |
| `test_r_followers` | PASÓ | 0.00 |

### L3 · Integración (test-Odoo real, staging)

**E2E escritura — MC** — 1/1 (test_e2e_escritura.py)

| Prueba | Resultado | Tiempo (s) |
|--------|-----------|-----------:|
| `test_e2e_mc_escribe_solicitud_e_inbox` | PASÓ | 11.53 |

**E2E escritura — por flujo** — 5/5 (test_e2e_flujos.py)

| Prueba | Resultado | Tiempo (s) |
|--------|-----------|-----------:|
| `test_e2e_cf_crea_configuracion` | PASÓ | 5.79 |
| `test_e2e_mp_crea_preventiva` | PASÓ | 4.96 |
| `test_e2e_i_sin_ubicacion_asocia_al_punto` | PASÓ | 6.04 |
| `test_e2e_i_cambio_de_ubicacion` | PASÓ | 7.46 |
| `test_e2e_r_calibracion_mueve_equipos` | PASÓ | 8.47 |

**test_e2e_ramas** — 9/9 (test_e2e_ramas.py)

| Prueba | Resultado | Tiempo (s) |
|--------|-----------|-----------:|
| `test_e2e_exc_sn_no_encontrado` | PASÓ | 2.76 |
| `test_e2e_exc_punto_no_existe` | PASÓ | 1.73 |
| `test_e2e_mc_no_operativo_crea_stage3` | PASÓ | 3.70 |
| `test_e2e_i_no_operativo_regresion_obs10` | PASÓ | 2.88 |
| `test_e2e_cf_no_operativo_crea_stage3` | PASÓ | 3.67 |
| `test_e2e_mc_vincula_existente` | PASÓ | 4.08 |
| `test_e2e_mp_proximidad_archiva_la_anterior` | PASÓ | 5.16 |
| `test_e2e_mc_campos_del_request` | PASÓ | 4.27 |
| `test_e2e_r_calibracion_bodega_mueve_a_594` | PASÓ | 5.62 |

**Smoke (solo lectura)** — 4/4 (test_smoke_test_odoo.py)

| Prueba | Resultado | Tiempo (s) |
|--------|-----------|-----------:|
| `test_autenticacion` | PASÓ | 0.80 |
| `test_lectura_modelo_base` | PASÓ | 0.46 |
| `test_partners_load_bearing_existen` | PASÓ | 0.20 |
| `test_team_y_ubicaciones_metrocal_existen` | PASÓ | 0.40 |

## Objetos creados en el test-Odoo

Durante la corrida se crearon **42** registros reales en el test-Odoo (staging), vinculados a la prueba que los originó. No se limpian.

| Modelo Odoo | Tipo | Cantidad | IDs |
|-------------|------|---------:|-----|
| `ir.attachment` | Adjunto (PDF) | 6 | 11147, 11148, 11152, 11153, 11154, 11155 |
| `maintenance.request` | Solicitud de mantención | 17 | 366, 367, 368, 369, 370, 371, 372, 373, 374, 375, 376, 377, 378, 37... |
| `x_inbox_integracion` | Registro de inbox | 19 | 770, 771, 772, 773, 774, 775, 776, 777, 778, 779, 780, 781, 782, 78... |

**Detalle por prueba:**

| Prueba | Modelo | ID | Referencia |
|--------|--------|---:|------------|
| `test_e2e_mc_escribe_solicitud_e_inbox` | Solicitud de mantención | 366 | Mantenimiento Correctivo | Caudalímetro QA-E2E |
| `test_e2e_mc_escribe_solicitud_e_inbox` | Registro de inbox | 770 | OT: 990001 |
| `test_e2e_cf_crea_configuracion` | Solicitud de mantención | 367 | Configuración | Caudalímetro QA-E2E |
| `test_e2e_cf_crea_configuracion` | Registro de inbox | 771 | OT: 990010 |
| `test_e2e_mp_crea_preventiva` | Solicitud de mantención | 368 | Mantenimiento Preventivo | Caudalímetro QA-E2E |
| `test_e2e_mp_crea_preventiva` | Registro de inbox | 772 | OT: 990011 |
| `test_e2e_i_sin_ubicacion_asocia_al_punto` | Solicitud de mantención | 369 | Instalación | Caudalímetro QA-E2E |
| `test_e2e_i_sin_ubicacion_asocia_al_punto` | Registro de inbox | 773 | OT: 990012 |
| `test_e2e_i_cambio_de_ubicacion` | Adjunto (PDF) | 11147 | informe_OT-990013_1_I_1.pdf |
| `test_e2e_i_cambio_de_ubicacion` | Registro de inbox | 774 | OT: 990013 |
| `test_e2e_i_cambio_de_ubicacion` | Adjunto (PDF) | 11148 | informe_OT-990013_1_I_1.pdf |
| `test_e2e_i_cambio_de_ubicacion` | Solicitud de mantención | 370 | Instalación | Caudalímetro QA-E2E |
| `test_e2e_i_cambio_de_ubicacion` | Registro de inbox | 775 | OT: 990013 |
| `test_e2e_r_calibracion_mueve_equipos` | Solicitud de mantención | 371 | Calibración | Caudalímetro QA-E2E-E |
| `test_e2e_r_calibracion_mueve_equipos` | Registro de inbox | 776 | OT: 990014 |
| `test_e2e_r_calibracion_mueve_equipos` | Solicitud de mantención | 372 | Extracción | Caudalímetro QA-E2E-E |
| `test_e2e_r_calibracion_mueve_equipos` | Registro de inbox | 777 | OT: 990014 |
| `test_e2e_r_calibracion_mueve_equipos` | Solicitud de mantención | 373 | Instalación | Caudalímetro QA-E2E-I |
| `test_e2e_r_calibracion_mueve_equipos` | Registro de inbox | 778 | OT: 990014 |
| `test_e2e_exc_sn_no_encontrado` | Registro de inbox | 779 | OT: 990201 |
| `test_e2e_exc_sn_no_encontrado` | Adjunto (PDF) | 11152 | informe_OT-990201_1_MC_1.pdf |
| `test_e2e_exc_punto_no_existe` | Registro de inbox | 780 | OT: 990202 |
| `test_e2e_mc_no_operativo_crea_stage3` | Solicitud de mantención | 374 | Mantenimiento Correctivo | Caudalímetro QA |
| `test_e2e_mc_no_operativo_crea_stage3` | Registro de inbox | 781 | OT: 990203 |
| `test_e2e_mc_no_operativo_crea_stage3` | Adjunto (PDF) | 11153 | informe_OT-990203_1_MC_1.pdf |
| `test_e2e_i_no_operativo_regresion_obs10` | Solicitud de mantención | 375 | Instalación | Caudalímetro QA |
| `test_e2e_i_no_operativo_regresion_obs10` | Registro de inbox | 782 | OT: 990204 |
| `test_e2e_i_no_operativo_regresion_obs10` | Adjunto (PDF) | 11154 | informe_OT-990204_1_I_1.pdf |
| `test_e2e_cf_no_operativo_crea_stage3` | Solicitud de mantención | 376 | Configuración | Caudalímetro QA |
| `test_e2e_cf_no_operativo_crea_stage3` | Registro de inbox | 783 | OT: 990205 |
| `test_e2e_cf_no_operativo_crea_stage3` | Adjunto (PDF) | 11155 | informe_OT-990205_1_CF_1.pdf |
| `test_e2e_mc_vincula_existente` | Solicitud de mantención | 377 | QA seed Mantención Correctiva |
| `test_e2e_mc_vincula_existente` | Registro de inbox | 784 | OT: 990206 |
| `test_e2e_mp_proximidad_archiva_la_anterior` | Solicitud de mantención | 378 | QA seed Mantención Preventiva |
| `test_e2e_mp_proximidad_archiva_la_anterior` | Solicitud de mantención | 379 | QA seed Mantención Preventiva |
| `test_e2e_mp_proximidad_archiva_la_anterior` | Registro de inbox | 785 | OT: 990207 |
| `test_e2e_mc_campos_del_request` | Solicitud de mantención | 380 | Mantenimiento Correctivo | Caudalímetro QA |
| `test_e2e_mc_campos_del_request` | Registro de inbox | 786 | OT: 990208 |
| `test_e2e_r_calibracion_bodega_mueve_a_594` | Solicitud de mantención | 381 | Extracción | Caudalímetro QA-E |
| `test_e2e_r_calibracion_bodega_mueve_a_594` | Registro de inbox | 787 | OT: 990209 |
| `test_e2e_r_calibracion_bodega_mueve_a_594` | Solicitud de mantención | 382 | Instalación | Caudalímetro QA-I |
| `test_e2e_r_calibracion_bodega_mueve_a_594` | Registro de inbox | 788 | OT: 990209 |

## Notas

- **L3 escribe en el test-Odoo (staging):** los E2E ejecutan `process_entrys` de punta a punta y crean registros reales (inbox, solicitudes) y mueven equipos QA. No se limpian; se acumulan al re-ejecutar (OTs 990xxx, equipos QA 1496-1500).
- **Oráculo positivo:** cada prueba afirma un efecto observable (llamada/valor en Odoo o en el spy), no solo la ausencia de excepción.
- Defectos encontrados y su estado: ver [`docs/09_matriz_trazabilidad.md`](docs/09_matriz_trazabilidad.md) §4 (incluye OBS-10, corregido).

## Cómo regenerar este reporte

```bash
PY=/Users/dacm/we/.venv/bin/python
# L1+L2+L3 (incluye escritura en staging):
RUN_ODOO_INTEGRATION=1 $PY -m pytest qa/scaffolding --junitxml=/tmp/qa_run/junit.xml
$PY qa/build_report.py /tmp/qa_run/junit.xml

# Solo L1+L2 (sin tocar Odoo): omitir RUN_ODOO_INTEGRATION y agregar -m "not integration"
```
