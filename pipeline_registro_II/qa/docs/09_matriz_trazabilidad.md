# 09 · Matriz de Trazabilidad

> Cruce **Requisito ↔ Casos de prueba ↔ Nivel ↔ Estado**.
> Requisitos definidos en [01](01_estrategia_y_requisitos.md). Casos en [03](03_casos_transversales.md)–[08](08_modulo_MP.md).
> Estado: `Implementado` · `Parcial` (algunos casos en código) · `Documentado` (sin código) · `No cubierto`.

**Ejecución al 2026-05-26:** 68 pruebas verdes.

- **L1 unitario (12):** `ordenar_respuestas` (8) + `check_new_sub` (4).
- **L2 componente (46), todas las ramas por módulo con OdooSpy:** MC 12, CF 9, I 9,
  MP 9, R 7. Cubren: S/N no encontrado (punto inexistente / con transferencia / sin
  transferencia), ubicación (False / distinta / coincide), crear y actualizar × operativo
  Sí/No, selección por proximidad + archivado (CF/MP), primera-activa (I), y el flujo
  bifásico de R (daño y calibración Lab→593 / Bodega→594 / entrante→punto).
- **L3 integración real (10):** 4 de solo lectura + 6 E2E de escritura de punta a punta
  (MC, CF, MP, I×2, R) que verifican el **movimiento real de `x_studio_location`**.

Comandos en [README](../README.md).

Al crear/ejecutar un test, actualizar la columna **Estado** y la fecha del encabezado.

---

## 1. Requisito → Casos

| Requisito | Descripción corta | Casos que lo cubren | Nivel | Estado |
|-----------|-------------------|---------------------|-------|--------|
| **REQ-ING-1** | Procesar cada submission nueva una sola vez | TC-TR-01,02,03,05 (implementados); 04,06 pend. | L1 | Parcial |
| **REQ-PARSE-1** | Detección de puntos + parsing proyecto/punto + conteo | TC-TR-10..17 (implementados); 20..44 vía componente | L1/L2 | Parcial |
| **REQ-VAL-SN-1** | Fallback S/N → stock.move.line | MC/CF/MP: punto-inexistente, con-transferencia ('Creación en espera'), sin-transferencia ('S/N no encontrado') — etiquetas afirmadas; I/R: no-crea | L2 | Implementado |
| **REQ-VAL-LOC-1** | Validación de ubicación del equipo | L2: False/distinta/coincide en MC/CF/MP/I; E2E I sin-ubicación y cambio (movimiento real); R calibración saliente→593, entrante→punto | L2/L3 | Implementado |
| **REQ-VAL-PT-1** | Punto inexistente → inbox M | L2: MC/CF/I/MP/R (etiqueta [(4,4)], origen M afirmados) | L2 | Implementado |
| **REQ-REQSEL-1** | Selección/creación de solicitud por módulo | L2: crear + actualizar × operativo (MC); proximidad+archivado (CF/MP); primera-activa (I); bifásico daño/calibración (R) | L2 | Implementado |
| **REQ-STAGE-1** | Operativo→stage5+feedback / no→stage3+PDF | L2: crear y actualizar, operativo Sí (stage 5 + close_date) y No (stage 3 + attachment) en MC/CF/I/MP; E2E real | L2/L3 | Implementado |
| **REQ-REQSEL-1 (E2E)** | Verificado en Odoo real | E2E MC(req 292), CF(294), MP(295), R(Calibración+Extracción+Instalación) | L3 | Implementado |
| **REQ-PDF-1** | PDF correcto + nomenclatura + adjunto | L2: adjunto (ir.attachment) afirmado en rama no-operativo; E2E adjunta en Odoo real; render visual fuera de alcance | L2/L3 | Parcial |
| **REQ-INBOX-1** | Inbox: origen/etiqueta/tipo/followers | L2: etiqueta/origen afirmados por tupla (MC/CF/MP/I); followers R afirmados | L2 | Implementado |
| **REQ-ISO-1** | No tocar prod ni mutar dedup real | spy en L2 + DB temporal (TC-TR-0x) + gate + chequeo host + IDs R3 en L3 | L1/L3 | Implementado |

---

## 2. Caso → Requisito (inverso, para detectar huérfanos)

| Caso | Req(s) | Nivel | Archivo |
|------|--------|-------|---------|
| TC-TR-01..06 | REQ-ING-1, REQ-ISO-1 | L1 | [03](03_casos_transversales.md) |
| TC-TR-10..17 | REQ-PARSE-1 | L1 | [03](03_casos_transversales.md) |
| TC-TR-20..23 | REQ-PARSE-1 (incl. defecto punto≥10) | L1 | [03](03_casos_transversales.md) |
| TC-TR-30..44 | REQ-PARSE-1 | L1/L2 | [03](03_casos_transversales.md) |
| TC-TR-50..56 | REQ-VAL-SN-1, REQ-VAL-LOC-1, REQ-VAL-PT-1 | L2 | [03](03_casos_transversales.md) |
| TC-TR-60..63 | REQ-PDF-1 | L2/L3 | [03](03_casos_transversales.md) |
| TC-TR-70..76 | REQ-INBOX-1 | L2 | [03](03_casos_transversales.md) |
| TC-MC-* | REQ-REQSEL-1, REQ-STAGE-1, REQ-VAL-* , REQ-PDF-1 | L2 | [04](04_modulo_MC.md) |
| TC-CF-* | REQ-REQSEL-1, REQ-STAGE-1, REQ-VAL-* | L2 | [05](05_modulo_CF.md) |
| TC-R-* | REQ-REQSEL-1, REQ-STAGE-1, REQ-PDF-1, REQ-INBOX-1, REQ-VAL-SN-1 | L2 | [06](06_modulo_R.md) |
| TC-I-* | REQ-REQSEL-1, REQ-STAGE-1, REQ-VAL-LOC-1, REQ-PDF-1 | L2 | [07](07_modulo_I.md) |
| TC-MP-* | REQ-REQSEL-1, REQ-STAGE-1, REQ-VAL-*, REQ-INBOX-1, REQ-PDF-1 | L2 | [08](08_modulo_MP.md) |
| Smoke L3 | REQ-PDF-1, REQ-INBOX-1, REQ-ISO-1, R3 (IDs) | L3 | [scaffolding/integration](../scaffolding/integration/README.md) |

---

## 3. Cobertura de riesgos → casos

| Riesgo ([01 §2](01_estrategia_y_requisitos.md)) | Casos que lo vigilan |
|------------------------------------------------|----------------------|
| R1 errores silenciados | **todos** (oráculo positivo); en especial los negativos TC-*-N* |
| R2 escrituras reales | REQ-ISO-1 (spy en L2; gate + chequeo host en L3) |
| R3 IDs prod/test | TC-TR-74; TC-R (593/594/team2/tec5118); TC-MP-08; smoke L3 |
| R4 dedup global | TC-TR-01..06 |
| R5 parsing frágil | TC-TR-20..44 (incl. TC-TR-23 defecto conocido); TC-R-10 |
| R6 selección de solicitud | TC-CF-04/09, TC-MP-03, TC-I-04, TC-MC-05, TC-R-01/04 |
| R7 zona horaria | TC-TR-12 (+ revisar doble conversión en `detalle_op`) |

---

## 4. Defectos / observaciones conocidas levantadas por QA

Estos no son fallos de los tests sino del SUT; quedan registrados con su caso testigo.

| ID | Observación | Caso testigo | Severidad |
|----|-------------|--------------|-----------|
| OBS-1 | Punto de dos dígitos ("10") se detecta como "1" (`col[0]`) | TC-TR-23 | Media |
| OBS-2 | `check_new_sub` retorna tipos mixtos (`DataFrame`/`False`/`[]`) | TC-TR-05 | Baja |
| OBS-3 | Followers reales `[5205,172,158]` ≠ docstring `[172,147,158]` | TC-TR-76 | Baja (doc) |
| OBS-4 | Mapas de inbox difieren prod/test (tipo/etiqueta IDs) | TC-MP-08, smoke L3 | Media |
| OBS-5 | `id_tipo_de_trabajo` no incluye `'R'`; listas desfasadas | revisión estática L0 | Baja |
| OBS-6 | Posible doble conversión UTC↔Santiago (`ordenar_respuestas`→`detalle_op`) | TC-TR-12 | Media |
| OBS-7 | `filter(like="… R")` arrastra columnas `R (E)/(I)` (frágil; warning "columns are not unique") | TC-R, TC-TR-42 | Media |
| OBS-8 | El registro "sin plan de mantenimiento" (MP, L4237) se pierde si falla el feedback de actividad (`continue` en L4223); además el texto tiene typo "mantenimiennto" | TC-MP (sin-plan) | Media |
| OBS-9 | R3 verificado: a hoy los IDs hardcodeados SÍ existen en el test-Odoo staging (partners, team 2, ubicaciones 593/594). Revalidar al promover/migrar | test L3 | Info |
| OBS-10 | **CORREGIDO (2026-05-26)**: I crear-operativo-No usaba `created_request_I` (no asignado) en vez de `created_request_II` → `NameError`. Eran **dos** instancias (L3471 y L3618); ambas corregidas. El registro de éxito y el adjunto PDF ahora se generan | `test_i_crear_operativo_no` | Alta (resuelto) |

> Estas observaciones provienen de la lectura del código y de
> [processor_documentation](../../flows/processor_documentation.md). Antes de "arreglarlas",
> confirmar con negocio: algunas pueden ser comportamiento intencional.
```
