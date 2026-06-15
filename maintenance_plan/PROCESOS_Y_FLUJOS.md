# Procesos y Flujos — Sistema de Mantención Preventiva por Punto (`x_maintenance_plan`)

> **Propósito:** documento técnico-funcional que grafica, proceso por proceso, **qué hace una persona** (capa manual) y **qué dispara el sistema** (capa automática: Server Actions + Automated Actions). Complementa al `PLAN_IMPLEMENTACION.md` (que tiene el detalle de campos, código y nombres técnicos).
>
> **Audiencia:** implementador funcional, soporte, y cualquiera que necesite entender "qué pasa cuando…".
>
> **Versión Odoo:** 16.0 (Studio + `base_automation`).

---

## 0. Convenciones y leyenda

### Capas

| Capa | Quién la ejecuta | Ejemplos |
|---|---|---|
| **Manual** | Una persona en la UI | Crear un plan, mover el `state` en el statusbar, apretar un botón, mover un equipo de ubicación |
| **Automática** | El ORM, vía Automated Action → Server Action | Generar hijas, calcular la próxima fecha, validar, registrar la bitácora |

### Cómo se enganchan SA y AA

- **Server Action (SA)** = el *qué hacer* (código Python). No corre sola.
- **Automated Action (AA)** = el *cuándo* (escucha un evento del ORM y ejecuta la SA).
- Algunas SA no cuelgan de una AA sino de un **botón** del formulario (SA-03, SA-04, SA-07).

> Detalle de este enganche en `PLAN_IMPLEMENTACION.md` §"Vinculación SA ↔ AA".

### Leyenda de los diagramas

```mermaid
flowchart LR
    M["Paso manual (persona)"]:::manual
    A["Paso automático (SA/AA)"]:::auto
    V["Validación que puede bloquear"]:::val
    D{"Decisión"}:::dec
    M --> A --> D
    classDef manual fill:#dbeafe,stroke:#2563eb,color:#1e3a8a;
    classDef auto fill:#ffedd5,stroke:#ea580c,color:#7c2d12;
    classDef val fill:#fee2e2,stroke:#dc2626,color:#7f1d1d;
    classDef dec fill:#f1f5f9,stroke:#475569,color:#0f172a;
```

> **Naming:** este documento usa **nombres lógicos** (`plan`, `state`, `scheduled_date`, `hija`) por legibilidad. En la instancia real llevan prefijo (`x_studio_state`, `x_studio_scheduled_date`, modelo `x_plan_de_mantencion_p`, bitácora `x_bitacora_de_movimien`). Ver la tabla de transposición en `PLAN_IMPLEMENTACION.md`.

---

## 1. Mapa general del sistema

Entidades y cómo se relacionan:

```mermaid
flowchart TD
    LOC["Punto / Ubicación<br/>(x_maintenance_location)<br/>+ contrato (start/end)"]:::ent
    PLAN["Plan de Mantención<br/>(x_maintenance_plan)<br/>una ocurrencia de la serie"]:::ent
    REQ["Solicitud / Hija<br/>(maintenance.request)"]:::ent
    EQ["Equipo<br/>(maintenance.equipment)"]:::ent
    MOV["Bitácora de Movimiento<br/>(x_equipment_movement)"]:::ent

    LOC -->|"1..N planes"| PLAN
    PLAN -->|"snapshot M2M"| EQ
    PLAN -->|"1..N hijas (plan_id)"| REQ
    REQ -->|"equipment_id"| EQ
    EQ -->|"x_studio_location"| LOC
    EQ -->|"1..N movimientos"| MOV
    MOV -->|"from/to location"| LOC
    PLAN -.->|"previous/next_plan_id<br/>(serie encadenada)"| PLAN

    classDef ent fill:#ecfeff,stroke:#0891b2,color:#155e75;
```

**Idea central:** el **plan es del punto**, no del equipo. Cada plan es **una ocurrencia** de una **serie** (cadena `previous/next_plan_id` con un `series_id` común). La serie avanza al **cerrar** una ocurrencia, no al crearla.

---

## 2. Ciclo de vida del plan (máquina de estados)

```mermaid
stateDiagram-v2
    [*] --> draft: crear plan (manual)<br/>+ SA-00 (name, series_id)
    draft --> scheduled: statusbar (manual)<br/>→ AA-01 → SA-01 (genera hijas)
    scheduled --> in_progress: statusbar (manual)
    in_progress --> done: statusbar (manual)<br/>→ AA-02 → SA-02 (cascada)
    in_progress --> partially_done: statusbar + motivo<br/>→ AA-02 → SA-02 (cascada + carryover)
    scheduled --> done: statusbar (manual)<br/>→ AA-02 → SA-02
    draft --> cancelled: botón Cancelar<br/>→ SA-04
    scheduled --> cancelled: botón Cancelar<br/>→ SA-04
    in_progress --> cancelled: botón Cancelar<br/>→ SA-04
    done --> [*]
    partially_done --> [*]
    cancelled --> [*]
```

> **Transiciones que disparan automatización:** solo **`→ scheduled`** (SA-01), **`→ done`/`→ partially_done`** (SA-02) y **`→ cancelled`** vía botón (SA-04). Mover a `in_progress` no dispara nada.
>
> **Validaciones** (SA-C01…C06) corren On Create & Update sobre todo cambio y pueden **bloquear** el guardado (ver §10).

---

## 3. Proceso P1 — Crear el plan

**Disparador:** una persona crea un registro de plan.

| Capa manual | Capa automática |
|---|---|
| Elegir punto, `scheduled_date`, frecuencia, slack, responsables. Guardar. | **AA-00 (On Create) → SA-00**: asigna `series_id` (secuencia), `seq_in_series=1`, `original_scheduled_date`, y `name` (`PMP-{año}-{seq} / {punto}`). |

```mermaid
flowchart TD
    A["Persona crea plan:<br/>punto, fecha, frecuencia, slack"]:::manual
    B["Guardar (create)"]:::manual
    C["AA-00 On Create"]:::auto
    D["SA-00: series_id, seq_in_series=1,<br/>original_scheduled_date, name"]:::auto
    E["Plan en estado draft<br/>con nombre PMP-AAAA-NNNN"]:::auto
    A --> B --> C --> D --> E
    classDef manual fill:#dbeafe,stroke:#2563eb,color:#1e3a8a;
    classDef auto fill:#ffedd5,stroke:#ea580c,color:#7c2d12;
```

> El `name` se completa **después** del insert (por eso el campo no es Required). Default `'New'` mientras tanto.

---

## 4. Proceso P2 — Programar el plan (`→ scheduled`) y generar hijas

**Disparador:** la persona mueve el `state` a `scheduled` en el statusbar.

| Capa manual | Capa automática |
|---|---|
| Statusbar → `scheduled`. | **AA-01 → SA-01**: (1) congela el **snapshot** de equipos del punto; (2) crea una **hija** por equipo; (3) estampa `tipo_de_trabajo = 'Mantención Preventiva'`. |

```mermaid
flowchart TD
    A["Persona: statusbar → scheduled"]:::manual
    B["AA-01 (Before: state≠scheduled,<br/>Apply: state=scheduled)"]:::auto
    C{"¿snapshot vacío?"}:::dec
    D["Congelar snapshot:<br/>equipos con location = punto,<br/>activos (Lab 593 / Bodega 594 quedan fuera)"]:::auto
    E["Por cada equipo del snapshot<br/>sin hija → crear maintenance.request"]:::auto
    F["Hija: schedule_date=plan,<br/>plan_id, responsables,<br/>tipo='Mantención Preventiva'"]:::auto
    G["Plan scheduled<br/>con N hijas vivas"]:::auto

    A --> B --> C
    C -->|sí| D --> E
    C -->|no| E
    E --> F --> G
    classDef manual fill:#dbeafe,stroke:#2563eb,color:#1e3a8a;
    classDef auto fill:#ffedd5,stroke:#ea580c,color:#7c2d12;
    classDef dec fill:#f1f5f9,stroke:#475569,color:#0f172a;
```

> Los equipos en **servicio externo** (Lab 593 / Bodega cliente 594) caen fuera del snapshot solos: su `x_studio_location` ya no es el punto.

---

## 5. Proceso P3 — Ejecutar y cerrar el plan (cascada de la serie)

Este es el corazón del sistema. Tiene una parte **manual** (el técnico hace el trabajo) y una **automática** muy rica (SA-02).

### 5.1 Capa manual

```mermaid
flowchart TD
    A["Técnico ejecuta el trabajo<br/>en cada hija (maintenance.request)"]:::manual
    B["Mueve cada hija por sus stages<br/>(hasta stage done)"]:::manual
    C{"¿Todas las hijas<br/>completas?"}:::dec
    D["Statusbar → done"]:::manual
    E["Statusbar → partially_done<br/>+ llenar force_close_reason"]:::manual
    C -->|sí| D
    C -->|no, pero hay que cerrar| E
    A --> B --> C
    classDef manual fill:#dbeafe,stroke:#2563eb,color:#1e3a8a;
    classDef dec fill:#f1f5f9,stroke:#475569,color:#0f172a;
```

> Si intentás `done` con hijas pendientes → **SA-C05 bloquea** (ver §10). Si cerrás `partially_done` sin motivo → **SA-C03 bloquea**.

### 5.2 Capa automática — SA-02 (cascada)

**Disparador:** `AA-02` (state → `done` o `partially_done`).

```mermaid
flowchart TD
    A["AA-02: state → done / partially_done"]:::auto
    B["SA-02 arranca<br/>close_date = hoy si vacío"]:::auto
    C{"¿cierre dentro<br/>del slack?"}:::dec
    D["base = scheduled_date"]:::auto
    E["base = close_date<br/>(cadencia deslizada)"]:::auto
    F["next_date = base + frecuencia<br/>→ ajustar a día hábil (calendario)"]:::auto
    G{"next_date ><br/>contract_end_date?"}:::dec
    H["SERIE MUERE por contrato:<br/>log en chatter, NO genera n+1"]:::auto
    I{"¿auto_replan?"}:::dec
    J{"¿existe next_plan_id<br/>(cola pre-generada)?"}:::dec
    K["Refechar n+1 + refechar EN BLOQUE<br/>la cola (paso 4-bis);<br/>lo que pase el contrato → cancelled"]:::auto
    L["Generar n+1 con copy():<br/>draft, nueva fecha, mismo series_id,<br/>seq+1, snapshot vacío"]:::auto
    M{"¿partially_done?"}:::dec
    N["CARRYOVER: recrear hijas pendientes<br/>en n+1, archivar las originales"]:::auto
    Z["Fin"]:::auto

    A --> B --> C
    C -->|sí| D --> F
    C -->|no| E --> F
    F --> G
    G -->|sí| H --> Z
    G -->|no| I
    I -->|no| M
    I -->|sí| J
    J -->|sí| K --> M
    J -->|no| L --> M
    M -->|sí| N --> Z
    M -->|no| Z
    classDef auto fill:#ffedd5,stroke:#ea580c,color:#7c2d12;
    classDef dec fill:#f1f5f9,stroke:#475569,color:#0f172a;
```

### 5.3 Secuencia completa de un cierre que genera la siguiente ocurrencia

```mermaid
sequenceDiagram
    actor T as Técnico
    participant P as Plan N
    participant AA as AA-02
    participant SA as SA-02
    participant P2 as Plan N+1
    participant R as Hijas

    T->>P: statusbar → done
    P->>AA: write(state=done)
    AA->>SA: ejecutar
    SA->>SA: calcular next_date (slack/contrato/calendario)
    alt next_date dentro de contrato y auto_replan
        SA->>P2: copy() nueva ocurrencia draft
        SA->>P: next_plan_id = Plan N+1
    else fin de contrato
        SA->>P: log "serie finalizada"
    end
    alt cerró partially_done
        SA->>R: recrear pendientes en N+1 (carryover)
        SA->>R: archivar originales
    end
```

> La serie **no** se re-ejecuta sola hacia el futuro: cada ocurrencia dispara su **propia** cascada cuando *ella* cierra. El paso 4-bis solo *re-fecha* la cola ya proyectada (sin recursión).

---

## 6. Proceso P4 — Cancelar el plan

**Disparador:** **botón "Cancelar"** en el formulario → SA-04. (No hay AA; cambiar el statusbar a `cancelled` a mano **no** ejecuta esta lógica.)

| Capa manual | Capa automática |
|---|---|
| Apretar botón "Cancelar" (con confirmación). | **SA-04**: archiva hijas vivas, pone `state=cancelled`, **puentea la cadena** si era una ocurrencia intermedia, log en chatter. |

```mermaid
flowchart TD
    A["Persona: botón Cancelar"]:::manual
    B["SA-04"]:::auto
    C["Archivar hijas vivas<br/>(kanban_state=blocked)"]:::auto
    D["state = cancelled"]:::auto
    E{"¿tiene previous Y next?<br/>(ocurrencia intermedia)"}:::dec
    F["Puentear cadena:<br/>previous.next = next<br/>next.previous = previous"]:::auto
    G["Cadena rota:<br/>la serie sigue desde el next"]:::auto
    H["Fin: serie termina aquí<br/>si era la cabeza"]:::auto
    A --> B --> C --> D --> E
    E -->|sí| F --> G
    E -->|no| H
    classDef manual fill:#dbeafe,stroke:#2563eb,color:#1e3a8a;
    classDef auto fill:#ffedd5,stroke:#ea580c,color:#7c2d12;
    classDef dec fill:#f1f5f9,stroke:#475569,color:#0f172a;
```

> **Cancelar NO genera la siguiente ocurrencia.** Si cancelás la última viva, la serie muere. Para continuar: crear un plan nuevo (serie nueva) o "Proyectar serie".

---

## 7. Proceso P5 — Sync con punto (reconciliar snapshot)

**Disparador:** **botón "Sync con punto"** → SA-03. Útil cuando cambiaron los equipos del punto después de programar.

```mermaid
flowchart TD
    A["Persona: botón Sync con punto"]:::manual
    B{"¿plan en draft<br/>o scheduled?"}:::dec
    X["UserError: solo draft/scheduled"]:::val
    C["SA-03: buscar equipos actuales del punto"]:::auto
    D["faltantes = en punto, no en snapshot<br/>sobrantes = en snapshot, no en punto"]:::auto
    E["Actualizar snapshot = equipos actuales<br/>last_sync_with_location = ahora"]:::auto
    F{"¿plan scheduled?"}:::dec
    G["Crear hijas para los faltantes<br/>(tipo Mantención Preventiva)"]:::auto
    H["Log: +faltantes / -sobrantes<br/>(las hijas sobrantes NO se borran)"]:::auto
    A --> B
    B -->|no| X
    B -->|sí| C --> D --> E --> F
    F -->|sí| G --> H
    F -->|no| H
    classDef manual fill:#dbeafe,stroke:#2563eb,color:#1e3a8a;
    classDef auto fill:#ffedd5,stroke:#ea580c,color:#7c2d12;
    classDef val fill:#fee2e2,stroke:#dc2626,color:#7f1d1d;
    classDef dec fill:#f1f5f9,stroke:#475569,color:#0f172a;
```

---

## 8. Proceso P6 — Proyectar serie (pre-generar ocurrencias futuras)

**Disparador:** **botón "Proyectar serie"** → SA-07. Pre-genera las ocurrencias futuras **en draft, sin hijas ni snapshot**, para que la Gantt muestre el plan completo del contrato.

```mermaid
flowchart TD
    A["Persona: botón Proyectar serie"]:::manual
    B["SA-07: caminar hasta el final<br/>de la cadena existente"]:::auto
    C{"¿horizonte?<br/>contract_end o 12 ocurr.<br/>(tope duro 60)"}:::dec
    D["Crear próxima ocurrencia draft:<br/>fecha = anterior + frecuencia,<br/>mismo series_id, seq+1,<br/>snapshot vacío"]:::auto
    E["Encadenar previous/next_plan_id"]:::auto
    F["Fin: serie proyectada<br/>(barras en la Gantt)"]:::auto
    A --> B --> C
    C -->|falta| D --> E --> C
    C -->|completo| F
    classDef manual fill:#dbeafe,stroke:#2563eb,color:#1e3a8a;
    classDef auto fill:#ffedd5,stroke:#ea580c,color:#7c2d12;
    classDef dec fill:#f1f5f9,stroke:#475569,color:#0f172a;
```

> **Idempotente:** re-ejecutar no duplica; completa solo lo que falte hasta el horizonte. Las hijas de cada ocurrencia nacen recién cuando esa ocurrencia pasa a `scheduled` (P2).

---

## 9. Proceso P7 — Reprogramar fecha del plan (propagación a hijas)

**Disparador:** la persona edita `scheduled_date` en un plan `draft`/`scheduled` → **AA-03 → SA-06**.

```mermaid
flowchart TD
    A["Persona edita scheduled_date<br/>(o lo mueve la cascada SA-02)"]:::manual
    B["AA-03 (On Update, state in draft/scheduled)<br/>dispara en CADA write"]:::auto
    C["SA-06 (autofiltrado):<br/>¿hijas con fecha distinta<br/>a la del plan?"]:::auto
    D{"¿hay hijas<br/>desalineadas?"}:::dec
    E["Actualizar schedule_date<br/>de esas hijas + log"]:::auto
    F["No-op (nada que propagar)"]:::auto
    A --> B --> C --> D
    D -->|sí| E
    D -->|no| F
    classDef manual fill:#dbeafe,stroke:#2563eb,color:#1e3a8a;
    classDef auto fill:#ffedd5,stroke:#ea580c,color:#7c2d12;
    classDef dec fill:#f1f5f9,stroke:#475569,color:#0f172a;
```

> SA-06 es el **único** punto de propagación de fecha: la cascada (SA-02) escribe `scheduled_date` en n+1 y deja que AA-03 → SA-06 alinee las hijas.

---

## 10. Proceso P8 — Movimiento de equipos (bitácora)

**Disparador:** cambia el `x_studio_location` de un equipo (manual desde Studio, o vía el pipeline `pipeline_registro_II`) → **AA-06 → SA-09**.

```mermaid
flowchart TD
    A["Cambio de ubicación del equipo<br/>(manual o pipeline)"]:::manual
    B["AA-06 (equipo On Update,<br/>dispara en cada write)"]:::auto
    C["SA-09: último movement → from_location<br/>(sin movement ⇒ baseline 594 'stock')"]:::auto
    D{"¿la ubicación<br/>cambió de verdad?"}:::dec
    E["No-op (mismo lugar)"]:::auto
    F["Inferir reason según destino"]:::auto
    G["593→calibration · 594→repair<br/>vuelve de Lab/Bod→return_from_service<br/>otro punto→reassignment<br/>sin previo→installation · sin destino→decommission"]:::auto
    H["Crear x_equipment_movement<br/>(date_in=date_out=hoy, completed)"]:::auto
    A --> B --> C --> D
    D -->|no| E
    D -->|sí| F --> G --> H
    classDef manual fill:#dbeafe,stroke:#2563eb,color:#1e3a8a;
    classDef auto fill:#ffedd5,stroke:#ea580c,color:#7c2d12;
    classDef dec fill:#f1f5f9,stroke:#475569,color:#0f172a;
```

| Capa manual | Capa automática |
|---|---|
| Mover el equipo de ubicación (o lo hace el pipeline). **Go-live:** correr el *seed* de bitácora (excepto equipos en 594). | **AA-06 → SA-09** crea el movimiento. **AA-MOV-00 → SA-MOV-00** le pone el `name` (`MOV-{año}-{seq}`). |

> El `period` nativo del equipo **no se toca**: su ciclo propio sigue corriendo en paralelo a las hijas del plan.

---

## 11. Proceso P9 — Validaciones (lo que puede bloquear un guardado)

En Odoo 16 no hay "Before save"; cada constraint es una SA con `raise UserError` disparada por una AA On Create & Update. Si el raise ocurre, **se revierte todo el guardado**.

```mermaid
flowchart TD
    A["Persona guarda un cambio en el plan"]:::manual
    B["AAs de validación corren por sequence (bajo)"]:::auto
    C{"SA-C01: frequency_value > 0"}:::val
    D{"SA-C02: slack < mitad del período"}:::val
    E{"SA-C03: partially_done ⇒ force_close_reason"}:::val
    F{"SA-C04: no solapar planes del mismo punto<br/>(salvo flag x_skip_c04 de la cascada)"}:::val
    G{"SA-C05: done ⇒ todas las hijas resueltas"}:::val
    H{"SA-C06: no archivar un plan vivo"}:::val
    OK["Guardado aplicado"]:::auto
    NO["UserError → rollback total"]:::val
    A --> B --> C --> D --> E --> F --> G --> H --> OK
    C -.falla.-> NO
    D -.falla.-> NO
    E -.falla.-> NO
    F -.falla.-> NO
    G -.falla.-> NO
    H -.falla.-> NO
    classDef manual fill:#dbeafe,stroke:#2563eb,color:#1e3a8a;
    classDef auto fill:#ffedd5,stroke:#ea580c,color:#7c2d12;
    classDef val fill:#fee2e2,stroke:#dc2626,color:#7f1d1d;
```

> Las validaciones tienen `sequence` **bajo** para reventar *antes* de que la lógica de negocio (AA-01/02/03) cree registros.

---

## 12. Proceso P10 — Etiquetado de hijas nativas del equipo

Coexisten dos corrientes de hijas en `maintenance.request`:

```mermaid
flowchart LR
    P["Hija del PLAN<br/>(plan_id ≠ vacío)"]:::auto
    N["Hija NATIVA del equipo<br/>(cron del period, plan_id vacío)"]:::auto
    P -->|"SA-01 / SA-03"| TP["tipo = 'Mantención Preventiva'<br/>(hardcodeado)"]:::auto
    N -->|"AA-13 → SA-10"| TN["tipo = 'Mantención del Equipo'"]:::auto
    classDef auto fill:#ffedd5,stroke:#ea580c,color:#7c2d12;
```

> Así no se confunden en kanban/listas, y el `progress` del plan solo cuenta sus propias hijas.

---

## 13. Tabla resumen: disparadores

| Proceso | Capa que lo inicia | Automatización | SA |
|---|---|---|---|
| P1 Crear plan | Manual (create) | AA-00 On Create | SA-00 |
| P2 Programar | Manual (statusbar → scheduled) | AA-01 | SA-01 |
| P3 Cerrar (cascada) | Manual (statusbar → done/partially_done) | AA-02 | SA-02 |
| P4 Cancelar | Manual (**botón**) | — | SA-04 |
| P5 Sync con punto | Manual (**botón**) | — | SA-03 |
| P6 Proyectar serie | Manual (**botón**) | — | SA-07 |
| P7 Reprogramar fecha | Manual (editar) o cascada | AA-03 | SA-06 |
| P8 Movimiento equipo | Manual / pipeline (cambio de ubicación) | AA-06 + AA-MOV-00 | SA-09, SA-MOV-00 |
| P9 Validaciones | Manual (cualquier guardado) | AA-07…AA-12 | SA-C01…C06 |
| P10 Etiquetar nativas | Automático (cron crea hija) | AA-13 | SA-10 |

---

## 14. Vista integral: un ciclo completo de la serie

```mermaid
sequenceDiagram
    actor U as Operario
    actor T as Técnico
    participant PL as Plan (serie)
    participant SYS as Sistema (AA/SA)
    participant EQ as Equipos / Bitácora

    U->>PL: crear plan (P1)
    SYS-->>PL: SA-00 inicializa (name, series_id)
    U->>PL: statusbar → scheduled (P2)
    SYS-->>PL: SA-01 snapshot + hijas
    T->>PL: ejecuta y completa hijas (P3 manual)
    Note over EQ: en paralelo, mover equipos<br/>registra bitácora (P8)
    T->>PL: statusbar → done (P3)
    SYS-->>PL: SA-02 genera la próxima ocurrencia
    Note over PL: la serie continúa: la nueva ocurrencia<br/>repite P2→P3 cuando llega su fecha
    U->>PL: (opcional) botón Cancelar (P4) → fin de serie
```

---

## 15. Reglas de oro (resumen ejecutivo)

1. **El plan es del punto.** Cada plan es una ocurrencia de una serie encadenada.
2. **La serie avanza al CERRAR** (`done`/`partially_done`), nunca al crear ni al cancelar.
3. **`scheduled` genera hijas** (snapshot congelado); equipos en Lab/Bodega quedan fuera solos.
4. **Cancelar es terminal** y va por **botón** (SA-04), no por statusbar.
5. **El contrato del punto es el límite duro**: la cascada no genera ocurrencias más allá de `contract_end_date`.
6. **La bitácora es append-only** y se alimenta de cada cambio de ubicación (SA-09).
7. **Las validaciones bloquean** vía `UserError` + rollback; corren primero.
8. **El `period` nativo del equipo coexiste** con el plan y no se gestiona desde acá.
