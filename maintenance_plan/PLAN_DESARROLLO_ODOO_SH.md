# Plan de Desarrollo Odoo.sh — Migración Studio → Código (`we_maintenance_base` + `we_maintenance_plan`)

> **Audiencia:** agente de desarrollo trabajando dentro del repositorio conectado a **Odoo.sh** (editor web / shell del build). Este documento es la guía maestra para generar el código.
> **Versión Odoo objetivo:** 16.0 Enterprise (Odoo.sh).
> **Especificación funcional:** `maintenance_plan/PLAN_IMPLEMENTACION.md` (en adelante **[SPEC]**). Sus snippets definen la **semántica** de cada regla — NO son código a copiar: fueron escritos para el sandbox de Studio/Server Actions y acá se reescriben como código nativo de módulo.
> **Diagramas de referencia:** `er_mantenciones.drawio` (estado actual con componentes Studio) y `propuesta_plan_punto.drawio` (modelo objetivo).
> **Regla de oro:** **cero Studio**. Todo modelo, campo, vista, automatización, secuencia, cron, grupo y ACL vive en los módulos del repo.

---

## 0. Resumen ejecutivo

Hoy el sistema corre sobre componentes creados con Odoo Studio en producción:

| Componente Studio actual | Estado | Destino en código |
| --- | --- | --- |
| Modelo `x_maintenance_location` (puntos de monitoreo, **con datos**, incl. IDs 593/594) | existe | → **`maintenance.location`** (módulo `we_maintenance_base`) con campos sin prefijo, **preservando IDs** |
| Campo `maintenance.equipment.x_studio_location` (m2o, **con datos**) | existe | → **`location`** (m2o → `maintenance.location`) — redefine el `location` char nativo (ver §2.2) |
| Campo `maintenance.equipment.x_studio_registros_de_bitcora` (o2m) | existe | → **`logbook`** (o2m → `maintenance.request`) |
| Campo `maintenance.request.x_studio_tipo_de_trabajo` (**con datos**) | existe | → **`work_type`** |
| Modelo `x_maintenance_plan` + toda su lógica (SA/AA/crons Studio) | existe, **sin datos** | → **`maintenance.plan`** (módulo `we_maintenance_plan`), se crea limpio, **sin ETL** |
| Modelo `x_equipment_movement` (**con datos**) | existe | → **`maintenance.equipment.movement`** con **ETL de datos** |
| Server Actions SA-00…SA-19, Automated Actions AA-*, crons CR-01…03, secuencias | existen | → métodos Python, `@api.constrains`, overrides de `create()`/`write()`, `ir.cron` y `ir.sequence` en data XML. Los artefactos Studio se **desactivan en el cutover** |

Decisiones cerradas por el equipo:

- **2 módulos**: `we_maintenance_base` (renombres/absorción de la base) y `we_maintenance_plan` (todo lo nuevo).
- **Nombres limpios en todo** (sin `x_` ni `x_studio_`).
- **Sin campos `company_id`** en los modelos nuevos ni record rules multi-company (instancia mono-compañía).
- **La vista Gantt del plan usa `scheduled_date`** como fecha de la barra: los computes `gantt_start`/`gantt_stop` del [SPEC] §3.8 **se eliminan del diseño**.
- Los IDs de `maintenance.location` **se preservan** en la migración (593 = Laboratorio | Metrocal, 594 = Bodega cliente, hardcodeados en `pipeline_registro_II/processor.py`).

> ⚠️ **Impacto externo:** los renombres rompen `pipeline_registro_II` (XML-RPC): `processor.py` referencia `x_maintenance_location` (10 refs), `x_studio_location` (19 refs) y `x_studio_tipo_de_trabajo` (31 refs), además de los tests de `qa/scaffolding/`. El go-live a producción (Fase F4, §6) debe ser **simultáneo** con el deploy del pipeline actualizado (§7).

---

## 1. Principios de traducción Studio → código

1. **[SPEC] es la fuente funcional.** Cada método nuevo debe referenciar en su docstring el identificador de origen (`SA-02`, `C-04`, `Req 5`, …) para trazabilidad.
2. **Las limitaciones del sandbox desaparecen.** En código nativo:
   - `record.campo = valor` es válido (el `STORE_ATTR` prohibido era del sandbox).
   - Las validaciones son `@api.constrains` reales con `ValidationError` (ya no SA + AA "On Creation & Update" + `UserError`).
   - Los "watched fields" se resuelven en el override de `write()` comparando `vals` y valores previos — desaparecen los guards anti-spam de AA-03/AA-06/AA-14/AA-18 diseñados porque el `On Update` de 16 dispara en cada write.
   - `write()` **ve el valor previo** del registro: SA-09 ya no necesita reconstruir la ubicación anterior desde el último movement (§3.4).
   - `uuid` es importable, aunque se mantiene la decisión del [SPEC] de usar `ir.sequence` para `series_id` (legible y ordenable).
   - Los `f-string`/formatos se reemplazan por `_()` con interpolación para traducibilidad donde el texto llegue al usuario.
3. **Transposición de nombres** — aplicar en TODOS los snippets/dominios del [SPEC]:

   | En [SPEC] (Studio) | En código |
   | --- | --- |
   | `x_maintenance_location` | `maintenance.location` |
   | `x_name` / `x_active` / `x_studio_sequence` | `name` / `active` / `sequence` |
   | `x_contract_start_date` / `x_contract_end_date` | `contract_start_date` / `contract_end_date` |
   | `x_frequency_value` / `x_frequency_unit` / `x_slack_days` | `frequency_value` / `frequency_unit` / `slack_days` |
   | `maintenance.equipment.x_studio_location` | `location` (m2o) |
   | `maintenance.equipment.x_studio_registros_de_bitcora` | `logbook` |
   | `maintenance.request.x_studio_tipo_de_trabajo` | `work_type` |
   | `x_maintenance_plan` / `x_studio_state` / `x_studio_plan_id` / `x_studio_<campo>` | `maintenance.plan` / `state` / `plan_id` / `<campo>` |
   | `x_equipment_movement` | `maintenance.equipment.movement` |
   | contexto `x_skip_c04` / `skip_auto_movement` | `skip_overlap_check` / `skip_auto_movement` |
4. **Lo que NO se migra:** el resto de campos Studio de `maintenance.equipment` (`x_studio_cliente`, contract_* del equipo, etc.) y de `maintenance.request` (`x_studio_tcnico`, `x_studio_inicio_actividad`, …) **quedan como están** (Studio) en esta fase. No tocarlos ni referenciarlos desde los módulos nuevos.
5. **Sin `company_id`:** omitir toda columna/regla/default de compañía descrita en el [SPEC] (§3.1, §3.bis.1, §10.3).

---

## 2. Módulo `we_maintenance_base`

### 2.0 Estructura

```
we_maintenance_base/
├── __init__.py
├── __manifest__.py            # depends: ['maintenance', 'mail']
├── models/
│   ├── __init__.py
│   ├── maintenance_location.py
│   ├── maintenance_equipment.py
│   └── maintenance_request.py
├── views/
│   ├── maintenance_location_views.xml     # form/list + menú
│   ├── maintenance_equipment_views.xml    # reemplazo de x_studio_location por location
│   └── maintenance_request_views.xml      # work_type
├── security/
│   └── ir.model.access.csv                # ACL de maintenance.location (Maintenance User/Manager)
└── migrations/                            # ver §5.1 (scripts de la Fase F1)
```

### 2.1 `maintenance.location` (nuevo modelo en código)

`_name = 'maintenance.location'` · `_description = 'Punto de Monitoreo'` · `_inherit = ['mail.thread', 'mail.activity.mixin']` · `_order = 'sequence, id'`

| Campo | Tipo | Origen Studio | Notas |
| --- | --- | --- | --- |
| `name` | Char, required | `x_name` | rec_name |
| `active` | Boolean, default True | `x_active` | archiving |
| `sequence` | Integer, default 10 | `x_studio_sequence` | orden manual |
| `asset_id` | Char | `x_studio_asset_id_1` | Asset ID |
| `coordinates` | Char | `x_studio_char_field_M8G1K` | Coordenadas |
| `location_desc` | Char | `x_studio_ubicacin` | Ubicación (texto) |
| `location_desc_alt` | Char | `x_studio_ubicacin_1` | Ubicación (alt) |
| `contract_start_date` | Date, tracking | `x_contract_start_date` | informativo |
| `contract_end_date` | Date, tracking | `x_contract_end_date` | **límite duro de la cascada** ([SPEC] §3.10) |
| `frequency_value` | Integer, required, default 1, tracking | `x_frequency_value` | cadencia del punto — fuente única ([SPEC] §3.3) |
| `frequency_unit` | Selection `day/week/month/year`, required, default `month`, tracking | `x_frequency_unit` | — |
| `slack_days` | Integer, default 3, tracking | `x_slack_days` | tolerancia ± |
| `equipment_ids` | One2many → `maintenance.equipment`, inverse `location` | `x_studio_equiposinstrumentos` | — |

Constraints nativos (reemplazan SA-C01/SA-C02 + AA-07/AA-08 del [SPEC] §7):

- **C-01** `@api.constrains('frequency_value')` → `frequency_value > 0`, si no `ValidationError`.
- **C-02** `@api.constrains('frequency_value', 'frequency_unit', 'slack_days')` → `slack_days * 2 < período_base` (UNIT_DAYS = day 1 / week 7 / month 30 / year 365).

> Los inversos `plan_ids`, `movement_out_ids`, `movement_in_ids` NO van acá: los agrega `we_maintenance_plan` vía `_inherit` (§3.3), para que la base no dependa del módulo de planes.

### 2.2 `maintenance.equipment` (_inherit)

| Campo | Tipo | Notas |
| --- | --- | --- |
| `location` | **Many2one → `maintenance.location`**, index, tracking | ⚠️ **Redefine el campo nativo** `location = fields.Char()` del core de `maintenance`. Odoo permite redefinir tipo vía `_inherit`, pero la columna char existente choca con la FK nueva: la migración `pre-migrate` debe renombrar la columna vieja **antes** de que el ORM cree la nueva (ver §5.1 paso 1). El valor char nativo casi no se usa (el dato real vivía en `x_studio_location`), pero se conserva en `location_legacy` por auditoría. |
| `location_legacy` | Char, readonly | Contenedor del valor del `location` char nativo pre-migración. Ocultarlo en vistas (solo Settings). |
| `logbook` | One2many → `maintenance.request`, inverse `equipment_id` | Reemplaza al o2m Studio `x_studio_registros_de_bitcora`. Mismo inverse que el `maintenance_ids` nativo — es una vista de bitácora separada en el form (tab "Bitácora"). |

### 2.3 `maintenance.request` (_inherit)

| Campo | Tipo | Notas |
| --- | --- | --- |
| `work_type` | Selection | Reemplaza `x_studio_tipo_de_trabajo`. **Antes de codificarlo, introspectar el campo Studio real** (selection vs char y sus valores — `er_introspection.json` lo lista como selection). Debe admitir al menos los literales que escribe el pipeline y las SAs: `Mantención Preventiva`, `Mantención del Equipo`, `Extracción`, `Calibración`, `Instalación`. Conservar las **keys existentes tal cual** para que la migración de datos sea copia directa y el pipeline solo cambie el nombre del campo, no los valores. |

### 2.4 Vistas del módulo base

- `maintenance.location`: form (tabs "Contrato" con contract_* + cadencia/slack, según [SPEC] §3.bis.6) + list + menú bajo Mantenimiento → Configuración. Replicar la estructura que hoy existe en Studio.
- Herencia del form de `maintenance.equipment`: mostrar `location` (m2o) donde hoy está `x_studio_location`; tab "Bitácora" con `logbook`.
- Herencia del form de `maintenance.request`: `work_type` visible en el bloque principal.

---

## 3. Módulo `we_maintenance_plan`

### 3.0 Estructura

```
we_maintenance_plan/
├── __init__.py
├── __manifest__.py            # depends: ['we_maintenance_base', 'maintenance', 'resource', 'mail']
├── models/
│   ├── __init__.py
│   ├── maintenance_plan.py            # maintenance.plan
│   ├── equipment_movement.py          # maintenance.equipment.movement
│   ├── maintenance_location.py        # _inherit: inversos + write() (SA-12/SA-19)
│   ├── maintenance_equipment.py       # _inherit: managed_by_plan, movement_ids, write() (SA-09)
│   └── maintenance_request.py         # _inherit: plan_id, create()/write() (SA-10/SA-17)
├── wizard/
│   ├── __init__.py
│   ├── plan_cancel_wizard.py          # confirmación SA-04
│   └── plan_force_close_wizard.py     # cierre partially_done + force_close_reason
├── data/
│   ├── ir_sequence_data.xml           # 3 secuencias (§3.6)
│   ├── ir_cron_data.xml               # 4 crons (§3.5)
│   └── mail_template_data.xml         # QWeb reporte semanal / mensual / alerta
├── views/
│   ├── maintenance_plan_views.xml     # form/list/kanban/calendar/gantt + actions + menú
│   ├── equipment_movement_views.xml
│   ├── maintenance_equipment_views.xml
│   ├── maintenance_request_views.xml
│   └── maintenance_location_views.xml # tab "Planes" + "Historial de equipos"
├── security/
│   ├── maintenance_plan_groups.xml    # Plan Manager / Plan User
│   └── ir.model.access.csv
├── report/                            # (opcional) helpers de render de los mails
├── tests/
│   ├── __init__.py
│   ├── common.py                      # setUp: punto + 3 equipos (checklist [SPEC] §11)
│   ├── test_plan_lifecycle.py         # T-01…T-17, T-30…T-36
│   ├── test_equipment_movement.py     # T-18…T-25c
│   ├── test_business_rules.py         # T-40…T-52 (Req 1–8)
│   └── test_location_cadence.py       # T-53…T-58
└── migrations/                        # ETL movements + cutover (§5.2)
```

### 3.1 Modelo `maintenance.plan`

`_name = 'maintenance.plan'` · `_description = 'Plan de Mantención Preventiva por Punto'` · `_inherit = ['mail.thread', 'mail.activity.mixin']` · `_order = 'scheduled_date desc, id desc'`

Campos ([SPEC] §3 completo, transpuesto; **sin** `company_id`, **sin** `gantt_start/gantt_stop`):

| Grupo | Campo | Tipo | Notas |
| --- | --- | --- | --- |
| Identificación | `name` | Char, required, readonly, default `'New'` | `create()` lo setea `PMP-{seq:04d}` (secuencia **sin prefijo** — evita `PMP-PMP-`, [SPEC] SA-00). En código el "required + autollenado post-insert" del [SPEC] deja de ser problema: se resuelve **dentro** de `create()`. |
| | `location_id` | Many2one → `maintenance.location`, required, index, `ondelete='restrict'` | no borrar un punto con planes |
| Programación | `scheduled_date` | Date, required, tracking | — |
| | `original_scheduled_date` | Date, readonly | snapshot en `create()` |
| | `close_date` | Date, readonly | seteado por la cascada |
| | `state` | Selection, required, default `draft`, tracking | `draft · scheduled · in_progress · done · partially_done · out_of_range · cancelled` ([SPEC] §3.2) |
| Cadencia (related del punto) | `frequency_value` | Integer, related `location_id.frequency_value`, store=True, index | readonly en form ([SPEC] §3.3) |
| | `frequency_unit` | Selection, related, store=True | — |
| | `slack_days` | Integer, related, store=True | — |
| | `auto_replan` | Boolean, default True | **propio del plan**, no related |
| Serie | `series_id` | Char, index, readonly | secuencia `maintenance.plan.series` en `create()` |
| | `previous_plan_id` / `next_plan_id` | Many2one → self, `ondelete='set null'` | — |
| | `seq_in_series` | Integer, default 1 | — |
| Responsables | `user_id` | Many2one → res.users, tracking, default usuario actual | responsable |
| | `technician_user_id` | Many2one → res.users | — |
| | `maintenance_team_id` | Many2one → maintenance.team | — |
| | `maintenance_type` | Selection `preventive/corrective`, default `preventive` | — |
| Calendario | `resource_calendar_id` | Many2one → resource.calendar, default = calendario de la compañía | [SPEC] §3.6 |
| Snapshot | `equipment_snapshot_ids` | Many2many → maintenance.equipment | congelado al pasar a `scheduled` |
| | `last_sync_with_location` | Datetime, readonly | — |
| Contrato (related) | `contract_start_date` / `contract_end_date` | Date, related de `location_id`, store=True, index | límite duro de la cascada ([SPEC] §3.10) |
| Calculados | `progress` | Integer, compute stored, `@api.depends('request_ids.stage_id.done', 'request_ids.archive')` | % hijas done excluyendo archivadas ([SPEC] §3.8) |
| | `delta_days_from_planned` | Integer, compute | `close_date − scheduled_date` |
| | `adjusted_from_scheduled` | Boolean, compute | `original != scheduled` |
| | `is_approaching` | Boolean, compute **no stored** | `state in (draft, scheduled)` y `0 ≤ scheduled_date − hoy ≤ 7` |
| Operativos | `force_close_reason` | Text | requerido al cerrar `partially_done` (C-03) |
| | `notes` | Text | — |
| Inversos | `request_ids` | One2many → maintenance.request, inverse `plan_id` | — |
| | `movement_ids` | One2many → maintenance.equipment.movement, inverse `linked_plan_id` | — |

Constraints nativos ([SPEC] §7, C-03…C-06):

- **C-03** `@api.constrains('state', 'force_close_reason')`: `partially_done` exige motivo.
- **C-04** `@api.constrains('state', 'scheduled_date', 'slack_days', 'location_id')`: no solapamiento de ventanas `±slack` entre **series distintas** del mismo punto, estados activos `draft/scheduled/in_progress`. Respeta `self.env.context.get('skip_overlap_check')` (escrituras de la cascada).
- **C-05** `@api.constrains('state')`: `done` exige 0 hijas vivas pendientes.
- **C-06** `@api.constrains('active')`: no archivar plan en `draft/scheduled/in_progress` (primero cancelar).

Lógica de negocio (métodos; semántica exacta en el [SPEC] indicado):

| Método | Origen | Semántica |
| --- | --- | --- |
| `create(vals_list)` | SA-00 | name por secuencia, `series_id`, `seq_in_series=1` si vacío, `original_scheduled_date = scheduled_date` |
| `write(vals)` | AA-01/02/03/17 | detecta transiciones y delega: entra a `scheduled` → `_generate_children()`; entra a `done/partially_done` → `_cascade_on_close()`; cambia `scheduled_date` → `_propagate_schedule_to_children()` (SA-06: solo hijas vivas con fecha distinta, ancla **12:00 UTC**) y `_check_out_of_range()` (SA-13: marca/desmarca `out_of_range` contra `contract_end_date`) |
| `_generate_children()` | SA-01 | snapshot del punto si vacío (equipos activos con `location == punto`; los que están en Lab/Bodega quedan fuera solos) + una `maintenance.request` por equipo sin hija: name `f"{plan.name} | {equipo.name}"`, `plan_id`, `schedule_date` 12:00 UTC, `work_type='Mantención Preventiva'`, herencia de user/team/type. Stage inicial: **primer stage por sequence** (no hardcodear `stage_id=1`, corrige el snippet del [SPEC]) |
| `_cascade_on_close()` | SA-02 | fija `close_date`; `base = scheduled_date` si `|close−sched| ≤ slack` sino `close_date`; `next = base + período` (dateutil para month/year); `_shift_to_workday()` con `resource_calendar_id.plan_days(1, dt, compute_leaves=True)`; si `next > contract_end_date` → chatter "Serie finalizada por término de contrato" y fin; si hay `next_plan_id` en draft/scheduled → re-fechar con `skip_overlap_check` + **re-fechado en bloque de la cola** (paso 4-bis: cada eslabón = anterior + período; lo que pase el contrato → `out_of_range`, guard 60); si no hay siguiente → `copy()` de la ocurrencia n+1 (defaults del [SPEC]); carryover si `partially_done`: duplicar hijas pendientes en n+1 con prefijo `[Arrastrada]` y **archivar** las originales |
| `action_sync_with_location()` | SA-03 | botón; solo `draft/scheduled`; re-snapshot + hijas para faltantes si `scheduled`; sobrantes se conservan y loggean |
| `action_cancel()` | SA-04 | vía `plan.cancel.wizard` (confirmación): archiva hijas vivas (`archive=True, kanban_state='blocked'`), `state='cancelled'`, **puentea la cadena** prev↔next |
| `action_project_series()` | SA-07 | botón; exige `auto_replan`; camina al último eslabón; genera `draft` encadenadas hasta `contract_end_date` (o 12 sin contrato; tope 60); idempotente |
| `_cron_promote_next_week()` | SA-15 / CR-01 | jueves AM: `draft` con fecha en lunes–domingo siguiente → `scheduled` (dispara `_generate_children()` vía `write`) |
| `_cron_weekly_report()` | SA-14 / CR-02 | mail calendario semanal identidad WE TECHS (ver §3.7) |
| `_cron_monthly_report()` | SA-16 / CR-03 | mail carta Gantt mensual (ver §3.7) |
| `_cron_upcoming_alert()` | SA-18 / AA-05 | cron **diario** (reemplaza la AA timed): planes `draft/scheduled` con `scheduled_date − hoy == 7` → `message_post` con `partner_ids` = responsable + técnico. Guard de idempotencia por igualdad exacta de fecha (corre 1 vez por ocurrencia) |

### 3.2 Modelo `maintenance.equipment.movement`

`_name = 'maintenance.equipment.movement'` · `_description = 'Movimiento de Equipo'` · `_inherit = ['mail.thread']` · `_order = 'date_out desc, id desc'`

| Campo | Tipo | Origen Studio | Notas |
| --- | --- | --- | --- |
| `name` | Char, required, readonly, default `'New'` | `x_name` | `create()`: `MOV-{YYYY}-{seq:04d} / {equipment.name}` |
| `equipment_id` | Many2one → maintenance.equipment, required, index, `ondelete='restrict'` | `x_studio_equipment_id` | — |
| `from_location_id` / `to_location_id` | Many2one → maintenance.location | `x_studio_from/to_location_id` | NULL = stock / servicio externo / baja |
| `reason` | Selection, required | `x_studio_reason` | `installation · calibration · repair · reassignment · return_from_service · decommission` ([SPEC] §3.bis.1). ⚠️ El snippet SA-09 del [SPEC] contiene el typo `'out_of _service'` para destino 594 — acá el valor correcto es **`repair`** (coherente con la selection y con SA-11/AA-15). La ETL normaliza datos viejos con ese typo (§5.2). |
| `date_out` | Date, required, default hoy | — | — |
| `date_in` | Date | — | el auto-movement la setea `= date_out` (hecho consumado) |
| `state` | Selection `completed/cancelled`, required, default `completed` | — | sin `in_transit` |
| `replaced_by_id` | Many2one → maintenance.equipment | — | anotación manual |
| `linked_request_id` | Many2one → maintenance.request | — | limitación conocida: NULL en flujos automáticos ([SPEC] §12.3) |
| `linked_plan_id` | Many2one → maintenance.plan | — | referencia débil |
| `notes` | Text | — | — |

Lógica:

- `create()` — **SA-MOV-00**: autogenerar `name` si viene vacío; **SA-11** (Req 3): si `reason == 'repair'`, archivar las hijas de plan abiertas del equipo (`plan_id != False`, no archivadas, stage no done) con `kanban_state='blocked'` y postear el resumen en cada plan afectado. `calibration` **no** archiva nada.
- ACL append-only: `unlink` solo superusuario (ni siquiera Plan Manager, [SPEC] §10.2); `write` solo Plan Manager.

### 3.3 Herencias (`we_maintenance_plan`)

**`maintenance.location`** (_inherit): inversos `plan_ids`, `movement_out_ids`, `movement_in_ids`; override `write(vals)`:
- Si cambia `contract_end_date` → `_recompute_series_for_contract()` (**SA-12**, Req 1): ocurrencias `draft` sin hijas más allá del término → `unlink`; `scheduled` con hijas → cancelar + archivar hijas; `out_of_range` no se toca; procesar de la más lejana al corte; resumen en chatter. En código ya no dispara "en cada write": **solo cuando la clave está en `vals` y la fecha se acorta**.
- Si cambia `frequency_value`/`frequency_unit` → `_reschedule_pending_series()` (**SA-19**): por cada serie viva del punto, la **cabeza** (primera no cerrada) conserva su fecha; la cola se re-fecha `anterior + período` con calendario laboral; lo que pase el contrato → `out_of_range`. Cambiar solo `slack_days` no mueve fechas. **Orden dentro del mismo write:** primero contrato (SA-12), después recadenciado (SA-19) — mismo criterio de secuencia AA-14 < AA-18 del [SPEC].

**`maintenance.equipment`** (_inherit):
- `managed_by_plan` — Boolean compute stored ([SPEC] §4): True si `location.plan_ids` tiene planes activos en `draft/scheduled/in_progress`. Solo informativo (badge + filtro).
- `movement_ids` — One2many → movement, inverse `equipment_id`.
- override `write(vals)` — **SA-09**: si `'location'` está en `vals` y **cambia realmente** (comparar contra el valor previo — en código no hace falta reconstruirlo desde la bitácora), crear el movement con `reason` inferido: destino NULL → `decommission`; destino 593 → `calibration`; destino 594 → `repair`; origen 593/594 → destino punto → `return_from_service`; punto → punto → `reassignment`; sin origen → `installation`. Respeta `skip_auto_movement` en contexto. `date_in = date_out = hoy`, `state='completed'`.
  - Los IDs 593/594 van como **parámetros de sistema** (`ir.config_parameter`: `we_maintenance.lab_location_id`, `we_maintenance.stock_location_id`) con default 593/594 — no literales dispersos.
  - El **baseline implícito 594** y el **seed** del [SPEC] §3.bis.5-bis eran necesarios porque la SA no veía el valor previo; en código el valor previo es directo, así que **no se necesita re-seedear**: la bitácora existente migrada (§5.2) queda como historial y el override registra los cambios desde el cutover.

**`maintenance.request`** (_inherit):
- `plan_id` — Many2one → maintenance.plan, index, tracking, `ondelete='set null'`.
- `create()` — **SA-10**: si `plan_id` vacío + `maintenance_type='preventive'` + `work_type` vacío → `work_type='Mantención del Equipo'` (etiqueta las hijas nativas del cron core).
- `write(vals)` — **SA-17** (Req 8): si cambia `stage_id` y la request tiene `plan_id`: (a) 100% de hijas vivas en stage done → plan `done` (dispara la cascada); (b) alguna hija dejó el stage inicial y el plan está `scheduled` → `in_progress`. Guard: planes en estados terminales/`out_of_range` no se tocan.

### 3.4 Vistas ([SPEC] §6 adaptado)

- **Form plan**: statusbar `state` + badge espejo con el semáforo ([SPEC] §6, tabla de `decoration-*`); botones "Proyectar serie" (`action_project_series`), "Sync con punto", "Cancelar" (wizard). 2 columnas + tabs "Equipos" (snapshot), "Hijas" (`request_ids`), "Auditoría". Cadencia/slack **readonly** con link al punto. Chatter.
- **List**: `decoration-danger` para `out_of_range`, `decoration-warning` para `is_approaching`, etc. (orden de prioridad del [SPEC] §6: el rojo gana al ámbar).
- **Kanban** agrupado por `state`; **Calendar** por `scheduled_date` color `state`.
- **Gantt** (Enterprise, `<gantt>`): **`date_start="scheduled_date"` y `date_stop="scheduled_date"`** — barra puntual en la fecha programada (decisión del equipo: NO se usa la ventana ±slack ni existen `gantt_start/stop`). `default_group_by="location_id"`, color por `state`, escala por defecto mes. Las barras no se arrastran editando la serie: documentar que la fecha se cambia por form/cascada.
- **Movement**: form ([SPEC] §3.bis.3) + list de auditoría ([SPEC] §3.bis.4) con filtros "Calibraciones", group-by equipo/origen/destino/reason.
- **Equipment**: badge "Gestionado por plan" (`managed_by_plan`), tab "Historial de movimientos" (`movement_ids`).
- **Request**: `plan_id` readonly cuando ya viene seteado (`attrs`).
- **Location**: tabs "Planes" (`plan_ids`) e "Historial de equipos" (`movement_in_ids`/`movement_out_ids`).

### 3.5 Crons (`data/ir_cron_data.xml`)

| Cron | Cadencia | Método |
| --- | --- | --- |
| CR-01 Promover semana siguiente | semanal, nextcall jueves 08:00 | `_cron_promote_next_week` |
| CR-02 Reporte semanal | semanal, jueves 08:15 (**después** de CR-01) | `_cron_weekly_report` |
| CR-03 Reporte mensual | mensual, día 1 08:00 | `_cron_monthly_report` |
| CR-04 Alerta −7 días (nuevo, reemplaza AA-05 timed) | diario 07:30 | `_cron_upcoming_alert` |

### 3.6 Secuencias (`data/ir_sequence_data.xml`)

| Code | Prefijo | Padding | Uso |
| --- | --- | --- | --- |
| `maintenance.plan` | *(ninguno — el `PMP-` lo pone `create()`)* | 4 | name del plan |
| `maintenance.plan.series` | ninguno | 6 | `series_id` |
| `maintenance.equipment.movement` | ninguno | 4 | name del movement |

### 3.7 Reportes de correo (SA-14 / SA-16 / SA-18)

- Implementarlos como **QWeb templates** (`mail_template_data.xml` + templates `ir.ui.view`) renderizados desde los métodos cron — no como strings f-string gigantes (los snippets del [SPEC] son la maqueta de referencia, con la identidad WE TECHS: paleta `#F26522`/`#2B2B2D`, jerarquía eyebrow→título→chip, doble trazo, estilos inline + `<table>`).
- **Maquetas HTML de referencia**: `maintenance_plan/report-example/reporte_semanal.html` y `reporte_mensual.html` (abrir y replicar).
- Semanal: calendario Lun–Vie (finde solo si tiene ocurrencias), tarjeta por ocurrencia con punto/estado/equipos del snapshot. Destinatarios: partners de `user_id` + `technician_user_id` de cada ocurrencia. No enviar si no hay ocurrencias.
- Mensual: matriz punto × día con conteo de hijas (`plan_id != False`, no archivadas) del mes + fila de carga diaria. Destinatarios: `user_id` de las hijas + responsables de los planes.
- Envío vía `mail.mail` con `recipient_ids`.

### 3.8 Seguridad ([SPEC] §10, sin multi-company)

`security/maintenance_plan_groups.xml`:

| Grupo | implied | XML-ID sugerido |
| --- | --- | --- |
| Maintenance / Plan Manager | `maintenance.group_equipment_manager` | `group_maintenance_plan_manager` |
| Maintenance / Plan User | `maintenance.group_maintenance_user` (o base.group_user si no existe) | `group_maintenance_plan_user` |

`ir.model.access.csv`:

| Modelo | Grupo | r | w | c | u |
| --- | --- | --- | --- | --- | --- |
| maintenance.plan | Plan Manager | ✔ | ✔ | ✔ | ✔ |
| maintenance.plan | Plan User | ✔ | – | – | – |
| maintenance.equipment.movement | Plan Manager | ✔ | ✔ | ✔ | – |
| maintenance.equipment.movement | Plan User | ✔ | – | ✔ | – |
| maintenance.equipment.movement | Maintenance / User (core) | ✔ | – | **✔** | – |
| maintenance.location (en `we_maintenance_base`) | Maintenance / User | ✔ | – | – | – |
| maintenance.location | Maintenance / Manager | ✔ | ✔ | ✔ | ✔ |

> El `create` de movements para Maintenance/User es **obligatorio**: el override de `write()` del equipo corre como el usuario que escribe — incluido el usuario API de `pipeline_registro_II`. Sin él, mover un equipo lanza `AccessError` y revierte el write ([SPEC] §10.2). **Sin record rules multi-company** (decisión del equipo).

### 3.9 Tests (`tests/`)

Codificar el checklist manual del [SPEC] §11 como `TransactionCase`/`SavepointCase`, un método por ítem, nombrados `test_T01_create_plan`, `test_T06_close_within_slack`, … Excepciones:

- T-04/T-20b (cron nativo de equipment): simular llamando `maintenance.equipment._cron_generate_requests()` del core.
- T-26…T-29 (pipeline E2E): fuera del alcance de los tests del módulo — se validan en staging (F3) con el pipeline real.
- T-49: probar `_cron_upcoming_alert` directamente.
- Añadir tests de migración de datos donde aplique con datos sintéticos (no dependen del ETL real).

Odoo.sh **ejecuta los tests automáticamente** en cada build de rama development (con demo data): mantenerlos verdes es el gate de F2.

---

## 4. Tabla de trazabilidad completa (Studio → código)

| ID [SPEC] | Artefacto Studio | Artefacto en código | Dónde |
| --- | --- | --- | --- |
| C-01 / SA-C01 / AA-07 | SA python + AA | `@api.constrains` frequency_value | `we_maintenance_base/models/maintenance_location.py` |
| C-02 / SA-C02 / AA-08 | ídem | `@api.constrains` slack vs período | ídem |
| C-03 / SA-C03 / AA-09 | ídem | `@api.constrains` force_close_reason | `maintenance_plan.py` |
| C-04 / SA-C04 / AA-10 | ídem | `@api.constrains` solapamiento (+ `skip_overlap_check`) | ídem |
| C-05 / SA-C05 / AA-11 | ídem | `@api.constrains` done sin pendientes | ídem |
| C-06 / SA-C06 / AA-12 | ídem | `@api.constrains` no archivar plan vivo | ídem |
| SA-00 / AA-00 | init on-create | `create()` | ídem |
| SA-01 / AA-01 | hijas al programar | `_generate_children()` desde `write()` | ídem |
| SA-02 / AA-02 | cascada al cerrar | `_cascade_on_close()` | ídem |
| SA-03 | botón sync | `action_sync_with_location()` | ídem |
| SA-04 | botón cancelar | `action_cancel()` + wizard | ídem + `wizard/` |
| SA-06 / AA-03 | propagar fecha a hijas | `_propagate_schedule_to_children()` (solo si `scheduled_date` en vals) | ídem |
| SA-07 | botón proyectar | `action_project_series()` | ídem |
| SA-13 / AA-17 | fuera de rango | `_check_out_of_range()` desde `write()` | ídem |
| SA-12 / AA-14 | acortar contrato | `_recompute_series_for_contract()` desde `write()` de location | `maintenance_location.py` (plan) |
| SA-19 / AA-18 | recadenciar series | `_reschedule_pending_series()` desde `write()` de location | ídem |
| SA-09 / AA-06 | bitácora auto | `write()` de equipment (ve valor previo; sin seed ni baseline) | `maintenance_equipment.py` (plan) |
| SA-MOV-00 / AA-MOV-00 | init movement | `create()` del movement | `equipment_movement.py` |
| SA-11 / AA-15 | equipo dañado (Req 3) | dentro de `create()` del movement si `reason=='repair'` | ídem |
| SA-10 / AA-13 | etiquetar hijas nativas | `create()` de request | `maintenance_request.py` (plan) |
| SA-17 / AA-16 | estado padre (Req 8) | `write()` de request | ídem |
| SA-15 / CR-01 | jueves: promover (Req 7) | `_cron_promote_next_week()` + ir.cron | `maintenance_plan.py` + data |
| SA-14 / CR-02 | reporte semanal (Req 6) | `_cron_weekly_report()` + QWeb | ídem |
| SA-16 / CR-03 | reporte mensual (Req 6) | `_cron_monthly_report()` + QWeb | ídem |
| SA-18 / AA-05 | alerta −7d (Req 6) | `_cron_upcoming_alert()` (cron diario) | ídem |
| Computes §3.8 | compute Studio | `progress`, `delta_days_from_planned`, `adjusted_from_scheduled`, `is_approaching` | ídem |
| `gantt_start`/`gantt_stop` §3.8 | compute Studio | **ELIMINADOS** — la Gantt usa `scheduled_date` | — |
| `x_managed_by_plan` §4 | compute Studio | `managed_by_plan` compute stored | `maintenance_equipment.py` (plan) |
| Secuencias §8 | ir.sequence manuales | `ir_sequence_data.xml` | data |
| Grupos/ACL §10 | manuales | XML + CSV | security |
| Record rules §10.3 | multi-company | **OMITIDAS** (mono-compañía) | — |
| Seed bitácora §3.bis.5-bis | script one-shot | **NO SE REPITE** — la data migrada es el historial; el override ve el valor previo | — |

---

## 5. Migración de datos y cutover

> Todos los scripts van en `migrations/<versión>/` de cada módulo (convención `pre-migrate.py` / `post-migrate.py`) o como `post_init_hook` del manifest para la instalación inicial. Se ejecutan solos en el build de Odoo.sh al instalar/actualizar. **Idempotentes** (chequear existencia antes de insertar) — los builds de staging se rehacen desde backups de prod repetidas veces.

### 5.1 Fase F1 — `we_maintenance_base` (post_init_hook)

1. **pre**: `ALTER TABLE maintenance_equipment RENAME COLUMN location TO location_legacy;` (libera el nombre para la FK nueva; solo si la columna es varchar).
2. Copiar puntos preservando IDs:
   ```sql
   INSERT INTO maintenance_location
       (id, name, active, sequence, asset_id, coordinates, location_desc, location_desc_alt,
        contract_start_date, contract_end_date, frequency_value, frequency_unit, slack_days,
        create_uid, create_date, write_uid, write_date)
   SELECT id, x_name, x_active, COALESCE(x_studio_sequence, 10), x_studio_asset_id_1,
          x_studio_char_field_m8g1k, x_studio_ubicacin, x_studio_ubicacin_1,
          x_contract_start_date, x_contract_end_date, COALESCE(x_frequency_value, 1),
          COALESCE(x_frequency_unit, 'month'), COALESCE(x_slack_days, 3),
          create_uid, create_date, write_uid, write_date
   FROM x_maintenance_location;
   SELECT setval('maintenance_location_id_seq', (SELECT MAX(id) FROM maintenance_location));
   ```
   (Verificar los nombres de columna reales contra `er_introspection.json` / `information_schema` antes de fijar el script.)
3. `UPDATE maintenance_equipment SET location = x_studio_location;` (mismos IDs → copia directa de FK).
4. `UPDATE maintenance_request SET work_type = x_studio_tipo_de_trabajo;` (keys idénticas).
5. Chatter del punto: `UPDATE mail_message SET model='maintenance.location' WHERE model='x_maintenance_location';` (ídem `mail_followers`, `mail_activity`).
6. **Verificación** (falla el hook si no cuadra): `count(maintenance_location) == count(x_maintenance_location)`; equipos con `location` == equipos con `x_studio_location`; existen IDs 593 y 594.
7. NO borrar el modelo/campos Studio: quedan como respaldo de solo-lectura hasta la fase de limpieza.

### 5.2 Fase F3 — `we_maintenance_plan` (post_init_hook / migration)

1. **ETL movements** (único modelo nuevo con datos):
   ```sql
   INSERT INTO maintenance_equipment_movement
       (id, name, equipment_id, from_location_id, to_location_id, reason,
        date_out, date_in, state, replaced_by_id, linked_request_id, notes,
        create_uid, create_date, write_uid, write_date)
   SELECT id, x_name, x_studio_equipment_id, x_studio_from_location_id,
          x_studio_to_location_id,
          CASE WHEN x_studio_reason IN ('out_of _service', 'out_of_service')
               THEN 'repair' ELSE x_studio_reason END,   -- normaliza el typo de SA-09
          x_studio_date_out, x_studio_date_in, COALESCE(x_studio_state, 'completed'),
          x_studio_replaced_by_id, x_studio_linked_request_id, x_studio_notes,
          create_uid, create_date, write_uid, write_date
   FROM x_equipment_movement;
   SELECT setval(...);
   ```
   (Los FKs de location apuntan a los mismos IDs — sin remapeo. `linked_plan_id` queda NULL: `x_maintenance_plan` no tiene datos. Migrar chatter como en 5.1.5.)
2. `x_maintenance_plan` **sin datos** → sin ETL de planes. Verificar antes: `SELECT COUNT(*) FROM x_maintenance_plan;` debe dar 0 — si no, detener y reportar.
3. **Desactivar el sistema Studio viejo — misma transacción del hook** (riesgo mayor del cutover: cascada/bitácora ejecutándose dos veces):
   ```python
   env['base.automation'].search([('model_id.model', 'in',
       ['x_maintenance_plan', 'x_equipment_movement', 'x_maintenance_location',
        'maintenance.equipment', 'maintenance.request'])]).write({'active': False})
   env['ir.cron'].search([('name', 'ilike', 'PMP%')]).write({'active': False})   # CR-01..03 Studio
   env['ir.sequence'].search([('code', 'in',
       ['maintenance.plan', 'maintenance.plan_serie', 'x_equipment_movement'])]
       ).filtered(lambda s: not s.company_id and s.create_uid.login != '__system__')
   ```
   Ajustar los dominios a los nombres reales de las AAs/SAs/crons en la instancia (inspeccionar en staging antes de fijar; loggear cuántos se desactivaron y abortar si el conteo no coincide con lo esperado).
4. Ocultar los menús/vistas Studio de plan y movement viejos (`ir.ui.menu.active = False`).
5. **NO eliminar** los `ir.model`/`ir.model.fields` Studio en esta fase — solo desactivar. La eliminación definitiva (Studio → Customizations o `ir.model.unlink`) va en una fase posterior, tras el período de validación en producción.

---

## 6. Ciclo de desarrollo entre ramas Odoo.sh

### 6.0 Cómo funciona el ciclo (referencia)

- El repo del proyecto tiene 3 categorías de ramas en Odoo.sh: **Production** (1 rama), **Staging** (ramas de validación con **copia neutralizada de la BD de producción**), **Development** (builds efímeros con datos demo o vacíos + **corren los tests automáticamente** al push).
- Flujo: crear rama development desde production → push → build automático → validar → **arrastrar la rama a Staging** (o merge en una rama staging) → probar contra datos reales neutralizados → **merge a production** → deploy (Odoo.sh toma backup automático previo y ejecuta `-u` sobre los módulos modificados).
- Los correos y crons en staging están **neutralizados** por defecto (mailcatcher, crons apagados): activar manualmente el cron a probar desde el backend de staging.
- Cada push a una rama re-instala/actualiza los módulos del repo cuyo código cambió; los hooks/migrations corren en ese momento.

### 6.1 Fases

| Fase | Rama development | Contenido | Gate para promover |
| --- | --- | --- | --- |
| **F0** | `feature/skeleton` | Estructura de ambos módulos (manifest, `__init__`, modelos vacíos), linter/config | Build verde en development |
| **F1** | `feature/base-takeover` | `we_maintenance_base` completo + migración §5.1 | En **staging** (copia fresca de prod): conteos de locations OK, IDs 593/594 existen, FKs de equipos pobladas, `work_type` poblado, pipeline de prueba (o smoke test §7) funciona contra staging |
| **F2** | `feature/plan-module` | `we_maintenance_plan` completo (modelos, lógica, vistas, wizards, crons, seguridad, tests) **sin** el cutover §5.2 | Tests `test_T*` verdes en el build de development |
| **F3** | `feature/data-cutover` | Migración §5.2 (ETL movements + desactivación Studio) | En **staging** con copia fresca: conteo de movements migrados == origen, typo de reason normalizado, AAs/SAs/crons Studio inactivos, UAT manual del checklist [SPEC] §11 (al menos T-01→T-12, T-18→T-25c, T-40→T-52) |
| **F4** | — (merge staging → production) | Go-live **coordinado con el deploy de `pipeline_registro_II` actualizado** (§7) | Ventana fuera del cron del pipeline (`0 11 * * 1-6` UTC = corre a las 11:00 UTC; desplegar después de esa corrida). Backup automático de Odoo.sh + verificación post-deploy: crear un plan de prueba, mover un equipo, revisar bitácora |

Reglas de trabajo entre fases:

- **Una fase = una rama development**; al aprobarse, merge (o arrastre) a staging, validación, merge a production, y la siguiente rama se crea **desde production actualizado**.
- No acumular dos fases sin promover: F1 debe llegar a producción antes de arrancar F3 (F2 puede desarrollarse en paralelo porque no toca datos).
- Cambios de solo-código en una rama ya construida → Odoo.sh actualiza; cambios en data XML/migrations → verificar en el log del build que el hook corrió.
- `requirements.txt` del repo: no se anticipan dependencias nuevas (dateutil y lxml ya vienen con Odoo).

---

## 7. Actualización coordinada de `pipeline_registro_II` (fuera de los módulos Odoo)

Cambios que el pipeline necesita para operar contra el esquema nuevo — **se despliegan junto con F4**, no antes ni después:

| Referencia actual | Cambio | Alcance detectado |
| --- | --- | --- |
| modelo `x_maintenance_location` | → `maintenance.location` | `processor.py` (10 refs), `data_processing.py`, tests de `qa/scaffolding/` |
| campo `x_name` de location | → `name` | búsquedas de puntos por nombre |
| campo `maintenance.equipment.x_studio_location` | → `location` | `processor.py` (19 refs) |
| campo `maintenance.request.x_studio_tipo_de_trabajo` | → `work_type` | `processor.py` (31 refs) |
| IDs 593 / 594 | **sin cambio** (preservados por la migración) | — |
| valores de `work_type` (`Extracción`, `Calibración`, `Instalación`, …) | **sin cambio** (keys idénticas) | — |

Procedimiento sugerido: rama en el repo del pipeline con `grep -rn "x_maintenance_location\|x_studio_location\|x_studio_tipo_de_trabajo\|x_name"` como checklist; apuntar sus tests de integración (`qa/scaffolding/integration/`) contra el **staging de F3** antes del go-live. El usuario API del pipeline debe pertenecer a *Maintenance / User* (por el `create` de movements, §3.8).

---

## 8. Instrucciones y prohibiciones para el agente ejecutor

**Hacer:**
- Leer [SPEC] completo antes de cada fase; implementar la semántica, no la letra, de los snippets.
- Docstrings con el ID de origen (`"""Cascada al cerrar (SPEC SA-02, Req …)."""`).
- Ancla horaria **12:00 UTC** en todo `schedule_date` de hijas (evita el corrimiento de día en America/Santiago, [SPEC] SA-01).
- `resource.calendar.plan_days(1, dt, compute_leaves=True)` para correr fechas a día hábil.
- Introspectar la instancia (staging) antes de fijar: nombres reales de columnas Studio, valores reales de `x_studio_tipo_de_trabajo`, nombres de las AAs/SAs a desactivar.
- Mantener los tests T-* verdes en cada push a development.

**No hacer:**
- ❌ Usar Studio o crear registros `base.automation`/`ir.actions.server` para lógica nueva — todo va en Python del módulo.
- ❌ Renombrar o borrar campos Studio que NO están en el alcance (§1.4).
- ❌ Cambiar los IDs de `maintenance.location` en la migración.
- ❌ Eliminar los modelos Studio viejos en F3 (solo desactivar; la limpieza es una fase posterior).
- ❌ Tocar `pipeline_registro_II` desde los módulos Odoo (su cambio va por su propio repo/deploy, §7).
- ❌ Agregar campos `company_id`, record rules multi-company, o los computes `gantt_start`/`gantt_stop`.
- ❌ Hardcodear 593/594 fuera de los `ir.config_parameter` definidos en §3.3.

---

## 9. Verificación final (por fase)

- **F1**: script de conteos §5.1.6 + abrir un equipo en staging y ver `location` (m2o) poblado; smoke test del pipeline contra staging.
- **F2**: suite `tests/` completa verde en el build de development (Odoo.sh la corre al push); revisión visual de form/list/kanban/calendar/gantt con datos demo.
- **F3**: conteos de movements; confirmar en staging que las AAs Studio están inactivas (`Settings → Technical → Automation`) y que mover un equipo genera exactamente **un** movement (no dos); UAT del checklist [SPEC] §11.
- **F4**: post-deploy en producción — crear plan de prueba en un punto sandbox, ciclo completo T-01→T-08, borrar el plan de prueba; primera corrida real del pipeline al día siguiente monitoreada contra `x_inbox_integracion`.
