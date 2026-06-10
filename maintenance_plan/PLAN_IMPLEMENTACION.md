# Plan de Implementación — `x_maintenance_plan` (Mantención Preventiva por Punto)

> **Audiencia:** desarrollador / administrador funcional que va a construir la entidad directamente en Odoo Studio + Acciones Automatizadas + Acciones de Servidor.
> **Versión Odoo objetivo:** 17.0 (las rutas/menús son válidas para Studio v17; saas-17.x los renombra a *Automation Rules*).
> **Diagrama de referencia:** `propuesta_plan_punto.drawio` (en este mismo directorio).
> **Tiempo estimado:** 4–6 horas en una instancia limpia; 1–2 días si se valida con datos reales.

---

## 0. Prerrequisitos

| # | Requisito | Verificación |
|---|---|---|
| 1 | Módulo **Studio** instalado (acceso al ícono superior derecho). | Menú principal → Aplicaciones → "Studio". |
| 2 | Módulo **Maintenance** instalado y con datos (equipos, requests). | Menú principal → Mantenimiento. |
| 3 | Modelo Studio `x_maintenance_location` ya existe (verificado vía introspección). | `er_introspection.json` lo confirma. |
| 4 | Usuario con permisos de **Administrador Settings** + **Studio Manager**. | Settings → Users → tu usuario. |
| 5 | **Snapshot / backup** de la base antes de empezar. | Odoo Online: módulo Database Manager; on-premise: `pg_dump`. |
| 6 | Módulo `base_automation` (se instala con Studio). | Settings → Technical → Automation Rules debe ser accesible. |
| 7 | Acceso al menú **Settings → Technical → Server Actions** y **Settings → Technical → Database Structure → Models**. | Activá "Modo Desarrollador" (`?debug=1` en la URL o vía Settings). |

> ⚠ **Modo desarrollador obligatorio** durante toda la implementación. URL: agregá `?debug=1` o activá en *Settings → Developer Tools → Activate the developer mode*.

---

## 1. Hoja de ruta resumida

```
Paso 1   · Crear el modelo x_maintenance_plan en Studio           [Studio]
Paso 2   · Definir los 24 campos del modelo (incl. contrato)      [Studio]
Paso 3   · Crear el modelo x_equipment_movement (Opción B)        [Studio]
Paso 4   · Tocar maintenance.equipment (3 campos nuevos)          [Studio]
Paso 5   · Tocar maintenance.request (1 campo nuevo)              [Studio]
Paso 6   · Diseñar vistas (form / list / kanban / calendar)       [Studio]
Paso 7   · Restricciones (constrains) vía Studio                  [Studio]
Paso 8   · Server Actions con código Python (SA-01 … SA-09)       [Technical]
Paso 9   · Automated Actions que disparan las SA (AA-01 … AA-06)  [Studio/Technical]
Paso 10  · Grupos de seguridad y reglas de registro              [Technical]
Paso 11  · Testing manual + checklist de aceptación              [Manual]
Paso 12  · Integración con pipeline_registro_II (ya existente)    [Doc]
```

---

## 2. Paso 1 — Crear el modelo `x_maintenance_plan`

**Camino:** abrí cualquier vista del módulo Mantenimiento → click en el ícono **Studio** (esquina superior derecha) → en el panel izquierdo "Customizations" → **+ New Model**.

| Campo del wizard | Valor |
|---|---|
| Model Name | `Plan de Mantención Preventiva` |
| Technical Name (auto) | `x_maintenance_plan` |
| **Features a marcar** | ✅ Chatter · ✅ Archiving · ✅ User assignment · ✅ Date & Calendar · ✅ Pipeline stages · ✅ Custom Sorting · ✅ Company |
| Features a NO marcar | Tags · Picture · Lines · Notes · Monetary · Contact details |

Los features marcados habilitan automáticamente:
- `active` (Archive) — usado para soft-delete.
- `sequence` (Custom Sorting) — orden manual en listas.
- `name` — siempre presente.
- `user_id` — responsable del plan.
- `date` — Studio lo crea como `x_studio_date` (lo renombraremos al uso en Paso 2 o lo eliminaremos y crearemos `scheduled_date` propio).
- `priority` + `kanban_state` + `stage_id` — para vista Kanban.
- `company_id` — multi-empresa.
- chatter (`message_ids`, `message_follower_ids`, `activity_ids`) — auditoría obligatoria.

> 📚 Ref: [Models, modules and apps — Odoo 17 Studio](https://www.odoo.com/documentation/17.0/applications/studio/models_modules_apps.html)

**Al guardar**, Studio crea el módulo `studio_customization` que agrupa todo lo que sigue. Exportable al final desde *Studio → Customizations → Export*.

---

## 3. Paso 2 — Campos del modelo `x_maintenance_plan`

Trabajamos en *Studio → tu modelo nuevo → Form view*. Para cada campo: panel derecho **+ Field** → tipo → drag al canvas → configurar propiedades.

> **Convención:** Studio prefija con `x_studio_`. En esta guía nombro los campos sin el prefijo para mayor legibilidad — pero en pantalla aparecerán como `x_studio_<name>`. La excepción son los nativos del feature (`name`, `active`, `user_id`, etc.) que no llevan prefijo.

### 3.1 Identificación

| Campo | Tipo | Required | Default | Notas |
|---|---|---|---|---|
| `name` | char | ✓ | — | nativo. Pattern sugerido: `PMP-{YYYY}-{seq:04d}` (ver Paso 7, SA-00). |
| `location_id` | many2one → `x_maintenance_location` | ✓ | — | `ondelete='restrict'` para no borrar un punto con planes vivos. |
| `company_id` | many2one → `res.company` | ✓ | `=user.company_id` | nativo (feature Company). |

### 3.2 Programación

| Campo | Tipo | Required | Notas |
|---|---|---|---|
| `scheduled_date` | date | ✓ | — |
| `original_scheduled_date` | date | — | escrito en `create()` vía SA-00. Solo lectura desde UI. |
| `close_date` | date | — | seteado por SA-02 al cerrar. |
| `state` | selection | ✓ | Valores: `draft` · `scheduled` · `in_progress` · `done` · `partially_done` · `cancelled`. *Default:* `draft`. |

> En Studio el tipo *Selection* se configura desde el panel derecho → **Values** (formato `key:Label`).

### 3.3 Cadencia

| Campo | Tipo | Required | Notas |
|---|---|---|---|
| `frequency_value` | integer | ✓ | default 1, validar > 0 (constrain en Paso 6). |
| `frequency_unit` | selection | ✓ | `day` · `week` · `month` · `year`. default `month`. |
| `slack_days` | integer | — | tolerancia ± en días. default 3. |
| `auto_replan` | boolean | — | default `True`. |

### 3.4 Serie (auto-referencia)

| Campo | Tipo | Notas |
|---|---|---|
| `series_id` | char | uuid generado en SA-00. Indexed = ✓ (panel Field → "Indexed"). |
| `previous_plan_id` | many2one → `x_maintenance_plan` | `ondelete='set null'`. |
| `next_plan_id` | many2one → `x_maintenance_plan` | `ondelete='set null'`. |
| `seq_in_series` | integer | computado por SA-00; 1 para el primero de la serie. |

### 3.5 Responsables (se heredan a hijas)

| Campo | Tipo | Notas |
|---|---|---|
| `user_id` | many2one → `res.users` | nativo (feature User assignment) — responsable del plan. |
| `technician_user_id` | many2one → `res.users` | técnico por defecto. |
| `maintenance_team_id` | many2one → `maintenance.team` | — |
| `maintenance_type` | selection | `preventive` (default) · `corrective`. |

### 3.6 Calendario laboral

| Campo | Tipo | Notas |
|---|---|---|
| `resource_calendar_id` | many2one → `resource.calendar` | default: `company_id.resource_calendar_id` (vía related compute o default). |

### 3.7 Snapshot de equipos

| Campo | Tipo | Notas |
|---|---|---|
| `equipment_snapshot_ids` | many2many → `maintenance.equipment` | sin restricción de dominio en Studio; el dominio operativo lo aplica SA-01. |
| `last_sync_with_location` | datetime | timestamp del último wizard "Sync con punto". |

> Studio crea la tabla M2M con nombre automático tipo `x_maintenance_plan_maintenance_equipment_rel`. Anotalo: lo vas a usar en queries de auditoría.

### 3.8 Calculados (read-only)

| Campo | Tipo | Dependencias | Notas |
|---|---|---|---|
| `progress` | integer | `request_ids`, `request_ids.stage_id.done` | % hijas con `stage_id.done = True`. |
| `delta_days_from_planned` | integer | `close_date`, `scheduled_date` | `close - scheduled` (en días). |
| `adjusted_from_scheduled` | boolean | `scheduled_date`, `original_scheduled_date` | True si difieren. |

> ⚠ **Limitación de Studio en compute:** el sandbox bloquea `STORE_ATTR`. **No** uses `record.x_field = …`; usá la forma `for record in self: record['x_field'] = …`. Las dependencias se declaran en el campo "Dependencies" del panel derecho, separadas por coma. ([ref](https://medium.com/cybrosys/how-to-set-compute-function-for-field-using-odoo-17-studio-aa2ad46dd305))

**Snippet `progress`** (pegar en el field → Compute):
```python
for record in self:
    total = len(record.request_ids)
    if total:
        done = len(record.request_ids.filtered(lambda r: r.stage_id.done))
        record['progress'] = int(round(100.0 * done / total))
    else:
        record['progress'] = 0
```
Dependencies: `request_ids,request_ids.stage_id.done`

**Snippet `delta_days_from_planned`:**
```python
for record in self:
    if record.close_date and record.scheduled_date:
        record['delta_days_from_planned'] = (record.close_date - record.scheduled_date).days
    else:
        record['delta_days_from_planned'] = 0
```
Dependencies: `close_date,scheduled_date`

**Snippet `adjusted_from_scheduled`:**
```python
for record in self:
    record['adjusted_from_scheduled'] = bool(
        record.original_scheduled_date
        and record.scheduled_date
        and record.original_scheduled_date != record.scheduled_date
    )
```
Dependencies: `scheduled_date,original_scheduled_date`

### 3.9 Operativos extra

| Campo | Tipo | Notas |
|---|---|---|
| `force_close_reason` | text | requerido al pasar a `partially_done` (validación en Paso 6). |
| `notes` | text | libre. |

### 3.10 Contrato (related — la verdad vive en `x_maintenance_location`)

> ✅ **Decisión confirmada:** los campos de contrato viven en `x_maintenance_location` (single source of truth por punto/cliente). El plan los lee como **related store=True** para poder filtrar/indexar y para que el constraint de cascada sea performante.

**Crear en `x_maintenance_location` (sección 3.bis.6 más abajo):**

| Campo en location | Tipo | Notas |
|---|---|---|
| `x_contract_start_date` | date | informativo (inicio de servicio). |
| `x_contract_end_date` | date | **límite duro**: corta la cascada de los planes del punto. |

**Crear en `x_maintenance_plan` (esta sección):**

| Campo | Tipo | Related | Notas |
|---|---|---|---|
| `contract_start_date` | date (related, **store=True**) | `location_id.x_contract_start_date` | indexed para reportes. |
| `contract_end_date` | date (related, **store=True**) | `location_id.x_contract_end_date` | **límite duro**: la cascada NO genera ocurrencias con `scheduled_date > contract_end_date`. |

> 📌 En Studio v17 los related fields se configuran desde **+ Field → Related Field**. Marcar **Stored = ✓** es crítico: sin store, el related se evalúa en cada acceso y no puede usarse en dominios eficientes ni en constrains.
>
> **Cambio si se modifica el contrato en location**: el related almacenado se invalida automáticamente — el ORM recomputa al primer acceso o al próximo write. No requiere migración manual.
>
> **Comportamiento en cascada (SA-02):** después de calcular `next_date`, si `next_date > contract_end_date` (leído del related), se aborta la generación y se loggea `"Serie finalizada por término de contrato"` en el chatter. La serie muere sin tener que cancelarla manualmente.

### 3.11 Inverso

| Campo | Tipo | Notas |
|---|---|---|
| `request_ids` | one2many → `maintenance.request`, inverse `plan_id` | aparece una vez creado `plan_id` en `maintenance.request` (Paso 5). |
| `movement_ids` | one2many → `x_equipment_movement`, inverse `linked_plan_id` | trazabilidad de movimientos asociados al plan. |

---

## 3.bis Paso 3 — Crear el modelo `x_equipment_movement` (Opción B)

**Justificación:** los equipos no son inmóviles. Salen a calibrar, vuelven a otro punto, se reasignan, se dan de baja. Esta entidad guarda la **bitácora completa de movimientos** — sin esto, "¿dónde estuvo S1 en marzo?" solo se responde leyendo chatter. Con esto, es un `search_read`.

**Camino:** Studio → **+ New Model** → name: `Movimiento de Equipo` → technical: `x_equipment_movement`.

**Features a marcar:** ✅ Chatter · ✅ Company. *Nada más* (es un modelo simple de bitácora).

### 3.bis.1 Campos

| Campo | Tipo | Required | Notas |
|---|---|---|---|
| `name` | char | ✓ | autogenerado por SA-MOV-00: `MOV-{YYYY}-{seq:04d} / {equipment.name}`. Secuencia `x_equipment_movement`. |
| `equipment_id` | m2o → `maintenance.equipment` | ✓ | indexed. `ondelete='restrict'` (no se borra un equipo con historial). |
| `from_location_id` | m2o → `x_maintenance_location` | — | NULL = venía de stock / equipo nuevo. |
| `to_location_id` | m2o → `x_maintenance_location` | — | NULL = sale a stock / servicio externo / baja. |
| `reason` | selection | ✓ | `installation` · `calibration` · `repair` · `reassignment` · `return_from_service` · `decommission`. |
| `date_out` | date | ✓ | default `today`. |
| `date_in` | date | — | NULL mientras `state='in_transit'`. |
| `expected_return_date` | date | — | para alertas en tránsitos largos (cron de avisos opcional). |
| `replaced_by_id` | m2o → `maintenance.equipment` | — | equipo que ocupó el lugar (opcional). |
| `linked_request_id` | m2o → `maintenance.request` | — | orden de calibración/reparación asociada. |
| `linked_plan_id` | m2o → `x_maintenance_plan` | — | plan de origen (referencia débil, no FK fuerte). |
| `state` | selection | ✓ | `in_transit` · `completed` · `cancelled`. Default `completed` (SA-09 cierra el movement en el acto). El estado `in_transit` queda disponible para escenarios futuros (p. ej. equipos enviados a calibración con tracking de retorno). |
| `duration_days` | int (computed) | — | `(date_in or today) - date_out`. Dependencies: `date_in,date_out`. |
| `notes` | text | — | libre. |
| `company_id` | m2o → `res.company` | ✓ | heredado de `equipment_id.company_id` (default compute). |

**Snippet compute `duration_days`:**
```python
for record in self:
    end = record.date_in or datetime.date.today()
    if record.date_out:
        record['duration_days'] = (end - record.date_out).days
    else:
        record['duration_days'] = 0
```
Dependencies: `date_in,date_out`

**Snippet default `company_id`** (en el field → Default Value):
```python
equipment_id and equipment_id.company_id or env.company
```

### 3.bis.2 Inversos a crear en otros modelos

| Modelo | Campo | Tipo |
|---|---|---|
| `maintenance.equipment` | `movement_ids` | one2many → `x_equipment_movement`, inverse `equipment_id` |
| `x_maintenance_location` | `movement_out_ids` | one2many → `x_equipment_movement`, inverse `from_location_id` |
| `x_maintenance_location` | `movement_in_ids` | one2many → `x_equipment_movement`, inverse `to_location_id` |

### 3.bis.3 Vista form sugerida

- Header: `state` como statusbar.
- 2 columnas:
  - Izq: `equipment_id`, `from_location_id` → `to_location_id` (mismo renglón visual), `reason`, `replaced_by_id`.
  - Der: `date_out`, `date_in`, `expected_return_date`, `duration_days`, `linked_request_id`, `linked_plan_id`.
- Notes al final.

### 3.bis.4 Vista list (la importante para auditoría)

Columnas: `equipment_id`, `date_out`, `from_location_id`, `to_location_id`, `reason`, `state`, `duration_days`, `linked_request_id`.

Default order: `date_out desc`.

**Filtros y agrupaciones:**
- Filter "En tránsito": `[('state','=','in_transit')]`
- Filter "Calibraciones": `[('reason','=','calibration')]`
- Group by: `equipment_id`, `from_location_id`, `to_location_id`, `reason`, `state`.

### 3.bis.5 Consulta de oro habilitada

```python
# "¿Qué sondas pasaron por el punto Norte entre 2026-01-01 y hoy?"
movements = env['x_equipment_movement'].search([
    '|',
    '&', ('from_location_id', '=', norte.id), ('date_out', '>=', '2026-01-01'),
    '&', ('to_location_id', '=', norte.id),   ('date_in', '>=', '2026-01-01'),
])
equipos = movements.mapped('equipment_id')
```

### 3.bis.6 Cambios complementarios en `x_maintenance_location`

**Camino:** Studio → seleccioná cualquier punto → ícono Studio → **Form view** → **+ Field**.

| Campo | Tipo | Required | Notas |
|---|---|---|---|
| `x_contract_start_date` | date | — | inicio del contrato de servicio con el cliente. |
| `x_contract_end_date` | date | — | **fin del contrato — corta la generación de planes futuros**. Tracking ✓ (chatter). |
| `plan_ids` | one2many → `x_maintenance_plan` (inv `location_id`) | — | inverso — habilita la lista de planes en el form del punto. |
| `movement_out_ids` | o2m → `x_equipment_movement` (inv `from_location_id`) | — | inverso. |
| `movement_in_ids` | o2m → `x_equipment_movement` (inv `to_location_id`) | — | inverso. |

**Form view del punto** (sugerencia): tab "Contrato" con `x_contract_start_date`, `x_contract_end_date` + tab "Planes" con `plan_ids` (list embebida) + tab "Historial de equipos" con `movement_out_ids` y `movement_in_ids` unidos en una vista combinada.

> ⚠ Si cambiás `x_contract_end_date` para acortar el contrato y ya existen planes futuros generados más allá de la nueva fecha, **no se cancelan automáticamente**. Considerá una SA-12 manual "Recalcular serie por cambio de contrato" o un constraint que avise.

---

## 4. Paso 4 — Cambios en `maintenance.equipment`

**Camino:** Studio → seleccioná un equipo → ícono Studio → **Form view** → **+ Field**.

| Campo | Tipo | Propiedades |
|---|---|---|
| `x_managed_by_plan` | boolean (computed, stored) | Compute: ver snippet abajo. Dependencies: `x_studio_location,x_studio_location.plan_ids.state,x_studio_location.plan_ids.active,x_in_external_service`. **Stored = ✓** (necesario para filtros). Readonly = ✓. |
| `x_studio_period_backup` | integer | guarda el `period` original antes de que la AA lo ponga en 0. Readonly = ✓. |
| `x_in_external_service` | boolean (computed, stored) | True si existe un `x_equipment_movement` con `state='in_transit'`. Dependencies: `movement_ids,movement_ids.state`. Readonly = ✓. |
| `x_current_replacement_id` | many2one → `maintenance.equipment` (computed, stored) | Equipo que actualmente está ocupando el lugar de este. Tomado del último movement in_transit. Dependencies: `movement_ids,movement_ids.state,movement_ids.replaced_by_id`. Readonly = ✓. |

**Snippet compute `x_managed_by_plan`:**
```python
ACTIVE_STATES = ('draft', 'scheduled', 'in_progress', 'partially_done')
for record in self:
    if record.x_in_external_service:
        record['x_managed_by_plan'] = False
        continue
    plans = record.x_studio_location.plan_ids.filtered(
        lambda p: p.active and p.state in ACTIVE_STATES
    ) if record.x_studio_location else False
    record['x_managed_by_plan'] = bool(plans)
```

**Snippet compute `x_in_external_service`:**
```python
for record in self:
    record['x_in_external_service'] = bool(
        record.movement_ids.filtered(lambda m: m.state == 'in_transit')
    )
```

**Snippet compute `x_current_replacement_id`:**
```python
for record in self:
    in_transit = record.movement_ids.filtered(
        lambda m: m.state == 'in_transit'
    ).sorted('date_out', reverse=True)
    record['x_current_replacement_id'] = (
        in_transit[0].replaced_by_id.id if in_transit and in_transit[0].replaced_by_id else False
    )
```

> 💡 `plan_ids` es el **inverso** que tenés que crear sobre `x_maintenance_location`: campo one2many → `x_maintenance_plan`, inverse `location_id`. Hacelo ahora — *Studio → x_maintenance_location → + Field*.

**UX:** agregá en la cabecera del Form view de equipment:
- Badge "⚙ Gestionado por plan PMP-XXX" si `x_managed_by_plan = True`.
- Badge rojo "🚚 En servicio externo (reemplazo: <nombre>)" si `x_in_external_service = True`. Este estado se infiere automáticamente del último `x_equipment_movement` con `state='in_transit'` — no requiere acción manual desde Odoo; el pipeline existente (`processor.py`) ya gestiona los flujos de calibración/reemplazo desde Connecteam (ver Paso 12).

Adicionalmente, agregá en el form de equipment un **tab "Historial de movimientos"** con el campo `movement_ids` como lista embebida (columnas: `date_out`, `from_location_id`, `to_location_id`, `reason`, `state`, `duration_days`). Esto da timeline inmediata por equipo.

---

## 5. Paso 5 — Cambios en `maintenance.request`

| Campo | Tipo | Propiedades |
|---|---|---|
| `plan_id` | many2one → `x_maintenance_plan` | `ondelete='set null'` (la baja del padre no borra trazabilidad). Indexed = ✓. Tracking = ✓ (Chatter). |

Adicionalmente, abrí el **Form view** de `maintenance.request` y agregá `plan_id` arriba del bloque de programación, en modo readonly cuando el campo viene autogenerado:
```xml
<field name="plan_id" attrs="{'readonly': [('plan_id', '!=', False)]}"/>
```
(Studio te lo deja editar en modo visual; el `attrs` lo pegás desde el editor XML del campo → menú "Edit XML".)

---

## 6. Paso 6 — Vistas

> **Recomendación:** dejá las vistas para después de probar las Server Actions con datos cargados a mano. Las vistas se iteran rápido en Studio; la lógica no.

### Form view (`x_maintenance_plan`)
- Header: `state` como statusbar (botones `scheduled`, `in_progress`, `done`, `partially_done`, `cancelled` en ese orden).
- 2 columnas:
  - Columna izq: `location_id`, `name`, `scheduled_date`, `close_date`, `frequency_value`/`frequency_unit` (inline), `slack_days`, `auto_replan`.
  - Columna der: `user_id`, `technician_user_id`, `maintenance_team_id`, `resource_calendar_id`, `series_id`, `seq_in_series`, `previous_plan_id`, `next_plan_id`.
- Tab "Equipos" → `equipment_snapshot_ids` (vista list) + botón "Sync con punto" (Server Action SA-03).
- Tab "Hijas" → `request_ids` (vista list embebida) con columnas `name`, `equipment_id`, `schedule_date`, `stage_id`, `kanban_state`.
- Tab "Auditoría" → `original_scheduled_date`, `delta_days_from_planned`, `adjusted_from_scheduled`, `force_close_reason`, `last_sync_with_location`, `notes`.
- Chatter al pie.

### Kanban view
- Agrupar por `series_id` o por `state`. Cards con `name`, `location_id`, `scheduled_date`, badge `progress`, ícono `adjusted_from_scheduled`.

### Calendar view
- Date field: `scheduled_date`. Color by: `state`. Filter por `location_id`, `maintenance_team_id`.

### List view
- Columnas: `name`, `location_id`, `scheduled_date`, `state`, `progress`, `delta_days_from_planned`, `user_id`.

### Gantt view (opcional, requiere enterprise)
- Start: `scheduled_date`, Stop: `scheduled_date + maintenance_duration` (computed). Grouped by `location_id`.

---

## 7. Paso 7 — Restricciones (validaciones de modelo)

Studio v17 expone **Constraints** desde *Studio → tu modelo → Constraints → + New*. Los snippets a continuación usan `self` como recordset (el editor de constraints es como un onchange / método regular). Si tu instalación de Studio no expone "Constraints" directamente, usá Server Actions con trigger `Before save` (Paso 8) — funcionalmente equivalente.

### C-01 — frequency_value > 0
```python
for record in self:
    if record.frequency_value <= 0:
        raise ValidationError(_("La frecuencia debe ser mayor a 0."))
```

### C-02 — slack_days no puede superar el período base
```python
UNIT_DAYS = {'day': 1, 'week': 7, 'month': 30, 'year': 365}
for record in self:
    period_days = record.frequency_value * UNIT_DAYS.get(record.frequency_unit, 30)
    if record.slack_days >= period_days:
        raise ValidationError(_(
            "slack_days (%s) debe ser menor que el período base (%s días)."
        ) % (record.slack_days, period_days))
```

### C-03 — `force_close_reason` requerido si state='partially_done'
```python
for record in self:
    if record.state == 'partially_done' and not (record.force_close_reason or '').strip():
        raise ValidationError(_(
            "Para cerrar como ‘partially_done’ debe registrar el motivo en force_close_reason."
        ))
```

### C-04 — No solapamiento de planes activos en el mismo punto
```python
from datetime import timedelta
ACTIVE = ('draft', 'scheduled', 'in_progress')
for record in self:
    if record.state not in ACTIVE or not record.scheduled_date:
        continue
    window_start = record.scheduled_date - timedelta(days=record.slack_days)
    window_end   = record.scheduled_date + timedelta(days=record.slack_days)
    overlap = self.search([
        ('id', '!=', record.id),
        ('location_id', '=', record.location_id.id),
        ('state', 'in', ACTIVE),
        ('scheduled_date', '<=', window_end),
        ('scheduled_date', '>=', window_start),
    ])
    if overlap:
        raise ValidationError(_(
            "Solapamiento con plan %s (programado %s)."
        ) % (overlap[0].name, overlap[0].scheduled_date))
```

> Esta restricción C-04 puede chocar contra la cascada cuando ésta empuja varias ocurrencias a la vez. La SA-02 (cascada) debe correr en `sudo()` y dentro de un único `try/except` para reportar conflictos al usuario sin abortar parcialmente.

---

## 8. Paso 8 — Server Actions

**Camino:** *Settings → Technical → Server Actions → New*. Para cada SA: **Model = x_maintenance_plan** salvo cuando se indique otro modelo (SA-05 y SA-09 son sobre `maintenance.equipment`; SA-MOV-00 sobre `x_equipment_movement`); **Type = Execute Python Code**.

> 📚 Ref: [Server Actions reference — Odoo 17](https://www.odoo.com/documentation/17.0/developer/reference/backend/actions.html)
>
> **Variables disponibles en el sandbox** ([ref](https://www.odoo.com/documentation/17.0/applications/studio/automated_actions.html)):
> `env, model, record, records, time, datetime, dateutil, timezone, float_compare, log(), _logger.info(), UserError, Command, action`

---

### SA-00 — Inicialización en `create()` (series_id, original_scheduled_date, name)

**Trigger:** se invoca desde la AA-00 (On creation).

```python
import uuid
for rec in records:
    vals = {}
    if not rec.series_id:
        vals['series_id'] = uuid.uuid4().hex
        vals['seq_in_series'] = 1
    if not rec.original_scheduled_date and rec.scheduled_date:
        vals['original_scheduled_date'] = rec.scheduled_date
    if not rec.name or rec.name == _('New'):
        seq = env['ir.sequence'].next_by_code('x_maintenance_plan') or '0001'
        loc = rec.location_id.x_name or '?'
        vals['name'] = f"PMP-{rec.scheduled_date.year if rec.scheduled_date else '????'}-{seq} / {loc}"
    if vals:
        rec.write(vals)
```

> 💡 Cargá una secuencia: *Settings → Technical → Sequences → New*, code `x_maintenance_plan`, prefix `PMP-`, padding 4.

---

### SA-01 — Generar hijas al pasar a `scheduled`

**Trigger:** AA-01 (state cambia a `scheduled`).

```python
for plan in records:
    # 1) Snapshot del punto si todavía está vacío
    if not plan.equipment_snapshot_ids:
        equipos = env['maintenance.equipment'].search([
            ('x_studio_location', '=', plan.location_id.id),
            ('active', '=', True),
            ('company_id', '=', plan.company_id.id),
        ])
        plan.equipment_snapshot_ids = [Command.set(equipos.ids)]
        plan.last_sync_with_location = datetime.datetime.now()

    # 2) Crear una maintenance.request por cada equipo del snapshot que aún no tenga hija
    existentes = plan.request_ids.mapped('equipment_id')
    nuevos = plan.equipment_snapshot_ids - existentes
    for equipo in nuevos:
        env['maintenance.request'].create({
            'name': f"{plan.name} - {equipo.name}",
            'equipment_id': equipo.id,
            'plan_id': plan.id,
            'schedule_date': plan.scheduled_date,
            'maintenance_type': 'preventive',
            'user_id': (plan.technician_user_id or plan.user_id).id or False,
            'maintenance_team_id': plan.maintenance_team_id.id or False,
            'company_id': plan.company_id.id,
        })

    plan.message_post(
        body=_("Generadas %s solicitudes hijas a partir del snapshot del punto.") % len(nuevos),
    )
```

---

### SA-02 — Cascada al cerrar (`done` / `partially_done`)

**Trigger:** AA-02 (state pasa a `done` o `partially_done`).

```python
from datetime import timedelta

UNIT = {'day': 'days', 'week': 'weeks', 'month': 'days', 'year': 'days'}
def add_period(base, value, unit):
    # week/day directos; month/year usan dateutil para ser precisos
    if unit == 'day':
        return base + timedelta(days=value)
    if unit == 'week':
        return base + timedelta(weeks=value)
    if unit == 'month':
        return base + dateutil.relativedelta.relativedelta(months=value)
    if unit == 'year':
        return base + dateutil.relativedelta.relativedelta(years=value)
    return base

def shift_to_workday(date, calendar):
    if not calendar:
        return date
    # plan_days(1, dt): primer día hábil >= dt
    dt = datetime.datetime.combine(date, datetime.time(8, 0))
    next_dt = calendar.plan_days(1, dt, compute_leaves=True)
    return next_dt.date() if next_dt else date

for plan in records:
    if not plan.close_date:
        plan.close_date = datetime.date.today()

    # 1) Calcular próxima fecha base
    delta_days = (plan.close_date - plan.scheduled_date).days
    within_slack = abs(delta_days) <= plan.slack_days
    base_for_next = plan.scheduled_date if within_slack else plan.close_date
    next_date = add_period(base_for_next, plan.frequency_value, plan.frequency_unit)

    # 2) Ajuste por calendario laboral
    next_date = shift_to_workday(next_date, plan.resource_calendar_id)

    # 3) ✨ LÍMITE DURO POR TÉRMINO DE CONTRATO
    if plan.contract_end_date and next_date > plan.contract_end_date:
        plan.message_post(body=_(
            "Serie %s finalizada por término de contrato (%s). "
            "No se generará la próxima ocurrencia (next_date hubiera sido %s)."
        ) % (plan.series_id, plan.contract_end_date, next_date))
        continue   # salta a la próxima iteración del for plan in records

    # 4) Aplicar a la siguiente ocurrencia (recursivo)
    if plan.auto_replan:
        nxt = plan.next_plan_id
        if nxt and nxt.state in ('draft', 'scheduled'):
            old = nxt.scheduled_date
            nxt.write({'scheduled_date': next_date})
            # propagar a hijas vivas
            hijas_vivas = nxt.request_ids.filtered(lambda r: not r.stage_id.done)
            hijas_vivas.write({'schedule_date': next_date})
            nxt.message_post(body=_(
                "Fecha reprogramada por cascada desde %s: %s → %s"
            ) % (plan.name, old, next_date))
            # encadenar (re-ejecutar SA-02 sobre nxt si nxt ya tenía cierre… raro pero contemplado)
            # Para evitar recursión infinita: solo cascadear si la diferencia es significativa
            if nxt.close_date:
                env.ref('your_module.sa_02_cascade').with_context(active_ids=nxt.ids).run()
        elif not nxt:
            # 5) Generar la siguiente ocurrencia (hereda contract_start/end)
            new_plan = plan.copy(default={
                'name': False,                     # SA-00 le pondrá uno nuevo
                'scheduled_date': next_date,
                'state': 'draft',
                'close_date': False,
                'previous_plan_id': plan.id,
                'next_plan_id': False,
                'series_id': plan.series_id,
                'seq_in_series': plan.seq_in_series + 1,
                'original_scheduled_date': next_date,
                'equipment_snapshot_ids': [Command.clear()],
                'force_close_reason': False,
                # 'contract_start_date' y 'contract_end_date' viajan tal cual via copy()
            })
            plan.next_plan_id = new_plan.id

    # 6) Carryover si cerró parcial
    if plan.state == 'partially_done' and plan.next_plan_id:
        pendientes = plan.request_ids.filtered(lambda r: not r.stage_id.done)
        for hija in pendientes:
            env['maintenance.request'].create({
                'name': f"[CARRYOVER {plan.name}] {hija.name}",
                'equipment_id': hija.equipment_id.id,
                'plan_id': plan.next_plan_id.id,
                'schedule_date': plan.next_plan_id.scheduled_date,
                'maintenance_type': hija.maintenance_type,
                'description': _("Arrastrada desde %s (no completada).") % plan.name,
            })
        plan.message_post(body=_(
            "%s solicitudes arrastradas como carryover al siguiente plan."
        ) % len(pendientes))
```

> ⚠ Para evitar recursión infinita en cascadas largas, considerá agregar un guard `if env.context.get('cascade_depth', 0) > 10: return` y pasar `with_context(cascade_depth=ctx+1)`.

---

### SA-03 — Wizard "Sync con punto"

**Trigger:** botón en el form view del plan (botón hecho desde Studio → "Add Button" → "Trigger Server Action" → SA-03).

```python
for plan in records:
    if plan.state not in ('draft', 'scheduled'):
        raise UserError(_("Solo se puede sincronizar planes en draft o scheduled."))

    equipos_punto = env['maintenance.equipment'].search([
        ('x_studio_location', '=', plan.location_id.id),
        ('active', '=', True),
        ('company_id', '=', plan.company_id.id),
    ])

    en_snapshot = plan.equipment_snapshot_ids
    faltantes = equipos_punto - en_snapshot
    sobrantes = en_snapshot - equipos_punto

    plan.equipment_snapshot_ids = [Command.set(equipos_punto.ids)]
    plan.last_sync_with_location = datetime.datetime.now()

    # Crear hijas para los faltantes si el plan ya está scheduled
    if plan.state == 'scheduled':
        for equipo in faltantes:
            env['maintenance.request'].create({
                'name': f"{plan.name} - {equipo.name}",
                'equipment_id': equipo.id,
                'plan_id': plan.id,
                'schedule_date': plan.scheduled_date,
                'maintenance_type': 'preventive',
            })

    # Las hijas de los sobrantes no se borran: se loggean
    plan.message_post(body=_(
        "Sync con punto: +%s equipos, -%s equipos (las hijas sobrantes se conservan)."
    ) % (len(faltantes), len(sobrantes)))
```

---

### SA-04 — Cancelar plan + hijas (con confirmación)

**Trigger:** botón "Cancelar" en el form (visible solo si state ≠ cancelled/done).

```python
for plan in records:
    hijas_vivas = plan.request_ids.filtered(
        lambda r: r.stage_id.id not in env['maintenance.stage'].search([('done','=',True)]).ids
    )
    hijas_vivas.write({'archive': True, 'kanban_state': 'blocked'})
    plan.write({'state': 'cancelled'})
    plan.message_post(body=_(
        "Plan cancelado. %s hijas archivadas. La serie continúa desde el último plan ‘done’."
    ) % len(hijas_vivas))
```

> Para la confirmación: definí esta SA con `binding_model_id = x_maintenance_plan` y `binding_view_types = form`, y al disparar abrí un wizard transitorio que pida confirmación. Si no querés crear el wizard, configurá la AA con un `confirm` JS-side desde el form view button.

---

### SA-05 — Normalizar `period` en equipment cuando entra/sale de un plan

**Modelo:** `maintenance.equipment`. **Trigger:** AA-04 (write donde cambia `x_managed_by_plan`).

```python
for eq in records:
    if eq.x_managed_by_plan and eq.period > 0:
        eq.x_studio_period_backup = eq.period
        eq.period = 0
        eq.message_post(body=_(
            "period (%s días) respaldado y puesto a 0: gestionado por plan de punto."
        ) % eq.x_studio_period_backup)
    elif not eq.x_managed_by_plan and eq.period == 0 and eq.x_studio_period_backup:
        eq.period = eq.x_studio_period_backup
        eq.x_studio_period_backup = 0
        eq.message_post(body=_(
            "period restaurado a %s días: ya no es gestionado por plan."
        ) % eq.period)
```

---

### SA-06 — Edición manual de `scheduled_date` con propagación

**Trigger:** AA-05 (On Save Update donde cambia `scheduled_date`).

```python
for plan in records:
    if plan.state not in ('draft', 'scheduled'):
        continue
    hijas_vivas = plan.request_ids.filtered(lambda r: not r.stage_id.done)
    if hijas_vivas:
        old_dates = hijas_vivas.mapped('schedule_date')
        hijas_vivas.write({'schedule_date': plan.scheduled_date})
        plan.message_post(body=_(
            "scheduled_date editado manualmente por %s; %s hijas reprogramadas (antes: %s)."
        ) % (env.user.name, len(hijas_vivas), old_dates[0] if old_dates else '?'))
```

> Si querés un wizard de confirmación previo a guardar, transformá esta lógica en un Server Action invocado desde un botón "Aplicar nueva fecha" en lugar de un AA on-save.

---

### SA-MOV-00 — Inicialización de `x_equipment_movement` (name + company_id)

**Modelo:** `x_equipment_movement`. **Trigger:** AA-MOV-00 (On creation).

```python
for mov in records:
    vals = {}
    if not mov.name:
        seq = env['ir.sequence'].next_by_code('x_equipment_movement') or '0001'
        eq_name = mov.equipment_id.name or '?'
        year = mov.date_out.year if mov.date_out else datetime.date.today().year
        vals['name'] = f"MOV-{year}-{seq} / {eq_name}"
    if not mov.company_id and mov.equipment_id:
        vals['company_id'] = mov.equipment_id.company_id.id
    if vals:
        mov.write(vals)
```

> 💡 Cargá la secuencia: *Settings → Technical → Sequences → New*, code `x_equipment_movement`, prefix `MOV-`, padding 4.

---

### SA-09 — Auto-crear `x_equipment_movement` al cambiar `x_studio_location`

**Modelo:** `maintenance.equipment`. **Trigger:** AA-06 (On save update, watched: `x_studio_location`).

**Pieza clave de la integración con `pipeline_registro_II`**: cubre tanto los cambios que escribe el procesador existente (módulos R/I al mover equipos a 593/594/punto del trabajo) como cambios manuales desde Studio. Sin esta SA, los movimientos físicos del procesador no quedarían registrados en la bitácora `x_equipment_movement`. Ver Paso 12 para el detalle del mapeo `processor.py → reason`.

Infiere el `reason` del movement según el destino para que la consulta histórica tenga semántica útil:

```python
# Mapping de destino → reason. Los IDs 593/594 son hardcoded en processor.py.
LAB_LOC_ID = 593       # Laboratorio | Metrocal
STOCK_LOC_ID = 594     # Bodega cliente

for eq in records:
    # Evitar dobles disparos cuando un SA propio escriba con skip_auto_movement
    if env.context.get('skip_auto_movement'):
        continue

    # Último movement → from_location
    last = eq.movement_ids.sorted('date_out', reverse=True)[:1]
    last_to = last.to_location_id if last else False

    # Si la ubicación no cambió realmente, no hacer nada
    if last_to and last_to == eq.x_studio_location:
        continue

    # Inferir reason según el destino
    new_loc = eq.x_studio_location
    if not new_loc:
        reason = 'decommission'              # salió del sistema (raro; sin destino)
    elif new_loc.id == LAB_LOC_ID:
        reason = 'calibration'               # destino laboratorio Metrocal
    elif new_loc.id == STOCK_LOC_ID:
        reason = 'repair'                    # destino bodega (servicio/daño)
    elif last_to:
        reason = 'reassignment'              # cambio entre puntos
    else:
        reason = 'installation'              # primera asignación

    env['x_equipment_movement'].create({
        'equipment_id': eq.id,
        'from_location_id': last_to.id if last_to else False,
        'to_location_id': new_loc.id if new_loc else False,
        'reason': reason,
        'date_out': datetime.date.today(),
        'date_in': datetime.date.today(),
        'state': 'completed',
        'notes': _("Movement auto-generado por AA-06 (cambio de x_studio_location)."),
    })
```

> ⚠ Si en el futuro agregás una SA propia que también escriba `x_studio_location`, usá `eq.with_context(skip_auto_movement=True).write({'x_studio_location': …})` para no disparar SA-09 dos veces sobre el mismo cambio.

---

## 9. Paso 9 — Automated Actions (Automation Rules)

**Camino:** *Studio → Automations → New* (o *Settings → Technical → Automation Rules*).

> 📚 Ref: [Automation rules — Odoo 17](https://www.odoo.com/documentation/17.0/applications/studio/automated_actions.html). Triggers v17: `On save (creation)`, `On save (update)`, `On change`, `On deletion`, `Based on date field`, `On webhook`.

| ID | Modelo | Trigger | Trigger fields / domain | Acción |
|---|---|---|---|---|
| AA-00 | `x_maintenance_plan` | On save (creation) | — | Execute → SA-00 |
| AA-01 | `x_maintenance_plan` | On save (update) | Watched field: `state`. Before update domain: `[('state','!=','scheduled')]`. Apply on: `[('state','=','scheduled')]`. | Execute → SA-01 |
| AA-02 | `x_maintenance_plan` | On save (update) | Watched: `state`. Apply on: `[('state','in',('done','partially_done'))]`. | Execute → SA-02 (incluye chequeo de `contract_end_date`) |
| AA-03 | `x_maintenance_plan` | On save (update) | Watched: `scheduled_date`. Apply on: `[('state','in',('draft','scheduled'))]`. | Execute → SA-06 |
| AA-04 | `maintenance.equipment` | On save (update) | Watched: `x_managed_by_plan`. | Execute → SA-05 |
| AA-05 (opcional) | `x_maintenance_plan` | Based on date field | Trigger field: `scheduled_date`. Delay: 0 days. | Execute → SA-XX (notificación al técnico el día del trabajo) |
| AA-06 | `maintenance.equipment` | On save (update) | Watched: `x_studio_location`. Before update domain: `[]`. | Execute → SA-09 (auto-movement) |
| AA-MOV-00 | `x_equipment_movement` | On save (creation) | — | Execute → SA-MOV-00 (autogen name, company) |

> 💡 La diferencia entre **Before update domain** y **Apply on**:
> - *Before update domain*: condición evaluada con los valores **previos** al save.
> - *Apply on*: condición con los valores **nuevos**.
> Combinarlas evita disparos espurios (ej: para AA-01 solo querés disparar cuando *entra* a `scheduled`, no cuando ya estaba).

---

## 10. Paso 10 — Permisos y seguridad

### 10.1 Grupos a crear

*Settings → Technical → Security → Groups → New*:

| Nombre | Hereda de | Comentario |
|---|---|---|
| `Maintenance / Plan Manager` | Maintenance / Manager | CRUD completo sobre `x_maintenance_plan` y `x_equipment_movement`. |
| `Maintenance / Plan User` | Maintenance / User | Lectura de planes y movimientos; CRUD sobre sus hijas asignadas. |

### 10.2 Access Rights (`ir.model.access`)

*Settings → Technical → Security → Access Rights → New*. Para `x_maintenance_plan`:

| Grupo | read | write | create | unlink |
|---|---|---|---|---|
| Plan Manager | ✓ | ✓ | ✓ | ✓ |
| Plan User | ✓ | ✗ | ✗ | ✗ |

Para `x_equipment_movement`:

| Grupo | read | write | create | unlink |
|---|---|---|---|---|
| Plan Manager | ✓ | ✓ | ✓ | ✗ (auditoría: no borrar bitácora) |
| Plan User | ✓ | ✗ | ✗ | ✗ |

Para `maintenance.equipment`: no tocar (heredan de Maintenance). Idem `maintenance.request`.

### 10.3 Record Rules (multi-empresa)

*Settings → Technical → Security → Record Rules → New*. Sobre `x_maintenance_plan`:
- Name: "Plan: multi-company"
- Domain: `[('company_id', 'in', company_ids)]`
- Aplica a todos los grupos.

Sobre `x_equipment_movement`:
- Name: "Movement: multi-company"
- Domain: `[('company_id', 'in', company_ids)]`

---

## 11. Paso 11 — Checklist de testing manual

Probar en este orden, con un punto que tenga 3 equipos:

- [ ] **T-01** Crear plan en draft. → name autogenerado, series_id se completa, original_scheduled_date = scheduled_date.
- [ ] **T-02** Click "Sync con punto" en draft. → equipment_snapshot_ids se llena con los 3.
- [ ] **T-03** Cambiar state a `scheduled`. → se crean 3 `maintenance.request` con `plan_id` apuntando al plan, `schedule_date` = plan.scheduled_date.
- [ ] **T-04** Verificar en cada uno de los 3 equipos: `x_managed_by_plan = True`, `period = 0`, `x_studio_period_backup = period_original`.
- [ ] **T-05** Cerrar 3 hijas en stage "Repaired/Done". → `progress` = 100%.
- [ ] **T-06** Cerrar el plan dentro del slack (state → `done` con close_date = scheduled_date). → se crea next_plan_id con scheduled_date = scheduled_date + frequency.
- [ ] **T-07** Cerrar fuera del slack (close_date = scheduled_date + slack + 5 días). → next_plan_id.scheduled_date = close_date + frequency (cadencia deslizada).
- [ ] **T-08** Cerrar como `partially_done` con 1 hija pendiente y `force_close_reason` lleno. → carryover crea 1 hija extra en next_plan_id con `[CARRYOVER ...]` en el name.
- [ ] **T-09** Intentar guardar `partially_done` sin `force_close_reason`. → C-03 dispara ValidationError.
- [ ] **T-10** Crear segundo plan para el mismo punto con scheduled_date dentro del slack del primero. → C-04 dispara ValidationError.
- [ ] **T-11** Editar manualmente scheduled_date en un plan `scheduled`. → AA-03 propaga a hijas vivas + log en chatter.
- [ ] **T-12** Cancelar el plan padre. → state = cancelled, hijas archivadas, mensaje en chatter.
- [ ] **T-13** Borrar el punto. → restricción impide borrar si tiene planes (cambiar `ondelete` si no se desea).
- [ ] **T-14** Agregar un nuevo equipo al punto entre Paso T-03 y T-05. Sync con punto. → se crea 1 hija extra, `last_sync_with_location` se actualiza.
- [ ] **T-15** scheduled_date que caiga en domingo con `resource_calendar_id` cargado. → SA-02 desplaza al lunes hábil.

**Tests específicos de `contract_end_date`:**

- [ ] **T-16** Plan con `contract_end_date = scheduled_date + 2 meses`, frequency = 1 mes. Cerrar plan 1. → genera plan 2 (próximo mes). Cerrar plan 2. → genera plan 3 (mes siguiente). Cerrar plan 3. → **NO** genera plan 4; chatter loggea "Serie finalizada por término de contrato".
- [ ] **T-17** Cambiar `contract_end_date` a una fecha posterior en un plan existente → al copiar el siguiente debería heredar el nuevo valor. Verificar que `plan.copy(default=...)` propagó.

**Tests específicos de `x_equipment_movement` (Opción B):**

- [ ] **T-18** Equipo S1 en punto Norte → "Enviar a servicio externo" con reason=`calibration`, sin reemplazo. → se crea movement in_transit, `eq.x_in_external_service=True`, `eq.x_studio_location=False`, hija viva del plan archivada.
- [ ] **T-19** Mismo flujo pero con reemplazo S1-temp (que estaba en stock). → 2 movements creados (uno in_transit para S1, uno completed para S1-temp), S1-temp ahora en Norte, plan vivo tiene una hija nueva para S1-temp.
- [ ] **T-20** "Recibir de servicio externo" sobre S1 con destino = Norte (mismo origen), policy = `return_to_stock`. → movement S1 se cierra con `date_in=today` y `to_location_id=Norte`, S1-temp vuelve a stock con un movement reassignment, S1.x_studio_location = Norte.
- [ ] **T-21** "Recibir" con destino = punto Sur (distinto del origen). → además del cierre del movement original, se crea un 2º movement reason=`reassignment` para S1 (from=NULL, to=Sur). El plan del punto Norte recibe message_post "S1 no vuelve al punto".
- [ ] **T-22** Cambiar manualmente `x_studio_location` de un equipo desde el form. → AA-06 dispara SA-09 y crea un movement automáticamente con reason inferido (calibration / repair / installation / reassignment según destino).
- [ ] **T-23** Intentar borrar un movement (incluso como admin). → restringido por ACL (auditoría protegida).
- [ ] **T-24** Consulta "todas las sondas que pasaron por Norte en los últimos 90 días" desde la list view filtrada. → resultados consistentes con los movements creados.
- [ ] **T-25** Equipo en servicio externo + plan del punto pasa a `scheduled` → la SA-01 NO genera hija para ese equipo (filtrado por `x_in_external_service=False` en SA-01 — actualizar el dominio).

**Tests de integración con el pipeline existente (Paso 12):**

- [ ] **T-26** Correr `pipeline_registro_II/main.py` con un form R de calibración (alcance `Ciclo de calibración`, destino `Laboratorio | Metrocal`). Verificar que se creó `x_equipment_movement` con `reason='calibration'`, `to_location_id=593`. La SA del processor ya escribió la `maintenance.request` de Extracción/Calibración; el movement queda con `linked_request_id=NULL` (limitación documentada).
- [ ] **T-27** Form R de daño con destino `Bodega cliente` → movement con `reason='repair'`, `to_location_id=594`.
- [ ] **T-28** Form I (Instalación) con equipo nuevo a un punto → movement con `reason='installation'`, `to_location_id=punto`. Si el equipo ya estaba en otro punto, `reason='reassignment'`.
- [ ] **T-29** Re-ejecutar `main.py` con el mismo form: idempotencia del processor (`form_entries.db`) impide duplicar la request; AA-06 no se redispara porque `x_studio_location` no cambió.

---

## 12. Paso 12 — Integración con el pipeline existente (NO crear script puente)

> ✅ **Decisión confirmada:** Connecteam → Odoo **ya está implementado en producción** en `pipeline_registro_II/`. No se construye un script puente nuevo. La trazabilidad de movimientos se cierra desde Odoo con AA-06 + SA-09 (definidos en Pasos 8 y 9).

### 12.1 Por qué no hay script puente

El módulo R (Reemplazo/Extracción) de `pipeline_registro_II/processor.py` (líneas 1631–2913, documentado en `general_doc/processor_documentation.md` §8) ya cubre el ciclo completo:

- Polea Connecteam vía `main.py` por cron GitHub Actions (`0 11 * * 1-6` UTC).
- Resuelve equipos por serial (`maintenance.equipment`), valida puntos (`x_maintenance_location.x_name`).
- Bifurca por `alcance_R`: `Ciclo de calibración` (con sub-flujo Metrocal `team=2`, `tcnico=5118`) vs `Otro motivo` (daño / cambio).
- Itera subtipos E (sale) e I (entra), creando solicitudes `Extracción` / `Calibración` / `Instalación` (literales en `x_studio_tipo_de_trabajo`).
- **Mueve `x_studio_location`** del equipo a `593` (Laboratorio | Metrocal), `594` (Bodega cliente), o al punto del trabajo.
- Idempotencia robusta en `form_entries.db` (SQLite tabla `processed_entries`, commiteada por CI).
- Excepciones ruteadas a `x_inbox_integracion` con etiquetas y followers — patrón establecido (ver `general_doc/gestion_manual_inbox.md`).

### 12.2 Cómo se cierra la trazabilidad con la nueva entidad

**AA-06 (Paso 9)** escucha cambios en `maintenance.equipment.x_studio_location`. **SA-09 (Paso 8)** crea automáticamente el registro `x_equipment_movement` con el `reason` inferido según el destino:

| Origen del cambio en `x_studio_location` | Destino | `reason` inferido por SA-09 |
|---|---|---|
| `processor.py` módulo R · t=E · alcance=Calibración · destino Lab | `id 593` | `calibration` |
| `processor.py` módulo R · t=E · alcance=Otro · destino Bodega | `id 594` | `repair` |
| `processor.py` módulo R · t=I (equipo que entra) | punto del trabajo | `reassignment` (si tenía ubicación previa) o `installation` (primera vez) |
| `processor.py` módulo I · primera asignación | punto | `installation` |
| `processor.py` módulo I · cambio de punto | punto | `reassignment` |
| Edición manual en Odoo (Studio o admin) | cualquiera | inferido por las mismas reglas |

> **Resultado**: cero código nuevo en `pipeline_registro_II`. El pipeline sigue funcionando exactamente igual; lo único nuevo es que Odoo lleva ahora la bitácora `x_equipment_movement` en paralelo.

### 12.3 Limitación conocida y plan de mejora

`x_equipment_movement.linked_request_id` queda **NULL** en los movements generados por AA-06 desde el processor. Esto es porque AA-06 dispara *después* del `write()` y no tiene contexto de qué `maintenance.request` se acababa de crear en esa misma transacción.

Si en una iteración futura se necesita el linkeo (p. ej. para reportes que cruzan calibraciones con sus ubicaciones), opciones:

1. **Lado pipeline**: agregar en `pipeline_registro_II/` un módulo `equipment_movement_linker.py` que corra después de `main.py` y matchee movements sin link con requests por equipo + fecha cercana.
2. **Lado Odoo**: agregar a SA-09 una búsqueda heurística de la última request creada para ese equipo en los últimos N segundos.

Ambas son opcionales — la consulta "qué equipos pasaron por X punto" funciona sin el link.

### 12.4 Forms Connecteam

**No se crean forms nuevos**. El form actual ya tiene las preguntas necesarias para R (serial extracción + serial instalación + motivo + destino). Si al implementar se detectan campos faltantes para enriquecer `x_equipment_movement.notes` o `expected_return_date`, se agregan al form existente.

---

## 13. Apéndice A — Snippets reutilizables

### A.1 Filtro "stages done"
Maintenance no tiene una marca booleana fija en `maintenance.stage` (depende de la base). Usá:
```python
done_stages = env['maintenance.stage'].search([('done', '=', True)])
hijas_done = plan.request_ids.filtered(lambda r: r.stage_id in done_stages)
```
Si tu instancia no tiene el campo `done` en stage, agregalo via Studio o usá `kanban_state == 'done'` como proxy.

### A.2 Resource calendar fallback
```python
calendar = plan.resource_calendar_id or plan.company_id.resource_calendar_id
```

### A.3 Generar las próximas N ocurrencias (utilidad)
SA opcional sobre el plan; útil para visualizar la serie en calendar antes de ejecutarla.
```python
N = 12  # próximos 12 períodos
current = plan
for _ in range(N):
    if current.next_plan_id:
        current = current.next_plan_id
        continue
    next_date = add_period(current.scheduled_date, plan.frequency_value, plan.frequency_unit)
    new_plan = current.copy(default={
        'name': False, 'scheduled_date': next_date, 'state': 'draft',
        'previous_plan_id': current.id, 'next_plan_id': False,
        'series_id': plan.series_id, 'seq_in_series': current.seq_in_series + 1,
        'original_scheduled_date': next_date, 'close_date': False,
    })
    current.next_plan_id = new_plan.id
    current = new_plan
```

---

## 14. Apéndice B — Mapping rápido de campos

| Modelo | Campo | Tipo | Origen | Nota |
|---|---|---|---|---|
| `x_maintenance_plan` | `name` | char | nativo | autogenerado por SA-00 |
| ↑ | `location_id` | m2o → x_maintenance_location | nuevo | requerido |
| ↑ | `scheduled_date` | date | nuevo | requerido |
| ↑ | `original_scheduled_date` | date | nuevo | seteado por SA-00 |
| ↑ | `close_date` | date | nuevo | seteado por SA-02 |
| ↑ | `state` | selection | nuevo | 6 valores |
| ↑ | `frequency_value` / `frequency_unit` | int / sel | nuevo | — |
| ↑ | `slack_days` | int | nuevo | default 3 |
| ↑ | `auto_replan` | bool | nuevo | default True |
| ↑ | `series_id` | char | nuevo | uuid hex |
| ↑ | `previous_plan_id` / `next_plan_id` | m2o → self | nuevo | self-ref |
| ↑ | `seq_in_series` | int | nuevo | 1, 2, … |
| ↑ | `user_id` / `technician_user_id` / `maintenance_team_id` | m2o | nuevo (user_id nativo) | herencia a hijas |
| ↑ | `maintenance_type` | sel | nuevo | preventive/corrective |
| ↑ | `resource_calendar_id` | m2o → resource.calendar | nuevo | calendario laboral |
| ↑ | `equipment_snapshot_ids` | m2m → maintenance.equipment | nuevo | snapshot |
| ↑ | `last_sync_with_location` | datetime | nuevo | timestamp |
| ↑ | `progress` / `delta_days_from_planned` / `adjusted_from_scheduled` | computed | nuevo | read-only |
| ↑ | `force_close_reason` | text | nuevo | requerido si partially_done |
| ↑ | `notes` | text | nuevo | libre |
| ↑ | `contract_start_date` | date | nuevo | informativo |
| ↑ | `contract_end_date` | date | nuevo | **límite duro de la cascada**: corta la generación de ocurrencias |
| ↑ | `request_ids` | o2m → maintenance.request | nuevo | inverso plan_id |
| ↑ | `movement_ids` | o2m → x_equipment_movement | nuevo | inverso linked_plan_id |
| ↑ | `active` / `company_id` / chatter | varios | nativos features | — |
| `maintenance.equipment` | `x_managed_by_plan` | bool (computed, stored) | nuevo | dependencies en doc |
| ↑ | `x_studio_period_backup` | int | nuevo | respaldo del period nativo |
| ↑ | `x_in_external_service` | bool (computed, stored) | nuevo | True si tiene movement in_transit |
| ↑ | `x_current_replacement_id` | m2o → maintenance.equipment (computed) | nuevo | equipo que cubre el lugar |
| ↑ | `movement_ids` | o2m → x_equipment_movement | nuevo | inverso equipment_id |
| `maintenance.request` | `plan_id` | m2o → x_maintenance_plan | nuevo | indexed, ondelete=set null, tracked |
| `x_maintenance_location` | `plan_ids` | o2m → x_maintenance_plan | nuevo | inverso location_id |
| ↑ | `movement_out_ids` | o2m → x_equipment_movement | nuevo | inverso from_location_id |
| ↑ | `movement_in_ids` | o2m → x_equipment_movement | nuevo | inverso to_location_id |
| **`x_equipment_movement`** (NUEVO modelo) | `name` | char | nuevo | autogenerado `MOV-{YYYY}-{seq:04d} / {eq}` |
| ↑ | `equipment_id` | m2o → maintenance.equipment | nuevo | requerido, indexed, ondelete=restrict |
| ↑ | `from_location_id` / `to_location_id` | m2o → x_maintenance_location | nuevo | NULL admitido (stock/servicio) |
| ↑ | `reason` | selection | nuevo | installation·calibration·repair·reassignment·return_from_service·decommission |
| ↑ | `date_out` / `date_in` / `expected_return_date` | date | nuevo | date_in NULL = in_transit |
| ↑ | `state` | selection | nuevo | in_transit·completed·cancelled |
| ↑ | `replaced_by_id` | m2o → maintenance.equipment | nuevo | opcional |
| ↑ | `linked_request_id` | m2o → maintenance.request | nuevo | orden corrective asociada |
| ↑ | `linked_plan_id` | m2o → x_maintenance_plan | nuevo | plan de origen (ref débil) |
| ↑ | `duration_days` | int (computed) | nuevo | (date_in or today) − date_out |
| ↑ | `notes` / `company_id` | varios | nuevo | — |

---

## 15. Apéndice C — Referencias oficiales

- [Models, modules and apps — Odoo 17 Studio](https://www.odoo.com/documentation/17.0/applications/studio/models_modules_apps.html)
- [Fields and widgets — Odoo 17 Studio](https://www.odoo.com/documentation/17.0/applications/studio/fields.html)
- [Automation rules — Odoo 17](https://www.odoo.com/documentation/17.0/applications/studio/automated_actions.html)
- [Server Actions reference — Odoo 17 (`ir.actions.server`)](https://www.odoo.com/documentation/17.0/developer/reference/backend/actions.html)
- [Computed fields — Odoo 17 tutorial](https://www.odoo.com/documentation/17.0/developer/tutorials/getting_started/09_compute_onchange.html)
- [ORM API reference — Odoo 17](https://www.odoo.com/documentation/17.0/developer/reference/backend/orm.html)
- Diagrama ER de la propuesta: `propuesta_plan_punto.drawio` (este directorio).
- ER de los modelos existentes: `er_mantenciones.drawio`.
- Introspección cruda usada como verdad: `er_introspection.json`.

---

## 16. Apéndice D — Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Cascadas recursivas infinitas si un plan futuro ya estaba cerrado. | Guard `cascade_depth` en SA-02; tope de 10 niveles. |
| Studio compute sandbox bloquea `record.x_field = …`. | Usar `record['x_field'] = …` siempre (ya aplicado en snippets). |
| `equipment_snapshot_ids` puede divergir del punto si nadie sincroniza. | UI: badge "Snapshot desactualizado" si `last_sync_with_location < write_date` del punto. |
| Cancelación masiva archiva hijas; perdés métricas. | No usar `active=False`; mejor estado `cancelled` en hijas (requiere kanban_state custom). |
| `period=0` en equipos desactiva alertas nativas → si se desinstala el plan, hay que restaurar. | El backup en `x_studio_period_backup` lo permite. Documentar en runbook. |
| Solapamiento C-04 bloquea la cascada legítima. | SA-02 debe correr con `sudo()` y atrapar `ValidationError` para reportar a un usuario gestor en vez de revertir el cierre. |
| Cambios concurrentes en el padre y una hija. | Activar tracking en `plan_id` y `state` para tener el log; considerar lock pesimista vía `for_update()` solo si aparece en producción. |

---

**Fin del plan.** Cualquier ajuste antes de empezar a tipear en la instancia: revisalo contra `propuesta_plan_punto.drawio` y confirmá los 12 puntos del bloque "Notas de diseño" del diagrama (4 quedan como 🟡 pendientes).
