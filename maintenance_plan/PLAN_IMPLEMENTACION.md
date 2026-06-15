# Plan de Implementación — `x_maintenance_plan` (Mantención Preventiva por Punto)

> **Audiencia:** desarrollador / administrador funcional que va a construir la entidad directamente en Odoo Studio + Acciones Automatizadas + Acciones de Servidor.
> **Versión Odoo objetivo:** 16.0 (las rutas/menús corresponden a Studio 16 y al módulo **Automated Actions** / `base.automation`).
> **Diagrama de referencia:** `propuesta_plan_punto.drawio` (en este mismo directorio).
> **Tiempo estimado:** 4–6 horas en una instancia limpia; 1–2 días si se valida con datos reales.

---

## 0. Prerrequisitos

| # | Requisito                                                                                                                           | Verificación                                                                |
| - | ----------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| 1 | Módulo**Studio** instalado (acceso al ícono superior derecho).                                                              | Menú principal → Aplicaciones → "Studio".                                 |
| 2 | Módulo**Maintenance** instalado y con datos (equipos, requests).                                                             | Menú principal → Mantenimiento.                                            |
| 3 | Modelo Studio `x_maintenance_location` ya existe (verificado vía introspección).                                                | `er_introspection.json` lo confirma.                                       |
| 4 | Usuario con permisos de**Administrador Settings** + **Studio Manager**.                                                 | Settings → Users → tu usuario.                                             |
| 5 | **Snapshot / backup** de la base antes de empezar.                                                                            | Odoo Online: módulo Database Manager; on-premise:`pg_dump`.               |
| 6 | Módulo `base_automation` (se instala con Studio).                                                                                | Settings → Technical → Automation → Automated Actions debe ser accesible. |
| 7 | Acceso al menú**Settings → Technical → Server Actions** y **Settings → Technical → Database Structure → Models**. | Activá "Modo Desarrollador" (`?debug=1` en la URL o vía Settings).       |

> **Modo desarrollador obligatorio** durante toda la implementación. URL: agregá `?debug=1` o activá en *Settings → Developer Tools → Activate the developer mode*.

---

## 1. Hoja de ruta resumida

```
Paso 1   · Crear el modelo x_maintenance_plan en Studio           [Studio]
Paso 2   · Definir los 24 campos del modelo (incl. contrato)      [Studio]
Paso 3   · Crear el modelo x_equipment_movement                   [Studio]
Paso 4   · Tocar maintenance.equipment (1 campo nuevo)            [Studio]
Paso 5   · Tocar maintenance.request (1 campo nuevo)              [Studio]
Paso 6   · Diseñar vistas (form / list / kanban / calendar)       [Studio]
Paso 7   · Restricciones (constrains) vía Studio                  [Studio]
Paso 8   · Server Actions con código Python (SA-00 … SA-10)       [Technical]
Paso 9   · Automated Actions que disparan las SA (AA-00 … AA-13)  [Studio/Technical]
Paso 10  · Grupos de seguridad y reglas de registro              [Technical]
Paso 11  · Testing manual + checklist de aceptación              [Manual]
Paso 12  · Integración con pipeline_registro_II                   [Doc]
```

---

## 2. Paso 1 — Crear el modelo `x_maintenance_plan`

**Camino:** abrí cualquier vista del módulo Mantenimiento → click en el ícono **Studio** (esquina superior derecha) → en el panel izquierdo "Customizations" → **+ New Model**.

| Campo del wizard            | Valor                                                                                         |
| --------------------------- | --------------------------------------------------------------------------------------------- |
| Model Name                  | `Plan de Mantención Preventiva`                                                            |
| Technical Name (auto)       | `x_maintenance_plan`                                                                        |
| **Features a marcar** | Chatter · Archiving · User assignment · Date & Calendar · Custom Sorting · Company       |
| Features a NO marcar        | **Pipeline stages** · Tags · Picture · Lines · Notes · Monetary · Contact details |

> **Pipeline stages NO se marca.** Ese feature crea `stage_id` + `kanban_state` Studio: una segunda máquina de estados en paralelo al campo `state` (Paso 2) que gobierna todas las automatizaciones. Se desincronizan inevitablemente (arrastrar una card en kanban movería `stage_id` sin tocar `state` → ninguna AA dispara). Un solo ciclo de vida: `state`. El kanban se agrupa por `state`.

Los features marcados habilitan automáticamente:

- `x_active` (Archive) — usado para soft-delete.
- `x_studio_sequence` (Custom Sorting) — orden manual en listas.
- `x_name` — siempre presente (rec_name).
- `x_studio_user_id` — responsable del plan.
- `date` — Studio lo crea como `x_studio_date` (lo renombraremos al uso en Paso 2 o lo eliminaremos y crearemos `scheduled_date` propio).
- `company_id` — multi-empresa.
- chatter (`message_ids`, `message_follower_ids`, `activity_ids`) — auditoría obligatoria.

> Ref: [Models, modules and apps — Odoo 16 Studio](https://www.odoo.com/documentation/16.0/applications/studio/models_modules_apps.html)

**Al guardar**, Studio crea el módulo `studio_customization` que agrupa todo lo que sigue. Exportable al final desde *Studio → Customizations → Export*.

---

## 3. Paso 2 — Campos del modelo `x_maintenance_plan`

Trabajamos en *Studio → tu modelo nuevo → Form view*. Para cada campo: panel derecho **+ Field** → tipo → drag al canvas → configurar propiedades.

> **Convención de nombres — LEER ANTES DE PEGAR CUALQUIER SNIPPET.** En modelos creados por Studio **todo lleva prefijo**, incluidos los campos de features: el rec_name es **`x_name`** y el archivado **`x_active`** (verificado en `er_introspection.json`: `x_maintenance_location` tiene `x_name`/`x_active`, no `name`/`active`); los demás features y campos manuales salen como `x_studio_<nombre>` (`x_studio_user_id`, `x_studio_company_id`, `x_studio_state`, …). Los únicos sin prefijo son los heredados del chatter (`message_ids`, `activity_ids`, …). En esta guía los snippets usan los **nombres lógicos sin prefijo** por legibilidad: al pegar cada snippet o dominio, **transponé** (`name`→`x_name`, `active`→`x_active`, `state`→`x_studio_state`, `plan_id`→`x_studio_plan_id`, etc.). Verificá el nombre técnico real de cada campo en *Settings → Technical → Fields* después de crearlo. Los campos de modelos **core** (`maintenance.request.archive`, `maintenance.equipment.period`, `stage_id`, …) sí van sin prefijo, tal cual aparecen acá.

### 3.1 Identificación

* [X] 

| Campo           | Tipo                                  | Required     | Default              | Notas                                                                                                                                                                                                                                                                                                                                                    |
| --------------- | ------------------------------------- | ------------ | -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`        | char                                  | **No** | `'New'`            | nativo (`x_name`). **NO marcar Required**: la cascada (SA-02) crea la ocurrencia n+1 con name vacío y SA-00 lo completa *después* del insert — con required a nivel de campo el `create()` revienta antes de que la AA corra. La obligatoriedad efectiva la da SA-00, que siempre lo rellena. Pattern: `PMP-{YYYY}-{seq:04d}`.<br />Cam |
| `location_id` | many2one →`x_maintenance_location` | Sí          | —                   | `ondelete='restrict'` para no borrar un punto con planes vivos.                                                                                                                                                                                                                                                                                        |
| `company_id`  | many2one →`res.company`            | Sí          | `=user.company_id` | nativo (feature Company).                                                                                                                                                                                                                                                                                                                                |

### 3.2 Programación

* [X] 

| Campo                       | Tipo      | Required | Notas                                                                                                                             |
| --------------------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `scheduled_date`          | date      | Sí      | —                                                                                                                                |
| `original_scheduled_date` | date      | —       | escrito en `create()` vía SA-00. Solo lectura desde UI.                                                                        |
| `close_date`              | date      | —       | seteado por SA-02 al cerrar.                                                                                                      |
| `state`                   | selection | Sí      | Valores:`draft` · `scheduled` · `in_progress` · `done` · `partially_done` · `cancelled`. *Default:* `draft`. |

> En Studio el tipo *Selection* se configura desde el panel derecho → **Values** (formato `key:Label`).

### 3.3 Cadencia

* [X] 

| Campo               | Tipo      | Required | Notas                                                            |
| ------------------- | --------- | -------- | ---------------------------------------------------------------- |
| `frequency_value` | integer   | Sí      | default 1, validar > 0 (constrain en Paso 6).                    |
| `frequency_unit`  | selection | Sí      | `day` · `week` · `month` · `year`. default `month`. |
| `slack_days`      | integer   | —       | tolerancia ± en días. default 3.                               |
| `auto_replan`     | boolean   | —       | default `True`.                                                |

### 3.4 Serie (auto-referencia)

* [X] 

| Campo                | Tipo                              | Notas                                                             |
| -------------------- | --------------------------------- | ----------------------------------------------------------------- |
| `series_id`        | char                              | uuid generado en SA-00. Indexed = Sí (panel Field → "Indexed"). |
| `previous_plan_id` | many2one →`x_maintenance_plan` | `ondelete='set null'`.                                          |
| `next_plan_id`     | many2one →`x_maintenance_plan` | `ondelete='set null'`.                                          |
| `seq_in_series`    | integer                           | computado por SA-00; 1 para el primero de la serie.               |

### 3.5 Responsables (se heredan a hijas)

* [X] 

| Campo                   | Tipo                            | Notas                                                     |
| ----------------------- | ------------------------------- | --------------------------------------------------------- |
| `user_id`             | many2one →`res.users`        | nativo (feature User assignment) — responsable del plan. |
| `technician_user_id`  | many2one →`res.users`        | técnico por defecto.                                     |
| `maintenance_team_id` | many2one →`maintenance.team` | —                                                        |
| `maintenance_type`    | selection                       | `preventive` (default) · `corrective`.               |

### 3.6 Calendario laboral

* [X] 

| Campo                    | Tipo                             | Notas                                                                         |
| ------------------------ | -------------------------------- | ----------------------------------------------------------------------------- |
| `resource_calendar_id` | many2one →`resource.calendar` | default:`company_id.resource_calendar_id` (vía related compute o default). |

### 3.7 Snapshot de equipos

* [X] 

| Campo                       | Tipo                                  | Notas                                                                        |
| --------------------------- | ------------------------------------- | ---------------------------------------------------------------------------- |
| `equipment_snapshot_ids`  | many2many →`maintenance.equipment` | sin restricción de dominio en Studio; el dominio operativo lo aplica SA-01. |
| `last_sync_with_location` | datetime                              | timestamp del último wizard "Sync con punto".                               |

> Studio crea la tabla M2M con nombre automático tipo `x_maintenance_plan_maintenance_equipment_rel`. Anotalo: lo vas a usar en queries de auditoría.

### 3.8 Calculados (read-only)

* [X] 

| Campo                       | Tipo                                 | Dependencias                                    | Notas                                                                                       |
| --------------------------- | ------------------------------------ | ----------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `progress`                | integer                              | `request_ids`, `request_ids.stage_id.done`  | % hijas con `stage_id.done = True`.                                                       |
| `delta_days_from_planned` | integer                              | `close_date`, `scheduled_date`              | `close - scheduled` (en días).                                                           |
| `adjusted_from_scheduled` | boolean                              | `scheduled_date`, `original_scheduled_date` | True si difieren.                                                                           |
| `gantt_start`             | date (computed,**stored** Sí) | `scheduled_date`, `slack_days`              | `scheduled_date − slack_days`. La barra Gantt = ventana de tolerancia.                   |
| `gantt_stop`              | date (computed,**stored** Sí) | `scheduled_date`, `slack_days`              | `scheduled_date + slack_days`. Stored es obligatorio: la Gantt lee por search/read_group. |

> **Limitación de Studio en compute:** el sandbox bloquea `STORE_ATTR`. **No** uses `record.x_field = …`; usá la forma `for record in self: record['x_field'] = …`. Las dependencias se declaran en el campo "Dependencies" del panel derecho, separadas por coma. ([ref](https://medium.com/cybrosys/how-to-set-compute-function-for-field-using-odoo-17-studio-aa2ad46dd305))

**Snippet `progress`** (pegar en el field → Compute):

```python
for record in self:
    # Excluir hijas archivadas (extraídas a servicio externo / carryover):
    # no deben impedir que el plan llegue a 100%.
    vivas = record.request_ids.filtered(lambda r: not r.archive)
    total = len(vivas)
    if total:
        done = len(vivas.filtered(lambda r: r.stage_id.done))
        record['progress'] = int(round(100.0 * done / total))
    else:
        record['progress'] = 0
```

Dependencies: `request_ids,request_ids.stage_id.done,request_ids.archive`

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

**Snippet `gantt_start`** (análogo para `gantt_stop` cambiando `-` por `+`):

```python
for record in self:
    if record.scheduled_date:
        record['gantt_start'] = record.scheduled_date - datetime.timedelta(days=record.slack_days or 0)
    else:
        record['gantt_start'] = False
```

Dependencies: `scheduled_date,slack_days`

### 3.9 Operativos extra

| Campo                  | Tipo | Notas                                                            |
| ---------------------- | ---- | ---------------------------------------------------------------- |
| `force_close_reason` | text | requerido al pasar a `partially_done` (validación en Paso 6). |
| `notes`              | text | libre.                                                           |

### 3.10 Contrato (related — fuente única en `x_maintenance_location`)

> Los campos de contrato viven en `x_maintenance_location` (fuente única por punto/cliente). El plan los lee como **related store=True** para poder filtrar/indexar y para que el constraint de cascada sea performante.

**Crear en `x_maintenance_location` (sección 3.bis.6 más abajo):**

* [X] 

| Campo en location         | Tipo | Notas                                                             |
| ------------------------- | ---- | ----------------------------------------------------------------- |
| `x_contract_start_date` | date | informativo (inicio de servicio).                                 |
| `x_contract_end_date`   | date | **límite duro**: corta la cascada de los planes del punto. |

**Crear en `x_maintenance_plan` (esta sección):**

* [X] 

| Campo                   | Tipo                                | Related                               | Notas                                                                                                |
| ----------------------- | ----------------------------------- | ------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `contract_start_date` | date (related,**store=True**) | `location_id.x_contract_start_date` | indexed para reportes.                                                                               |
| `contract_end_date`   | date (related,**store=True**) | `location_id.x_contract_end_date`   | **límite duro**: la cascada NO genera ocurrencias con `scheduled_date > contract_end_date`. |

> En Studio 16 los related fields se configuran desde **+ Field → Related Field**. Marcar **Stored = Sí** es crítico: sin store, el related se evalúa en cada acceso y no puede usarse en dominios eficientes ni en constrains.
>
> **Cambio si se modifica el contrato en location**: el related almacenado se invalida automáticamente — el ORM recomputa al primer acceso o al próximo write. No requiere migración manual.
>
> **Comportamiento en cascada (SA-02):** después de calcular `next_date`, si `next_date > contract_end_date` (leído del related), se aborta la generación y se loggea `"Serie finalizada por término de contrato"` en el chatter. La serie muere sin tener que cancelarla manualmente.

> **Coexistencia con los campos de contrato de `maintenance.equipment`.** La base **ya tiene** `contract_start_date` / `contract_end_date` ("Fecha Inicio/Fin de Contrato") + `contract_dates_valid` a nivel de **equipo** (verificado en `er_introspection.json`). Ambos niveles conviven y significan cosas distintas — **no se migran ni se deprecan**:
>
> - Contrato del **punto** (`x_maintenance_location.x_contract_*`): gobierna la cascada del plan de mantención por punto.
> - Contrato del **equipo** (`maintenance.equipment.contract_*`): gobierna ciclos propios del instrumento bajo otra frecuencia (p. ej. calibraciones vía `period`/cron nativo), independiente del punto donde esté.
>
> Documentar en el form de equipment que sus fechas de contrato **no** cortan los planes del punto.

### 3.11 Inverso

| Campo            | Tipo                                                            | Notas                                                                   |
| ---------------- | --------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `request_ids`  | one2many →`maintenance.request`, inverse `plan_id`         | aparece una vez creado `plan_id` en `maintenance.request` (Paso 5). |
| `movement_ids` | one2many →`x_equipment_movement`, inverse `linked_plan_id` | trazabilidad de movimientos asociados al plan.                          |

---

## 3.bis Paso 3 — Crear el modelo `x_equipment_movement`

Esta entidad guarda la **bitácora de movimientos de equipos** (salidas a calibración, retornos, reasignaciones, bajas), de modo que el historial de ubicaciones de un equipo se obtiene con un `search_read` en vez de leer el chatter.

**Camino:** Studio → **+ New Model** → name: `Movimiento de Equipo` → technical: `x_equipment_movement`.

**Features a marcar:** Chatter · Company. *Nada más* (es un modelo simple de bitácora).

### 3.bis.1 Campos

* [X] 

| Campo                 | Tipo                             | Required | Notas                                                                                                                                                                                                                                                                                                                                                                                             |
| --------------------- | -------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`              | char                             | **No**  | rec_name (`x_name`). **NO marcar Required** (y si Studio lo dejó NOT NULL, quitalo en *Technical → Fields*): SA-MOV-00 llena el name **post-insert** vía AA-MOV-00 (*On Creation*); con required, el `INSERT` con `x_name=NULL` revienta en Postgres (`NotNullViolation`) antes de que la AA corra — y **SA-09** también crea movements sin name, así que en runtime fallaría igual. Mismo caso que `x_maintenance_plan` §3.1. Default `'New'`. Autogenerado por SA-MOV-00: `MOV-{YYYY}-{seq:04d} / {equipment.name}`. Secuencia `x_equipment_movement`.                                                                                                                                                                                                                                                                                       |
| `equipment_id`      | m2o →`maintenance.equipment`  | Sí      | indexed.`ondelete='restrict'` (no se borra un equipo con historial).                                                                                                                                                                                                                                                                                                                            |
| `from_location_id`  | m2o →`x_maintenance_location` | —       | NULL = venía de stock / equipo nuevo.                                                                                                                                                                                                                                                                                                                                                            |
| `to_location_id`    | m2o →`x_maintenance_location` | —       | NULL = sale a stock / servicio externo / baja.                                                                                                                                                                                                                                                                                                                                                    |
| `reason`            | selection                        | Sí      | `installation` · `calibration` · `repair` · `reassignment` · `return_from_service` · `decommission`.                                                                                                                                                                                                                                                                             |
| `date_out`          | date                             | Sí      | default `today`.                                                                                                                                                                                                                                                                                                                                                                                |
| `date_in`           | date                             | —       | fecha de llegada al destino. SA-09 la setea `= date_out`: el cambio de ubicación se registra como **hecho consumado**, no como tránsito abierto.                                                                                                                                                                                                                                        |
| `replaced_by_id`    | m2o →`maintenance.equipment`  | —       | equipo que ocupó el lugar (anotación manual opcional).                                                                                                                                                                                                                                                                                                                                          |
| `linked_request_id` | m2o →`maintenance.request`    | —       | orden de calibración/reparación asociada.                                                                                                                                                                                                                                                                                                                                                       |
| `linked_plan_id`    | m2o →`x_maintenance_plan`     | —       | plan de origen (referencia débil, no FK fuerte).                                                                                                                                                                                                                                                                                                                                                 |
| `state`             | selection                        | Sí      | `completed` · `cancelled`. Default `completed`. **No existe estado `in_transit`**: el movement es una bitácora de hechos consumados. La estadía en Laboratorio (593) o Bodega cliente (594) se lee directamente de `x_studio_location` del equipo — mientras esté ahí, simplemente *no está en ningún punto* y por lo tanto queda fuera de los snapshots de los planes. |
| `notes`             | text                             | —       | libre.                                                                                                                                                                                                                                                                                                                                                                                            |
| `company_id`        | m2o →`res.company`            | Sí      | heredado de `equipment_id.company_id` (default compute).                                                                                                                                                                                                                                                                                                                                        |

**Snippet default `company_id`** (en el field → Default Value):

```python
equipment_id and equipment_id.company_id or env.company
```

### 3.bis.2 Inversos a crear en otros modelos

* [X] 

| Modelo                     | Campo                | Tipo                                                              |
| -------------------------- | -------------------- | ----------------------------------------------------------------- |
| `maintenance.equipment`  | `movement_ids`     | one2many →`x_equipment_movement`, inverse `equipment_id`     |
| `x_maintenance_location` | `movement_out_ids` | one2many →`x_equipment_movement`, inverse `from_location_id` |
| `x_maintenance_location` | `movement_in_ids`  | one2many →`x_equipment_movement`, inverse `to_location_id`   |

### 3.bis.3 Vista form sugerida

- Header: `state` como statusbar.
- 2 columnas:
  - Izq: `equipment_id`, `from_location_id` → `to_location_id` (mismo renglón visual), `reason`, `replaced_by_id`.
  - Der: `date_out`, `date_in`, `linked_request_id`, `linked_plan_id`.
- Notes al final.

### 3.bis.4 Vista list (la importante para auditoría)

Columnas: `equipment_id`, `date_out`, `from_location_id`, `to_location_id`, `reason`, `state`, `linked_request_id`.

Default order: `date_out desc`.

**Filtros y agrupaciones:**

- Filter "En servicio externo": se consulta sobre **equipment**, no sobre movements: `[('x_studio_location','in',(593,594))]` en la list de equipos.
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

### 3.bis.5-bis Seed inicial de la bitácora (paso obligatorio de go-live)

SA-09 infiere `from_location_id` del **último movement** del equipo. Con la bitácora vacía, el primer write de cada equipo generaría un movement `installation` espurio (aunque solo se haya editado una nota) y el historial previo sería invisible. **Antes de activar AA-06**, correr un script one-shot (shell de Odoo o Server Action manual) que cree el movement inicial por equipo:

> **Excluí Bodega cliente (594).** Es la ubicación **default al crear un equipo**: significa "stock / no instalado", no una posición real en un punto. Sembrar un `installation → 594` sería falso (el equipo no está instalado en ningún lado) y además mal-etiquetaría su primer traslado real como `return_from_service`. Estos equipos **no se seedean**: SA-09 los cubre con un **baseline implícito de 594** (sin movement = está en stock), de modo que su primer movimiento real sale correctamente como `installation` desde `from=NULL`. **Sí** se seedean los equipos en puntos reales y los que estén en Laboratorio (593) al go-live — su ubicación previa NO es el baseline 594, así que necesitan el movement semilla.

> El seed setea el `name` **explícitamente** (no lo deja en NULL): así funciona aunque AA-MOV-00 todavía no esté activa, y aunque por error `x_name` siguiera siendo NOT NULL. Si AA-MOV-00 ya está activa, SA-MOV-00 ve el name puesto y se saltea (chequea `if not mov.name`) — no hay doble nombrado.

```python
STOCK_LOC_ID = 594   # Bodega cliente = ubicación default / stock
for eq in env['maintenance.equipment'].search([
    ('x_studio_location', '!=', False),
    ('x_studio_location', '!=', STOCK_LOC_ID),
]):
    seed_date = eq.effective_date or datetime.date.today()
    seq = env['ir.sequence'].next_by_code('x_equipment_movement') or '0001'
    env['x_equipment_movement'].create({
        'name': f"MOV-{seed_date.year}-{seq} / {eq.name or '?'}",
        'equipment_id': eq.id,
        'to_location_id': eq.x_studio_location.id,
        'reason': 'installation',
        'date_out': seed_date,
        'date_in': seed_date,
        'state': 'completed',
        'notes': 'Seed inicial de bitácora (go-live).',
    })
```

### 3.bis.6 Cambios complementarios en `x_maintenance_location`

**Camino:** Studio → seleccioná cualquier punto → ícono Studio → **Form view** → **+ Field**.

* [X] 

| Campo                     | Tipo                                                      | Required | Notas                                                                                         |
| ------------------------- | --------------------------------------------------------- | -------- | --------------------------------------------------------------------------------------------- |
| `x_contract_start_date` | date                                                      | —       | inicio del contrato de servicio con el cliente.                                               |
| `x_contract_end_date`   | date                                                      | —       | **fin del contrato — corta la generación de planes futuros**. Tracking Sí (chatter). |
| `plan_ids`              | one2many →`x_maintenance_plan` (inv `location_id`)   | —       | inverso — habilita la lista de planes en el form del punto.                                  |
| `movement_out_ids`      | o2m →`x_equipment_movement` (inv `from_location_id`) | —       | inverso.                                                                                      |
| `movement_in_ids`       | o2m →`x_equipment_movement` (inv `to_location_id`)   | —       | inverso.                                                                                      |

**Form view del punto** (sugerencia): tab "Contrato" con `x_contract_start_date`, `x_contract_end_date` + tab "Planes" con `plan_ids` (list embebida) + tab "Historial de equipos" con `movement_out_ids` y `movement_in_ids` unidos en una vista combinada.

> Si cambiás `x_contract_end_date` para acortar el contrato y ya existen planes futuros generados más allá de la nueva fecha, **no se cancelan automáticamente**. Considerá una SA-12 manual "Recalcular serie por cambio de contrato" o un constraint que avise.

---

## 4. Paso 4 — Cambios en `maintenance.equipment`

**Camino:** Studio → seleccioná un equipo → ícono Studio → **Form view** → **+ Field**.

| Campo                      | Tipo                       | Propiedades                                                                                                                                                                                         |
| -------------------------- | -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `x_managed_by_plan`      | boolean (computed, stored) | Compute: ver snippet abajo. Dependencies:`x_studio_location,x_studio_location.plan_ids.state,x_studio_location.plan_ids.active`. **Stored = Sí** (necesario para filtros). Readonly = Sí. **Solo informativo** (badge/filtros). |

> **Dos ciclos de mantención sobre el equipo.** El `period` nativo no se modifica. El cron nativo de Maintenance genera las hijas **propias del equipo** (p. ej. calibración del instrumento) con `plan_id = False`; el plan del punto genera sus hijas con `plan_id` seteado. Son trabajos distintos que conviven sin interferir:
>
> - `progress`, la cascada y C-05 operan sobre `request_ids` (inverso de `plan_id`), por lo que ignoran las hijas nativas.
> - Para distinguirlas en kanban/lista, las hijas nativas se etiquetan vía **AA-13 → SA-10** (Pasos 8 y 9): si `plan_id` es False y `maintenance_type='preventive'`, se estampa `x_studio_tipo_de_trabajo = 'Mantención del Equipo'`.

> **No hay campo "en servicio externo".** Un equipo está en servicio externo cuando su `x_studio_location` es Laboratorio (593) o Bodega cliente (594) — es un dato derivable por dominio (`[('x_studio_location','in',(593,594))]`), no necesita campo propio. Al no estar en ningún punto, queda automáticamente fuera de los snapshots de los planes (SA-01/SA-03 buscan por `x_studio_location = punto`).

**Snippet compute `x_managed_by_plan`:**

```python
# partially_done NO cuenta: es estado terminal (dispara cascada, igual que done).
# La ocurrencia siguiente (draft) es la que mantiene el True.
ACTIVE_STATES = ('draft', 'scheduled', 'in_progress')
for record in self:
    plans = record.x_studio_location.plan_ids.filtered(
        lambda p: p.active and p.state in ACTIVE_STATES
    ) if record.x_studio_location else False
    record['x_managed_by_plan'] = bool(plans)
```

> **`x_managed_by_plan` es informativo, no disparador.** Se usa para el badge del form y para filtros. Al ser computed **stored**, su recomputación se escribe vía `_write` durante el flush y no pasa por `write()` (que es lo que `base_automation` parchea en 16), por lo que no debe usarse como disparador de Automated Actions.

> `plan_ids` es el **inverso** que tenés que crear sobre `x_maintenance_location`: campo one2many → `x_maintenance_plan`, inverse `location_id`. Hacelo ahora — *Studio → x_maintenance_location → + Field*.

**UX:** agregá en la cabecera del Form view de equipment:

- Badge "Gestionado por plan PMP-XXX" si `x_managed_by_plan = True`.
- El estado "en servicio externo" **no necesita badge propio**: el propio campo `x_studio_location` mostrando "Laboratorio | Metrocal" o "Bodega cliente" ya lo comunica. El pipeline existente (`processor.py`) gestiona los flujos de calibración/reemplazo desde Connecteam moviendo ese campo (ver Paso 12), y SA-09 deja la bitácora.

Adicionalmente, agregá en el form de equipment un **tab "Historial de movimientos"** con el campo `movement_ids` como lista embebida (columnas: `date_out`, `from_location_id`, `to_location_id`, `reason`, `state`). Esto da timeline inmediata por equipo.

---

## 5. Paso 5 — Cambios en `maintenance.request`

* [X] 

| Campo       | Tipo                              | Propiedades                                                                                                                                                                                                       |
| ----------- | --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `plan_id` | many2one →`x_maintenance_plan` | nombre real:**`x_studio_plan_id`** (transponer en todos los snippets/dominios de esta guía). `ondelete='set null'` (la baja del padre no borra trazabilidad). Indexed = Sí. Tracking = Sí (Chatter). |

Adicionalmente, abrí el **Form view** de `maintenance.request` y agregá `plan_id` arriba del bloque de programación, en modo readonly cuando el campo viene autogenerado:

```xml
<field name="plan_id" attrs="{'readonly': [('plan_id', '!=', False)]}"/>
```

(Studio te lo deja editar en modo visual; el `attrs` lo pegás desde el editor XML del campo → menú "Edit XML".)

---

## 6. Paso 6 — Vistas

> **Recomendación:** dejá las vistas para después de probar las Server Actions con datos cargados a mano. Las vistas se iteran rápido en Studio; la lógica no.

### Form view (`x_maintenance_plan`)

- Header: `state` como statusbar (botones `scheduled`, `in_progress`, `done`, `partially_done`, `cancelled` en ese orden) + botón **"Proyectar serie"** (Trigger Server Action → SA-07).
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

### Gantt view (visualización global del plan — pieza central junto a SA-07)

> Requiere Enterprise; si tenés Studio, la tenés. En Studio: *Views → + Gantt*.

- **Date start:** `gantt_start` · **Date stop:** `gantt_stop` → cada barra representa la **ventana de tolerancia** `scheduled_date ± slack_days` de una ocurrencia.
- **Default group by:** `location_id` → una fila por punto, con la serie completa del contrato como secuencia de barras (pre-generada con el botón "Proyectar serie" / SA-07).
- **Color:** `state` (draft = proyectada, scheduled/in_progress = comprometida, done = cerrada, cancelled = recortada por contrato).
- Escala por defecto: mes; rango año para ver el contrato completo.
- Las barras **no son arrastrables**: `gantt_start/gantt_stop` son computed stored sin inverse — un drag fallaría. Es deliberado: la fecha se cambia editando `scheduled_date` en el form (AA-03 → SA-06 propaga), o la mueve la cascada. Documentáselo a los usuarios.

---

## 7. Paso 7 — Restricciones (validaciones de modelo)

En Odoo 16 **no existe un trigger "Before save"**: todas las automated actions disparan *después* de guardar. Para validaciones que **bloqueen el guardado**, cada restricción se implementa como una **Server Action "Execute Python Code"** (modelo `x_maintenance_plan`) que hace `raise UserError(...)` — el raise revierte la transacción completa —, disparada por una **Automated Action con trigger "On Creation & Update"** (ver AA-07…AA-12 en el Paso 9). Crealas como `SA-C01`…`SA-C06` junto al resto de las Server Actions del Paso 8.

> **Sandbox 16:** `ValidationError` y `_` (traducción) **no** están en el contexto de evaluación. Usá `raise UserError("...")` con strings planos. `UserError`, `Warning`, `Command`, `datetime`, `dateutil` y `float_compare` **sí** están disponibles. En una Server Action el recordset disparado es `records` (y `model` para `search`).

### C-01 (SA-C01) — frequency_value > 0

```python
for record in records:
    if record.frequency_value <= 0:
        raise UserError("La frecuencia debe ser mayor a 0.")
```

### C-02 (SA-C02) — slack_days debe ser menor que la MITAD del período base

```python
UNIT_DAYS = {'day': 1, 'week': 7, 'month': 30, 'year': 365}
for record in records:
    period_days = record.frequency_value * UNIT_DAYS.get(record.frequency_unit, 30)
    if record.slack_days * 2 >= period_days:
        raise UserError(
            "slack_days (%s) debe ser menor que la mitad del período base (%s días): "
            "si no, las ventanas ±slack de dos ocurrencias consecutivas se solapan "
            "y la cascada chocaría contra C-04."
            % (record.slack_days, period_days))
```

> El factor `* 2`: dos ocurrencias separadas por `período` tienen ventanas `[d−slack, d+slack]` que se intersectan cuando `período < 2·slack`. Por eso `slack_days` debe ser menor que la mitad del período base; de lo contrario las ventanas de dos ocurrencias consecutivas se solapan y C-04 bloquea la generación de n+1.

### C-03 (SA-C03) — `force_close_reason` requerido si state='partially_done'

```python
for record in records:
    if record.state == 'partially_done' and not (record.force_close_reason or '').strip():
        raise UserError(
            "Para cerrar como ‘partially_done’ debe registrar el motivo en force_close_reason.")
```

### C-04 (SA-C04) — No solapamiento de planes activos en el mismo punto

```python
# Las escrituras de la cascada (SA-02) viajan con x_skip_c04=True en el
# contexto: la cadencia intra-serie ya la garantiza C-02 y un cierre legítimo
# no debe quedar bloqueado por su propia generación de n+1. El contexto del
# write/create se propaga a la Automated Action que ejecuta esta SA.
if not env.context.get('x_skip_c04'):
    ACTIVE = ('draft', 'scheduled', 'in_progress')
    for record in records:
        if record.state not in ACTIVE or not record.scheduled_date:
            continue
        window_start = record.scheduled_date - datetime.timedelta(days=record.slack_days)
        window_end   = record.scheduled_date + datetime.timedelta(days=record.slack_days)
        overlap = model.search([
            ('id', '!=', record.id),
            ('series_id', '!=', record.series_id),   # excluir la propia serie
            ('location_id', '=', record.location_id.id),
            ('state', 'in', ACTIVE),
            ('scheduled_date', '<=', window_end),
            ('scheduled_date', '>=', window_start),
        ])
        if overlap:
            raise UserError(
                "Solapamiento con plan %s (programado %s)."
                % (overlap[0].name, overlap[0].scheduled_date))
```

> C-04 valida el solapamiento **solo entre series distintas**: excluye la propia serie (la cadencia intra-serie la garantiza C-02 con `2·slack < período`). Su función es impedir que dos series distintas compitan por el mismo punto.

> Las escrituras de la cascada (SA-02) viajan con `x_skip_c04=True` en el contexto y C-04 las omite; cualquier creación o edición manual se valida completa.

### C-05 (SA-C05) — `done` exige todas las hijas resueltas

```python
# Sin esto, un usuario puede marcar 'done' con hijas pendientes y se pierden
# silenciosamente: el carryover solo corre en 'partially_done'.
for record in records:
    if record.state != 'done':
        continue
    pendientes = record.request_ids.filtered(
        lambda r: not r.stage_id.done and not r.archive)
    if pendientes:
        raise UserError(
            "No se puede cerrar como 'done' con %s hijas pendientes. "
            "Complete las hijas, o cierre como 'partially_done' con motivo: "
            "las pendientes se arrastran como carryover a la siguiente ocurrencia."
            % len(pendientes))
```

### C-06 (SA-C06) — No archivar un plan vivo

```python
# El archivado (x_active=False) saltea SA-04 y dejaría las hijas vivas
# huérfanas (sin archivar) y la cadena de la serie sin puentear. Única puerta
# de salida de un plan vivo: cancelarlo (SA-04 archiva hijas y puentea la
# cadena). Ya cancelado/cerrado, archivar es libre.
for record in records:
    if not record.active and record.state in ('draft', 'scheduled', 'in_progress'):
        raise UserError(
            "No se puede archivar un plan vivo (%s está en '%s'). "
            "Cancelalo primero: la cancelación archiva las hijas y puentea la "
            "serie. Después podés archivarlo."
            % (record.name, record.state))
```

---

## 8. Paso 8 — Server Actions

**Camino:** *Settings → Technical → Server Actions → New*. Para cada SA: **Model = x_maintenance_plan** salvo cuando se indique otro modelo (SA-09 es sobre `maintenance.equipment`; SA-MOV-00 sobre `x_equipment_movement`); **Type = Execute Python Code**.

> Ref: [Server Actions reference — Odoo 16](https://www.odoo.com/documentation/16.0/developer/reference/backend/actions.html)
>
> **Variables disponibles en el sandbox 16** (verificado en `ir_actions.py` rama 16.0, [doc](https://www.odoo.com/documentation/16.0/applications/studio/automated_actions.html)):
> `env, model, record, records, uid, user, time, datetime, dateutil, timezone, float_compare, b64encode, b64decode, log(), Warning, UserError, Command, action`
> **NO disponibles:** `_` (traducción), `ValidationError` ni `_logger`. Usá strings planos, `raise UserError(...)` y `log(...)`. **No uses `import`** (safe_eval lo bloquea salvo un whitelist mínimo): `datetime`, `dateutil`, `time` ya vienen como variables.
>
> **`STORE_ATTR` prohibido (igual que en los computes):** el sandbox bloquea la asignación directa de atributos `registro.campo = valor` (lanza `forbidden opcode(s) ... STORE_ATTR`). Para escribir un campo usá **`registro.write({'campo': valor})`** (escribe varios de una) o la forma subíndice `registro['campo'] = valor` (usa `STORE_SUBSCR`, permitido). Esto aplica a TODAS las SA: ya está reflejado en SA-01, SA-02, SA-03 y SA-07.

---

### SA-00 — Inicialización en `create()` (series_id, original_scheduled_date, name)

**Trigger:** se invoca desde la AA-00 (On creation).

```python

```

> Cargá **dos** secuencias en *Settings → Technical → Sequences → New*: (1) code `x_maintenance_plan`, **sin prefijo** (solo padding 4) — el `PMP-` ya lo agrega SA-00 en el formato del name (`f"PMP-{year}-{seq}"`); si la secuencia **también** lleva prefix `PMP-`, el nombre sale duplicado: `PMP-2026-PMP-0003`; (2) code `x_maintenance_plan_series`, sin prefijo, padding 6 (identificador de serie — reemplaza al `uuid` que el sandbox de 16 no permite importar).

---

### SA-01 — Generar hijas al pasar a `scheduled`

**Trigger:** AA-01 (state cambia a `scheduled`).

```python
for plan in records:
    # 1) Snapshot del punto si todavía está vacío.
    #    Los equipos en servicio externo (Lab 593 / Bodega 594) quedan fuera
    #    solos: su x_studio_location ya no es el punto.
    #    company 'in (False, id)': no excluir equipos compartidos sin company.
    if not plan.equipment_snapshot_ids:
        equipos = env['maintenance.equipment'].search([
            ('x_studio_location', '=', plan.location_id.id),
            ('active', '=', True),
            ('company_id', 'in', (False, plan.company_id.id)),
        ])
        # .write() en vez de asignación directa: el sandbox prohíbe STORE_ATTR
        plan.write({
            'equipment_snapshot_ids': [Command.set(equipos.ids)],
            'last_sync_with_location': datetime.datetime.now(),
        })

    # schedule_date de la hija es DATETIME: anclar a las 12:00 UTC.
    # Medianoche UTC se mostraría como el día ANTERIOR a las 20:00/21:00
    # en America/Santiago — el plan entero parecería corrido un día.
    sched_dt = datetime.datetime.combine(plan.scheduled_date, datetime.time(12, 0))

    # 2) Crear una maintenance.request por cada equipo del snapshot que aún no tenga hija
    existentes = plan.request_ids.mapped('equipment_id')
    nuevos = plan.equipment_snapshot_ids - existentes
    for equipo in nuevos:
        env['maintenance.request'].create({
            'name': f"{plan.name} - {equipo.name}",
            'equipment_id': equipo.id,
            'plan_id': plan.id,
            'stage_id': 1,
            'schedule_date': sched_dt,
            'maintenance_type': plan.maintenance_type or 'preventive',
            'user_id': (plan.technician_user_id or plan.user_id).id or False,
            'maintenance_team_id': plan.maintenance_team_id.id or False,
            'x_studio_tipo_de_trabajo': 'Mantención Preventiva',
        })

    # NOTA: el period nativo NO se toca. El equipo conserva su ciclo propio
    # (cron nativo → hijas con plan_id=False), que coexiste con las hijas del
    # plan (plan_id seteado). Son dos trabajos distintos; ver Paso 4.

    plan.message_post(
        body="Generadas %s solicitudes hijas a partir del snapshot del punto." % len(nuevos),
    )
```

---

### SA-02 — Cascada al cerrar (`done` / `partially_done`)

**Trigger:** AA-02 (state pasa a `done` o `partially_done`).

```python
UNIT = {'day': 'days', 'week': 'weeks', 'month': 'days', 'year': 'days'}
def add_period(base, value, unit):
    # week/day directos; month/year usan dateutil para ser precisos
    if unit == 'day':
        return base + datetime.timedelta(days=value)
    if unit == 'week':
        return base + datetime.timedelta(weeks=value)
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
        plan.write({'close_date': datetime.date.today()})   # .write(): el sandbox prohíbe STORE_ATTR

    # 1) Calcular próxima fecha base
    delta_days = (plan.close_date - plan.scheduled_date).days
    within_slack = abs(delta_days) <= plan.slack_days
    base_for_next = plan.scheduled_date if within_slack else plan.close_date
    next_date = add_period(base_for_next, plan.frequency_value, plan.frequency_unit)

    # 2) Ajuste por calendario laboral
    next_date = shift_to_workday(next_date, plan.resource_calendar_id)

    # 3) LÍMITE DURO POR TÉRMINO DE CONTRATO
    if plan.contract_end_date and next_date > plan.contract_end_date:
        # La serie muere: no se genera la próxima ocurrencia. El period nativo
        # del equipo NO se toca (su ciclo propio sigue corriendo, ver Paso 4).
        plan.message_post(body=(
            "Serie %s finalizada por término de contrato (%s). "
            "No se generará la próxima ocurrencia (next_date hubiera sido %s)."
        ) % (plan.series_id, plan.contract_end_date, next_date))
        continue   # salta a la próxima iteración del for plan in records

    # 4) Aplicar a la siguiente ocurrencia (recursivo)
    if plan.auto_replan:
        nxt = plan.next_plan_id
        if nxt and nxt.state in ('draft', 'scheduled'):
            old = nxt.scheduled_date
            # x_skip_c04: las escrituras de la cascada viajan con este flag de
            # contexto para que SA-C04 (no solapamiento) no bloquee el cierre.
            # La propagación a las hijas vivas de nxt NO se hace acá: el write
            # dispara AA-03 → SA-06, que la hace de forma autofiltrada.
            nxt.with_context(x_skip_c04=True).write({'scheduled_date': next_date})
            nxt.message_post(body=(
                "Fecha reprogramada por cascada desde %s: %s → %s"
            ) % (plan.name, old, next_date))
            # NO se re-ejecuta la cascada sobre nxt: cuando nxt cierre, AA-02
            # disparará SA-02 sobre él de forma natural. (La re-entrada vía
            # env.ref se eliminó: además habría fallado — las SAs creadas a
            # mano no tienen XML-ID de un módulo propio.)

            # 4-bis) Re-fechar EN BLOQUE la cola pre-generada por SA-07.
            # Sin esto, un cierre fuera de slack solo movería a n+1 y la
            # frecuencia entre n+1 y n+2 quedaría rota. Cada eslabón =
            # anterior + período; lo que el deslizamiento empuje más allá
            # del contrato se cancela.
            prev = nxt
            cur = nxt.next_plan_id
            guard = 0
            while cur and cur.state in ('draft', 'scheduled') and guard < 60:
                new_date = add_period(prev.scheduled_date,
                                      prev.frequency_value, prev.frequency_unit)
                new_date = shift_to_workday(new_date, prev.resource_calendar_id)
                if plan.contract_end_date and new_date > plan.contract_end_date:
                    cur.with_context(x_skip_c04=True).write({'state': 'cancelled'})
                    cur.message_post(body=(
                        "Ocurrencia proyectada cancelada: el deslizamiento de la "
                        "serie superó el fin de contrato (%s)."
                    ) % plan.contract_end_date)
                elif cur.scheduled_date != new_date:
                    # AA-03 → SA-06 propaga a hijas vivas si las hubiera
                    cur.with_context(x_skip_c04=True).write({'scheduled_date': new_date})
                prev = cur
                cur = cur.next_plan_id
                guard += 1
        elif not nxt:
            # 5) Generar la siguiente ocurrencia (hereda contract_start/end)
            new_plan = plan.with_context(x_skip_c04=True).copy(default={
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
            plan.write({'next_plan_id': new_plan.id})   # .write(): el sandbox prohíbe STORE_ATTR

    # 6) Carryover si cerró parcial
    if plan.state == 'partially_done' and plan.next_plan_id:
        pendientes = plan.request_ids.filtered(lambda r: not r.stage_id.done and not r.archive)
        carry_dt = datetime.datetime.combine(plan.next_plan_id.scheduled_date, datetime.time(12, 0))
        for hija in pendientes:
            env['maintenance.request'].create({
                'name': f"[CARRYOVER] {hija.name}",   # hija.name ya incluye el nombre del plan; no repetirlo
                'equipment_id': hija.equipment_id.id,
                'plan_id': plan.next_plan_id.id,
                'schedule_date': carry_dt,
                'maintenance_type': hija.maintenance_type,
                'user_id': hija.user_id.id or False,
                'maintenance_team_id': hija.maintenance_team_id.id or False,
                'company_id': hija.company_id.id,
                'description': "Arrastrada desde %s (no completada)." % plan.name,
            })
        # Archivar las originales: no dejar DOS órdenes vivas por el mismo trabajo.
        # La trazabilidad queda en el plan cerrado (request_ids las conserva).
        pendientes.write({'archive': True})
        plan.message_post(body=(
            "%s solicitudes arrastradas como carryover al siguiente plan (originales archivadas)."
        ) % len(pendientes))
```

> La cascada **no** se re-ejecuta sobre planes futuros: cada ocurrencia dispara su propia cascada al cerrar (AA-02). El paso 4-bis solo *re-fecha* la cola pre-generada (writes planos, sin recursión); el `guard < 60` es un tope de iteración alineado con el `MAX_OCC` de SA-07, no un guard de recursión.

---

### SA-03 — Wizard "Sync con punto"

**Trigger:** botón en el form view del plan (botón hecho desde Studio → "Add Button" → "Trigger Server Action" → SA-03).

```python
for plan in records:
    if plan.state not in ('draft', 'scheduled'):
        raise UserError("Solo se puede sincronizar planes en draft o scheduled.")

    equipos_punto = env['maintenance.equipment'].search([
        ('x_studio_location', '=', plan.location_id.id),
        ('active', '=', True),
        ('company_id', 'in', (False, plan.company_id.id)),
    ])

    en_snapshot = plan.equipment_snapshot_ids
    faltantes = equipos_punto - en_snapshot
    sobrantes = en_snapshot - equipos_punto

    # .write() en vez de asignación directa: el sandbox prohíbe STORE_ATTR
    plan.write({
        'equipment_snapshot_ids': [Command.set(equipos_punto.ids)],
        'last_sync_with_location': datetime.datetime.now(),
    })

    # Crear hijas para los faltantes si el plan ya está scheduled.
    # Misma receta que SA-01: datetime anclado 12:00 UTC + herencia de
    # responsables/equipo/tipo.
    if plan.state == 'scheduled':
        sched_dt = datetime.datetime.combine(plan.scheduled_date, datetime.time(12, 0))
        for equipo in faltantes:
            env['maintenance.request'].create({
                'name': f"{plan.name} - {equipo.name}",
                'equipment_id': equipo.id,
                'plan_id': plan.id,
                'schedule_date': sched_dt,
                'maintenance_type': plan.maintenance_type or 'preventive',
                'user_id': (plan.technician_user_id or plan.user_id).id or False,
                'maintenance_team_id': plan.maintenance_team_id.id or False,
                'company_id': plan.company_id.id,
            })

    # Las hijas de los sobrantes no se borran: se loggean
    plan.message_post(body=(
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

    # Puentear la cadena si se cancela una ocurrencia INTERMEDIA de una serie
    # proyectada (SA-07): sin esto, la cascada del anterior encontraría un
    # next_plan_id cancelado y la serie quedaría trabada.
    if plan.previous_plan_id and plan.next_plan_id:
        plan.previous_plan_id.write({'next_plan_id': plan.next_plan_id.id})
        plan.next_plan_id.write({'previous_plan_id': plan.previous_plan_id.id})
        plan.message_post(body=(
            "Cadena puenteada: %s → %s (esta ocurrencia queda fuera de la serie activa)."
        ) % (plan.previous_plan_id.name, plan.next_plan_id.name))

    # El period nativo del equipo NO se toca: su ciclo propio sigue corriendo
    # independientemente de que el plan del punto se cancele (ver Paso 4).

    plan.message_post(body=(
        "Plan cancelado. %s hijas archivadas. "
        "La serie continúa desde el último plan ‘done’."
    ) % len(hijas_vivas))
```

> Para la confirmación: definí esta SA con `binding_model_id = x_maintenance_plan` y `binding_view_types = form`, y al disparar abrí un wizard transitorio que pida confirmación. Si no querés crear el wizard, configurá la AA con un `confirm` JS-side desde el form view button.

---

### SA-06 — Propagación de `scheduled_date` a las hijas (autofiltrada)

**Trigger:** AA-03 (On Update sobre el plan). En 16 dispara ante **cualquier** write de un plan en draft/scheduled (no hay watched fields), por eso el guard: solo actúa sobre hijas cuya fecha difiere de la del plan. Esto también la convierte en el único punto de propagación — la cascada (SA-02) escribe `scheduled_date` en n+1 y deja que esta SA haga el resto.

```python
for plan in records:
    if plan.state not in ('draft', 'scheduled') or not plan.scheduled_date:
        continue
    # datetime anclado a 12:00 UTC (ver SA-01)
    target = datetime.datetime.combine(plan.scheduled_date, datetime.time(12, 0))
    # Guard anti-spam: si las fechas ya coinciden (write de notas, responsable,
    # etc.), no escribir ni loggear nada.
    hijas_desfasadas = plan.request_ids.filtered(
        lambda r: not r.stage_id.done and not r.archive and r.schedule_date != target
    )
    if hijas_desfasadas:
        hijas_desfasadas.write({'schedule_date': target})
        plan.message_post(body=(
            "scheduled_date del plan aplicado a %s hijas vivas (nueva fecha: %s; write de %s)."
        ) % (len(hijas_desfasadas), plan.scheduled_date, env.user.name))
```

> Si querés un wizard de confirmación previo a guardar, transformá esta lógica en un Server Action invocado desde un botón "Aplicar nueva fecha" en lugar de un AA on-save.

---

### SA-07 — Proyectar serie (pre-generar ocurrencias futuras para la Gantt)

**Trigger:** botón "Proyectar serie" en el form del plan (Studio → "Add Button" → "Trigger Server Action" → SA-07). No lleva AA: es una acción deliberada del gestor.

**Propósito:** poblar la serie hacia el futuro como planes padre en `draft` — **sin hijas y sin snapshot** — para que la carta Gantt muestre el plan global del contrato. Las hijas de cada ocurrencia nacen recién cuando esa ocurrencia pasa a `scheduled` (SA-01), contra el estado real del punto en ese momento. La cascada (SA-02) ya contempla la cadena pre-generada: al cerrar cada ocurrencia *re-fecha* la cola completa en vez de crear planes nuevos.

**Horizonte:** hasta `contract_end_date` si el punto tiene contrato cargado; si no, 12 ocurrencias. Tope duro de seguridad: 60 (evita runaway con frecuencias diarias).

```python
MAX_OCC = 60

def add_period(base, value, unit):
    if unit == 'day':
        return base + datetime.timedelta(days=value)
    if unit == 'week':
        return base + datetime.timedelta(weeks=value)
    if unit == 'month':
        return base + dateutil.relativedelta.relativedelta(months=value)
    if unit == 'year':
        return base + dateutil.relativedelta.relativedelta(years=value)
    return base

def shift_to_workday(date, calendar):
    if not calendar:
        return date
    dt = datetime.datetime.combine(date, datetime.time(8, 0))
    next_dt = calendar.plan_days(1, dt, compute_leaves=True)
    return next_dt.date() if next_dt else date

for plan in records:
    if not plan.auto_replan:
        raise UserError(
            "La serie %s tiene auto_replan desactivado: activalo antes de proyectar."
            % plan.name)

    # 1) Caminar hasta el último eslabón de la serie (el botón puede
    #    clickearse desde cualquier ocurrencia).
    current = plan
    guard = 0
    while current.next_plan_id and guard < MAX_OCC:
        current = current.next_plan_id
        guard += 1

    # 2) Generar hacia adelante hasta el horizonte.
    horizon = plan.contract_end_date
    limit = MAX_OCC if horizon else 12
    creadas = 0
    while creadas < limit:
        next_date = add_period(current.scheduled_date,
                               current.frequency_value, current.frequency_unit)
        next_date = shift_to_workday(next_date, current.resource_calendar_id)
        if horizon and next_date > horizon:
            break   # serie completa hasta fin de contrato
        new_plan = current.with_context(x_skip_c04=True).copy(default={
            'name': False,                     # SA-00 le pondrá uno nuevo
            'scheduled_date': next_date,
            'state': 'draft',
            'close_date': False,
            'previous_plan_id': current.id,
            'next_plan_id': False,
            'series_id': current.series_id,
            'seq_in_series': current.seq_in_series + 1,
            'original_scheduled_date': next_date,
            'equipment_snapshot_ids': [Command.clear()],
            'force_close_reason': False,
        })
        current.write({'next_plan_id': new_plan.id})   # .write(): el sandbox prohíbe STORE_ATTR
        current = new_plan
        creadas += 1

    plan.message_post(body=(
        "Proyección de serie %s: %s ocurrencias nuevas (horizonte: %s)."
    ) % (plan.series_id, creadas,
         horizon or "12 ocurrencias por defecto"))
```

> **Idempotente:** re-ejecutar el botón no duplica nada — camina hasta el final de la cadena existente y solo completa lo que falte hasta el horizonte. Si la serie ya llega a `contract_end_date`, genera 0 y lo dice en el chatter.
>
> **Las fechas proyectadas son teóricas** (cadencia ideal desde la última ocurrencia). Cuando la realidad se imponga — un cierre fuera de slack — SA-02 re-fecha la cola completa en bloque, y las ocurrencias que el deslizamiento empuje más allá del contrato se cancelan solas (ver paso 4-bis de SA-02).

---

### SA-MOV-00 — Inicialización de `x_equipment_movement` (name + company_id)

**Modelo:** `x_equipment_movement`. **Trigger:** AA-MOV-00 (On Creation).

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

> Cargá la secuencia: *Settings → Technical → Sequences → New*, code `x_equipment_movement`, prefix `MOV-`, padding 4.

---

### SA-09 — Auto-crear `x_equipment_movement` al cambiar `x_studio_location`

**Modelo:** `maintenance.equipment`. **Trigger:** AA-06 (On Update — en 16 dispara ante cualquier write; la SA filtra comparando el último movement, ver nota de AA-06 en el Paso 9).

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

    # Último movement → from_location. Ordenar por (date_out, id) desc: date_out
    # es granularidad DÍA y casi todos nacen con date_out=hoy, así que a igualdad
    # de fecha hay que desempatar por id (monótono) o el [:1] toma el más viejo
    # del día y el guard / from_location_id quedan mal.
    last = eq.movement_ids.sorted(key=lambda m: (m.date_out, m.id), reverse=True)[:1]
    last_to = last.to_location_id if last else False

    # Baseline implícito: los equipos sin seed son los que están en Bodega
    # cliente (594), la ubicación default = "stock" (sección 3.bis.5-bis). Sin
    # movement previo, su ubicación anterior efectiva es 594 — así un write que
    # NO cambia la ubicación (editar una nota estando en bodega) no dispara un
    # movement 594→594 espurio. El from_location real sigue siendo NULL (abajo),
    # de modo que el primer traslado real sale como 'installation' desde stock.
    prev_loc_id = last_to.id if last_to else STOCK_LOC_ID
    cur_loc_id  = eq.x_studio_location.id if eq.x_studio_location else False

    # Si la ubicación no cambió realmente, no hacer nada
    if prev_loc_id == cur_loc_id:
        continue

    # Inferir reason según origen y destino
    new_loc = eq.x_studio_location
    if not new_loc:
        reason = 'decommission'              # salió del sistema (raro; sin destino)
    elif new_loc.id == LAB_LOC_ID:
        reason = 'calibration'               # destino laboratorio Metrocal
    elif new_loc.id == STOCK_LOC_ID:
        reason = 'repair'                    # destino bodega (servicio/daño)
    elif last_to and last_to.id in (LAB_LOC_ID, STOCK_LOC_ID):
        reason = 'return_from_service'       # vuelve de Lab/Bodega a un punto
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
        'notes': "Movement auto-generado por AA-06 (cambio de x_studio_location).",
    })

    # El period nativo del equipo NO se toca al reubicar: su ciclo propio sigue
    # corriendo donde sea que esté. SA-09 solo registra la bitácora de movimientos.
```

> Si en el futuro agregás una SA propia que también escriba `x_studio_location`, usá `eq.with_context(skip_auto_movement=True).write({'x_studio_location': …})` para no disparar SA-09 dos veces sobre el mismo cambio.

> **SA-09 reconstruye la ubicación anterior desde la bitácora** (una SA *On Update* en Studio 16 no puede leer el valor viejo de `x_studio_location`). Para que funcione correctamente deben sostenerse tres condiciones: (1) **orden monótono** del "último movement" por `(date_out, id)` desc; (2) **seed inicial** de la bitácora antes de activar AA-06 (sección 3.bis.5-bis), excepto los equipos en Bodega cliente (594), que quedan sin seed y cubiertos por el baseline de 594 del guard; (3) **bitácora append-only** (la ACL bloquea `unlink` salvo Plan Manager — Paso 10). Si la bitácora se desincroniza (un move con `skip_auto_movement`, un `create` fallido, o un movement editado/borrado), `from_location_id` y el guard quedan desfasados a partir de ese punto.

---

### SA-10 — Etiquetar las hijas propias del equipo (ciclo nativo)

**Modelo:** `maintenance.request`. **Trigger:** AA-13 (On Creation).

**Propósito:** las dos corrientes de hijas (plan del punto vs ciclo propio del equipo) ya quedan distinguidas en los datos por `plan_id`, pero el cron nativo crea sus requests con un tipo genérico. Esta SA las etiqueta para que en kanban/lista no se confundan con las del plan. Las del plan ya nacen con `x_studio_tipo_de_trabajo = 'Mantención Preventiva'` desde SA-01, así que no se tocan.

```python
for req in records:
    # Solo las hijas NATIVAS (sin plan) y preventivas, que aún no tengan tipo.
    if not req.plan_id and req.maintenance_type == 'preventive' \
            and not (req.x_studio_tipo_de_trabajo or '').strip():
        req.write({'x_studio_tipo_de_trabajo': 'Mantención del Equipo'})
```

> Ajustá el literal `'Mantención del Equipo'` al valor que uses en tu campo `x_studio_tipo_de_trabajo`. Si el campo es selection, usá la `key` correspondiente.

---

## 9. Paso 9 — Automated Actions

**Camino:** *Studio → Automations → New* (o *Settings → Technical → Automation → Automated Actions*).

> Ref: [Automated actions — Odoo 16](https://www.odoo.com/documentation/16.0/applications/studio/automated_actions.html). Triggers en 16: `On Creation`, `On Update`, `On Creation & Update`, `On Deletion`, `Based on Form Modification`, `Based on Timed Condition`. **No existe trigger de webhook en 16.**
>
> **Diferencia clave con 17:** en 16 el trigger `On Update` **no tiene "Watched field"** — dispara ante *cualquier* write del registro. Se acota declarativamente con **"Before Update Domain"** (`filter_pre_domain`, evaluado sobre los valores **previos**) + **"Apply on"** (`filter_domain`, valores **nuevos**), ambos presentes en 16. Cuando no alcanza, la propia Server Action filtra (ej. SA-09 compara el último movement).

| ID               | Modelo                    | Trigger (16)             | Before Update Domain / Apply on                                                                                                                 | Acción                                                                                                      |
| ---------------- | ------------------------- | ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| AA-00            | `x_maintenance_plan`    | On Creation              | —                                                                                                                                              | Execute → SA-00                                                                                             |
| AA-01            | `x_maintenance_plan`    | On Update                | Before Update:`[('state','!=','scheduled')]` · Apply on: `[('state','=','scheduled')]`                                                     | Execute → SA-01                                                                                             |
| AA-02            | `x_maintenance_plan`    | On Update                | Before Update:`[('state','not in',('done','partially_done'))]` · Apply on: `[('state','in',('done','partially_done'))]`                    | Execute → SA-02 (incluye chequeo de `contract_end_date`)                                                  |
| AA-03            | `x_maintenance_plan`    | On Update                | Apply on:`[('state','in',('draft','scheduled'))]` (dispara en cada write; SA-06 se autofiltra: solo escribe si la fecha de las hijas difiere) | Execute → SA-06                                                                                             |
| AA-05 (opcional) | `x_maintenance_plan`    | Based on Timed Condition | Trigger Date:`scheduled_date`. Delay: 0 días.                                                                                                | Execute → SA-XX (notificación al técnico el día del trabajo)                                             |
| AA-06            | `maintenance.equipment` | On Update                | — (en 16 dispara en cada write; SA-09 compara el último movement y sale si la ubicación no cambió)                                          | Execute → SA-09 (registra la bitácora de movimientos)                                                     |
| AA-MOV-00        | `x_equipment_movement`  | On Creation              | —                                                                                                                                              | Execute → SA-MOV-00 (autogen name, company)                                                                 |
| AA-07            | `x_maintenance_plan`    | On Creation & Update     | —                                                                                                                                              | Execute → SA-C01 (`frequency_value > 0`)                                                                  |
| AA-08            | `x_maintenance_plan`    | On Creation & Update     | —                                                                                                                                              | Execute → SA-C02 (`slack_days` < período base)                                                           |
| AA-09            | `x_maintenance_plan`    | On Creation & Update     | Apply on:`[('state','=','partially_done')]`                                                                                                   | Execute → SA-C03 (`force_close_reason` requerido)                                                         |
| AA-10            | `x_maintenance_plan`    | On Creation & Update     | Apply on:`[('state','in',('draft','scheduled','in_progress'))]`                                                                               | Execute → SA-C04 (no solapamiento; se salta si el contexto trae `x_skip_c04` — escrituras de la cascada) |
| AA-11            | `x_maintenance_plan`    | On Update                | Apply on:`[('state','=','done')]`                                                                                                             | Execute → SA-C05 (`done` exige hijas resueltas)                                                           |
| AA-12            | `x_maintenance_plan`    | On Update                | Apply on:`[('active','=',False)]`                                                                                                             | Execute → SA-C06 (no archivar plan vivo)                                                                    |
| AA-13            | `maintenance.request`   | On Creation              | Apply on:`[('plan_id','=',False),('maintenance_type','=','preventive')]`                                                                      | Execute → SA-10 (etiqueta las hijas propias del equipo / ciclo nativo)                                       |

> **Orden de ejecución:** cuando varias AAs disparan sobre el mismo write, corren por su campo `sequence`. Asigná **sequence bajo a las validaciones** (AA-07…AA-12, p. ej. 1–6) y más alto a las de negocio (AA-01/AA-02/AA-03, p. ej. 10+): si una validación va a revertir todo, mejor que reviente *antes* de que la cascada haya creado registros — el resultado es el mismo (rollback), pero el debugging es mucho más claro.

> La diferencia entre **Before Update Domain** y **Apply on**:
>
> - *Before Update Domain*: condición evaluada con los valores **previos** al save (solo aplica a `On Update`).
> - *Apply on*: condición con los valores **nuevos** (aplica a `On Update` y `On Creation & Update`).
>   Combinarlas evita disparos espurios (ej: para AA-01 solo querés disparar cuando *entra* a `scheduled`, no cuando ya estaba).
>
> **AA-07…AA-12 (validaciones).** En 16 reemplazan a los constraints "Before save" inexistentes: ejecutan SA-C01…SA-C06 con `raise UserError(...)`. El raise revierte la transacción, bloqueando el guardado igual que un `@api.constrains`.

---

## 10. Paso 10 — Permisos y seguridad

### 10.1 Grupos a crear

*Settings → Technical → Security → Groups → New*:

| Nombre                         | Hereda de             | Comentario                                                             |
| ------------------------------ | --------------------- | ---------------------------------------------------------------------- |
| `Maintenance / Plan Manager` | Maintenance / Manager | CRUD completo sobre `x_maintenance_plan` y `x_equipment_movement`. |
| `Maintenance / Plan User`    | Maintenance / User    | Lectura de planes y movimientos; CRUD sobre sus hijas asignadas.       |

### 10.2 Access Rights (`ir.model.access`)

*Settings → Technical → Security → Access Rights → New*. Para `x_maintenance_plan`:

| Grupo        | read | write | create | unlink |
| ------------ | ---- | ----- | ------ | ------ |
| Plan Manager | Yes  | Yes   | Yes    | Yes    |
| Plan User    | Yes  | No    | No     | No     |

Para `x_equipment_movement`:

| Grupo                        | read | write | create        | unlink                               |
| ---------------------------- | ---- | ----- | ------------- | ------------------------------------ |
| Plan Manager                 | Yes  | Yes   | Yes           | No (auditoría: no borrar bitácora) |
| Plan User                    | Yes  | No    | Yes           | No                                   |
| **Maintenance / User** | Yes  | No    | **Yes** | No                                   |

> **Maintenance/User requiere `create` sobre movements.** Las Server Actions disparadas por Automated Actions corren **como el usuario que hizo el write**. AA-06 → SA-09 crea un `x_equipment_movement` cada vez que se cambia `x_studio_location` de un equipo, incluido el write XML-RPC de `pipeline_registro_II`. Sin permiso de create, la AA lanza `AccessError` y revierte el write completo. El usuario API que usa `pipeline_registro_II` debe estar en *Maintenance / User* (o tener el ACL directo). `write`/`unlink` quedan cerrados: la bitácora es append-only salvo para Plan Manager.
>
> Nota de alcance: las ACLs no aplican al superusuario (`admin`/OdooBot bypasea `ir.model.access`) — la prohibición de unlink protege contra usuarios normales, no contra el admin.

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
- [ ] **T-04** Verificar en cada uno de los 3 equipos: `x_managed_by_plan = True` y que el `period` nativo **sigue intacto** (no se toca). Si el equipo tenía `period > 0`, el cron nativo debe seguir generando sus hijas propias (`plan_id = False`) en paralelo a las del plan.
- [ ] **T-05** Cerrar 3 hijas en stage "Repaired/Done". → `progress` = 100%.
- [ ] **T-06** Cerrar el plan dentro del slack (state → `done` con close_date = scheduled_date). → se crea next_plan_id con scheduled_date = scheduled_date + frequency.
- [ ] **T-07** Cerrar fuera del slack (close_date = scheduled_date + slack + 5 días). → next_plan_id.scheduled_date = close_date + frequency (cadencia deslizada).
- [ ] **T-08** Cerrar como `partially_done` con 1 hija pendiente y `force_close_reason` lleno. → carryover crea 1 hija extra en next_plan_id con `[CARRYOVER ...]` en el name.
- [ ] **T-09** Intentar guardar `partially_done` sin `force_close_reason`. → SA-C03 (AA-09) dispara UserError y bloquea el guardado.
- [ ] **T-09b** Intentar cerrar como `done` con 1 hija pendiente. → SA-C05 (AA-11) dispara UserError: o se completan las hijas o se cierra `partially_done`.
- [ ] **T-10** Crear segundo plan para el mismo punto con scheduled_date dentro del slack del primero. → SA-C04 (AA-10) dispara UserError.
- [ ] **T-11** Editar manualmente scheduled_date en un plan `scheduled`. → AA-03 propaga a hijas vivas + log en chatter.
- [ ] **T-12** Cancelar el plan padre. → state = cancelled, hijas archivadas, cadena puenteada, mensaje en chatter. El `period` nativo de los equipos **no cambia** (sigue corriendo su ciclo propio).
- [ ] **T-12b** Intentar archivar (`active = False`) un plan `scheduled`. → SA-C06 (AA-12) bloquea con UserError. Tras cancelarlo (T-12), archivar sí funciona.
- [ ] **T-13** Borrar el punto. → restricción impide borrar si tiene planes (cambiar `ondelete` si no se desea).
- [ ] **T-14** Agregar un nuevo equipo al punto entre Paso T-03 y T-05. Sync con punto. → se crea 1 hija extra, `last_sync_with_location` se actualiza.
- [ ] **T-15** scheduled_date que caiga en domingo con `resource_calendar_id` cargado. → SA-02 desplaza al lunes hábil.

**Tests específicos de `contract_end_date`:**

- [ ] **T-16** Plan con `contract_end_date = scheduled_date + 2 meses`, frequency = 1 mes. Cerrar plan 1. → genera plan 2 (próximo mes). Cerrar plan 2. → genera plan 3 (mes siguiente). Cerrar plan 3. → **NO** genera plan 4; chatter loggea "Serie finalizada por término de contrato".
- [ ] **T-17** Cambiar `contract_end_date` a una fecha posterior en un plan existente → al copiar el siguiente debería heredar el nuevo valor. Verificar que `plan.copy(default=...)` propagó.

**Tests específicos de `x_equipment_movement`:**

- [ ] **T-18** Equipo S1 en punto Norte → cambiar `x_studio_location` a Laboratorio (593). → AA-06/SA-09 crea movement `completed` con `from=Norte`, `to=Lab`, `reason='calibration'`, `date_in=date_out=today`. El `period` del equipo **no cambia**.
- [ ] **T-19** S1 vuelve del Lab al punto Norte (con plan activo). → movement `reason='return_from_service'`. El `period` del equipo **no cambia**.
- [ ] **T-20** S1 se mueve de Norte a un punto Sur **sin** plan activo. → movement `reason='reassignment'`. El `period` del equipo **no cambia**.
- [ ] **T-20b** Equipo con `period > 0` dentro de un plan: el cron nativo genera una hija `plan_id=False`. → AA-13/SA-10 le estampa `x_studio_tipo_de_trabajo='Mantención del Equipo'`; el `progress` del plan **no se altera** y cerrarla no dispara cascada.
- [ ] **T-21** Quitar `x_studio_location` de un equipo (baja). → movement `reason='decommission'` con `to=NULL`.
- [ ] **T-22** Cambiar manualmente `x_studio_location` desde el form (como Plan User o Maintenance User). → AA-06 dispara SA-09 sin AccessError (ACL de create verificada) y el reason se infiere según destino.
- [ ] **T-23** Intentar borrar un movement como Plan Manager o Plan User. → bloqueado por ACL. (El superusuario admin bypasea ACLs — esta protección no aplica para él.)
- [ ] **T-24** Consulta "todas las sondas que pasaron por Norte en los últimos 90 días" desde la list view filtrada. → resultados consistentes con los movements creados.
- [ ] **T-25** Equipo con `x_studio_location = Lab (593)` + plan de su punto de origen pasa a `scheduled`. → SA-01 NO le genera hija: ya no está en el punto, queda fuera del snapshot naturalmente.
- [ ] **T-25b** Equipo recién creado en **Bodega cliente (594)** (default), **sin** seed. Editar cualquier campo NO-ubicación (p. ej. una nota). → SA-09 **NO** crea ningún movement (baseline implícito 594 == 594). No aparece un `594→594 'repair'` espurio.
- [ ] **T-25c** Ese mismo equipo de 594 se mueve por primera vez a un punto real. → SA-09 crea movement con `from=NULL`, `to=punto`, `reason='installation'` (no `return_from_service`). Confirma que el primer traslado desde stock se etiqueta como instalación.

**Tests de proyección de serie (SA-07) y Gantt:**

- [ ] **T-30** Plan 1 `scheduled`, `contract_end_date = +6 meses`, frequency = 1 mes. Click "Proyectar serie". → se crean ~5 ocurrencias `draft` encadenadas (`previous/next_plan_id`, `seq_in_series` correlativo, mismo `series_id`), **sin hijas y sin snapshot**, ninguna después del fin de contrato. La Gantt agrupada por punto muestra la serie completa como barras `±slack`.
- [ ] **T-31** Re-click en "Proyectar serie" (desde cualquier ocurrencia de la serie). → idempotente: 0 ocurrencias nuevas, mensaje en chatter.
- [ ] **T-32** Cerrar plan 1 **fuera del slack** (close_date = scheduled + slack + 10). → SA-02 re-fecha n+1 desde `close_date` y el paso 4-bis desliza **toda la cola** en bloque; las ocurrencias empujadas más allá de `contract_end_date` quedan `cancelled` con log en chatter.
- [ ] **T-33** Cerrar plan 1 **dentro del slack**. → la cola no se mueve (las fechas recalculadas coinciden y el guard `!=` evita writes).
- [ ] **T-34** Plan sin `contract_end_date`. → "Proyectar serie" genera exactamente 12 ocurrencias.
- [ ] **T-35** Pasar a `scheduled` una ocurrencia proyectada. → SA-01 toma el snapshot del punto recién ahí y genera las hijas con los equipos presentes en ese momento.
- [ ] **T-36** Cancelar una ocurrencia **intermedia** de la cadena proyectada (SA-04). → la cadena se puentea (`prev.next_plan_id` salta a la siguiente); al cerrar la ocurrencia anterior, la cascada re-fecha la cola sin trabarse.

**Tests de integración con el pipeline existente (Paso 12):**

- [ ] **T-26** Correr `pipeline_registro_II/main.py` con un form R de calibración (alcance `Ciclo de calibración`, destino `Laboratorio | Metrocal`). Verificar que se creó `x_equipment_movement` con `reason='calibration'`, `to_location_id=593`. La SA del processor ya escribió la `maintenance.request` de Extracción/Calibración; el movement queda con `linked_request_id=NULL` (limitación documentada).
- [ ] **T-27** Form R de daño con destino `Bodega cliente` → movement con `reason='repair'`, `to_location_id=594`.
- [ ] **T-28** Form I (Instalación) con equipo nuevo a un punto → movement con `reason='installation'`, `to_location_id=punto`. Si el equipo ya estaba en otro punto, `reason='reassignment'`.
- [ ] **T-29** Re-ejecutar `main.py` con el mismo form: idempotencia del processor (`form_entries.db`) impide duplicar la request; AA-06 no se redispara porque `x_studio_location` no cambió.

---

## 12. Paso 12 — Integración con el pipeline existente

> La integración Connecteam → Odoo corre en `pipeline_registro_II/`. La trazabilidad de movimientos se cierra desde Odoo con AA-06 + SA-09 (Pasos 8 y 9); no requiere componentes adicionales en el pipeline.

### 12.1 Alcance del pipeline existente

El módulo R (Reemplazo/Extracción) de `pipeline_registro_II/processor.py` (líneas 1631–2913, documentado en `general_doc/processor_documentation.md` §8) cubre el ciclo completo:

- Polea Connecteam vía `main.py` por cron GitHub Actions (`0 11 * * 1-6` UTC).
- Resuelve equipos por serial (`maintenance.equipment`), valida puntos (`x_maintenance_location.x_name`).
- Bifurca por `alcance_R`: `Ciclo de calibración` (con sub-flujo Metrocal `team=2`, `tcnico=5118`) vs `Otro motivo` (daño / cambio).
- Itera subtipos E (sale) e I (entra), creando solicitudes `Extracción` / `Calibración` / `Instalación` (literales en `x_studio_tipo_de_trabajo`).
- **Mueve `x_studio_location`** del equipo a `593` (Laboratorio | Metrocal), `594` (Bodega cliente), o al punto del trabajo.
- Idempotencia robusta en `form_entries.db` (SQLite tabla `processed_entries`, commiteada por CI).
- Excepciones ruteadas a `x_inbox_integracion` con etiquetas y followers — patrón establecido (ver `general_doc/gestion_manual_inbox.md`).

### 12.2 Cómo se cierra la trazabilidad con la nueva entidad

**AA-06 (Paso 9)** escucha cambios en `maintenance.equipment.x_studio_location`. **SA-09 (Paso 8)** crea automáticamente el registro `x_equipment_movement` con el `reason` inferido según el destino:

| Origen del cambio en `x_studio_location`                               | Destino           | `reason` inferido por SA-09                                                   |
| ------------------------------------------------------------------------ | ----------------- | ------------------------------------------------------------------------------- |
| `processor.py` módulo R · t=E · alcance=Calibración · destino Lab | `id 593`        | `calibration`                                                                 |
| `processor.py` módulo R · t=E · alcance=Otro · destino Bodega      | `id 594`        | `repair`                                                                      |
| `processor.py` módulo R · t=I (equipo que entra)                     | punto del trabajo | `reassignment` (si tenía ubicación previa) o `installation` (primera vez) |
| `processor.py` módulo I · primera asignación                        | punto             | `installation`                                                                |
| `processor.py` módulo I · cambio de punto                            | punto             | `reassignment`                                                                |
| Edición manual en Odoo (Studio o admin)                                 | cualquiera        | inferido por las mismas reglas                                                  |

Odoo lleva la bitácora `x_equipment_movement` en paralelo al pipeline, sin cambios en `pipeline_registro_II`.

### 12.3 Limitación conocida

`x_equipment_movement.linked_request_id` queda **NULL** en los movements generados por AA-06 desde el processor: AA-06 dispara *después* del `write()` y no tiene contexto de qué `maintenance.request` se creó en esa misma transacción. La consulta "qué equipos pasaron por X punto" funciona sin ese link.

Si se necesita el linkeo (p. ej. reportes que cruzan calibraciones con ubicaciones):

1. **Lado pipeline**: un módulo `equipment_movement_linker.py` que corra después de `main.py` y matchee movements sin link con requests por equipo + fecha cercana.
2. **Lado Odoo**: una búsqueda heurística en SA-09 de la última request creada para ese equipo en los últimos N segundos.

### 12.4 Forms Connecteam

El form actual ya tiene las preguntas necesarias para R (serial extracción + serial instalación + motivo + destino). Si se detectan campos faltantes para enriquecer `x_equipment_movement.notes`, se agregan al form existente.

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

### A.3 Generar las próximas N ocurrencias

Ver **SA-07** en el Paso 8 (botón "Proyectar serie"). El re-fechado de la cola pre-generada cuando la cadencia se desliza lo hace el paso 4-bis de SA-02.

---

## 14. Apéndice B — Mapping rápido de campos

| Modelo                                            | Campo                                                                    | Tipo                          | Origen                 | Nota                                                                               |
| ------------------------------------------------- | ------------------------------------------------------------------------ | ----------------------------- | ---------------------- | ---------------------------------------------------------------------------------- |
| `x_maintenance_plan`                            | `name`                                                                 | char                          | nativo                 | autogenerado por SA-00                                                             |
| ↑                                                | `location_id`                                                          | m2o → x_maintenance_location | nuevo                  | requerido                                                                          |
| ↑                                                | `scheduled_date`                                                       | date                          | nuevo                  | requerido                                                                          |
| ↑                                                | `original_scheduled_date`                                              | date                          | nuevo                  | seteado por SA-00                                                                  |
| ↑                                                | `close_date`                                                           | date                          | nuevo                  | seteado por SA-02                                                                  |
| ↑                                                | `state`                                                                | selection                     | nuevo                  | 6 valores                                                                          |
| ↑                                                | `frequency_value` / `frequency_unit`                                 | int / sel                     | nuevo                  | —                                                                                 |
| ↑                                                | `slack_days`                                                           | int                           | nuevo                  | default 3                                                                          |
| ↑                                                | `auto_replan`                                                          | bool                          | nuevo                  | default True                                                                       |
| ↑                                                | `series_id`                                                            | char                          | nuevo                  | uuid hex                                                                           |
| ↑                                                | `previous_plan_id` / `next_plan_id`                                  | m2o → self                   | nuevo                  | self-ref                                                                           |
| ↑                                                | `seq_in_series`                                                        | int                           | nuevo                  | 1, 2, …                                                                           |
| ↑                                                | `user_id` / `technician_user_id` / `maintenance_team_id`           | m2o                           | nuevo (user_id nativo) | herencia a hijas                                                                   |
| ↑                                                | `maintenance_type`                                                     | sel                           | nuevo                  | preventive/corrective                                                              |
| ↑                                                | `resource_calendar_id`                                                 | m2o → resource.calendar      | nuevo                  | calendario laboral                                                                 |
| ↑                                                | `equipment_snapshot_ids`                                               | m2m → maintenance.equipment  | nuevo                  | snapshot                                                                           |
| ↑                                                | `last_sync_with_location`                                              | datetime                      | nuevo                  | timestamp                                                                          |
| ↑                                                | `progress` / `delta_days_from_planned` / `adjusted_from_scheduled` | computed                      | nuevo                  | read-only                                                                          |
| ↑                                                | `gantt_start` / `gantt_stop`                                         | date (computed, stored)       | nuevo                  | ventana `scheduled_date ± slack_days` para la vista Gantt                       |
| ↑                                                | `force_close_reason`                                                   | text                          | nuevo                  | requerido si partially_done                                                        |
| ↑                                                | `notes`                                                                | text                          | nuevo                  | libre                                                                              |
| ↑                                                | `contract_start_date`                                                  | date                          | nuevo                  | informativo                                                                        |
| ↑                                                | `contract_end_date`                                                    | date                          | nuevo                  | **límite duro de la cascada**: corta la generación de ocurrencias          |
| ↑                                                | `request_ids`                                                          | o2m → maintenance.request    | nuevo                  | inverso plan_id                                                                    |
| ↑                                                | `movement_ids`                                                         | o2m → x_equipment_movement   | nuevo                  | inverso linked_plan_id                                                             |
| ↑                                                | `active` / `company_id` / chatter                                    | varios                        | nativos features       | —                                                                                 |
| `maintenance.equipment`                         | `x_managed_by_plan`                                                    | bool (computed, stored)       | nuevo                  | solo informativo (badge/filtros)                                                   |
| ↑                                                | `movement_ids`                                                         | o2m → x_equipment_movement   | nuevo                  | inverso equipment_id                                                               |
| `maintenance.request`                           | `plan_id`                                                              | m2o → x_maintenance_plan     | nuevo                  | indexed, ondelete=set null, tracked                                                |
| `x_maintenance_location`                        | `plan_ids`                                                             | o2m → x_maintenance_plan     | nuevo                  | inverso location_id                                                                |
| ↑                                                | `movement_out_ids`                                                     | o2m → x_equipment_movement   | nuevo                  | inverso from_location_id                                                           |
| ↑                                                | `movement_in_ids`                                                      | o2m → x_equipment_movement   | nuevo                  | inverso to_location_id                                                             |
| **`x_equipment_movement`** (NUEVO modelo) | `name`                                                                 | char                          | nuevo                  | autogenerado `MOV-{YYYY}-{seq:04d} / {eq}`                                       |
| ↑                                                | `equipment_id`                                                         | m2o → maintenance.equipment  | nuevo                  | requerido, indexed, ondelete=restrict                                              |
| ↑                                                | `from_location_id` / `to_location_id`                                | m2o → x_maintenance_location | nuevo                  | NULL admitido (stock/servicio)                                                     |
| ↑                                                | `reason`                                                               | selection                     | nuevo                  | installation·calibration·repair·reassignment·return_from_service·decommission |
| ↑                                                | `date_out` / `date_in`                                               | date                          | nuevo                  | SA-09 setea ambas al día del cambio (hecho consumado)                             |
| ↑                                                | `state`                                                                | selection                     | nuevo                  | completed·cancelled                                                               |
| ↑                                                | `replaced_by_id`                                                       | m2o → maintenance.equipment  | nuevo                  | opcional (anotación manual)                                                       |
| ↑                                                | `linked_request_id`                                                    | m2o → maintenance.request    | nuevo                  | orden corrective asociada                                                          |
| ↑                                                | `linked_plan_id`                                                       | m2o → x_maintenance_plan     | nuevo                  | plan de origen (ref débil)                                                        |
| ↑                                                | `notes` / `company_id`                                               | varios                        | nuevo                  | —                                                                                 |

---

## 15. Apéndice C — Referencias oficiales

- [Models, modules and apps — Odoo 16 Studio](https://www.odoo.com/documentation/16.0/applications/studio/models_modules_apps.html)
- [Fields and widgets — Odoo 16 Studio](https://www.odoo.com/documentation/16.0/applications/studio/fields.html)
- [Automated actions — Odoo 16](https://www.odoo.com/documentation/16.0/applications/studio/automated_actions.html)
- [Server Actions reference — Odoo 16 (`ir.actions.server`)](https://www.odoo.com/documentation/16.0/developer/reference/backend/actions.html)
- [Computed fields — Odoo 16 tutorial](https://www.odoo.com/documentation/16.0/developer/tutorials/getting_started/09_compute_onchange.html)
- [ORM API reference — Odoo 16](https://www.odoo.com/documentation/16.0/developer/reference/backend/orm.html)
- Diagrama ER de referencia: `propuesta_plan_punto.drawio` (este directorio).
- ER de los modelos existentes: `er_mantenciones.drawio`.
- Introspección cruda usada como verdad: `er_introspection.json`.

---

## 16. Apéndice D — Riesgos y mitigaciones

| Riesgo                                                                   | Mitigación                                                                                                                                                                                               |
| ------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cascadas recursivas infinitas.                                           | La cascada no se re-ejecuta sobre planes futuros: cada ocurrencia dispara la suya al cerrar (AA-02).                                                                              |
| Studio compute sandbox bloquea `record.x_field = …`.                  | Usar `record['x_field'] = …` siempre (ya aplicado en snippets).                                                                                                                                        |
| `equipment_snapshot_ids` puede divergir del punto si nadie sincroniza. | UI: badge "Snapshot desactualizado" si `last_sync_with_location < write_date` del punto.                                                                                                                |
| Cancelación masiva archiva hijas; perdés métricas.                    | No usar `active=False`; mejor estado `cancelled` en hijas (requiere kanban_state custom).                                                                                                             |
| Hijas duplicadas: plan vs ciclo propio del equipo.                    | Conviven dos corrientes (plan_id seteado vs `plan_id=False`). `progress`/cascada/C-05 filtran por `request_ids`, así que las nativas se ignoran; AA-13/SA-10 las etiqueta para distinguirlas en la UI. Aplica solo si ambas corrientes modelan el mismo trabajo. |
| Solapamiento C-04 bloquea la cascada legítima.                          | SA-02 escribe/copia con `with_context(x_skip_c04=True)` y SA-C04 omite esas escrituras. Las ediciones manuales se validan.                                                    |
| Cambios concurrentes en el padre y una hija.                             | Activar tracking en `plan_id` y `state` para tener el log; considerar lock pesimista vía `for_update()` solo si aparece en producción.                                                            |

---

El modelo entidad-relación de referencia de esta implementación está en `propuesta_plan_punto.drawio` (este directorio).
