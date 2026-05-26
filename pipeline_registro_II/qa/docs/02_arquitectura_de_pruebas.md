# 02 · Arquitectura de Pruebas

> Cómo se aísla el SUT, cómo fluyen los datos de prueba, y qué hace cada doble de prueba.

---

## 1. Vista de aislamiento

El pipeline tiene **tres bordes externos**: Connecteam (HTTP), Odoo (XML-RPC) y el
disco (`form_entries.db`, PDFs). La estrategia es cortar cada borde según el nivel.

```mermaid
flowchart TB
    subgraph SUT["SUT — process_entrys"]
        PE[process_entrys]
        IB[data_processing.inbox]
        DOP[data_processing.detalle_op]
    end

    subgraph BORDES["Bordes externos"]
        CT["connecteam_api.user()<br/>HTTP"]
        PDF["report_generator.<br/>informe_pdf_profesional()<br/>HTTP imágenes + reportlab"]
        ODOO["OdooClient<br/>XML-RPC"]
        DB["form_entries.db<br/>SQLite"]
    end

    PE -->|resuelve técnico| CT
    PE -->|genera informe| PDF
    PE -->|create/write/...| ODOO
    IB -->|create/message_*| ODOO

    classDef mock fill:#fde,stroke:#a36;
    classDef real fill:#dfe,stroke:#3a6;

    CT:::mock
    PDF:::mock
    ODOO:::mock
```

| Borde | L1 unitario | L2 componente | L3 integración |
|-------|-------------|---------------|----------------|
| `connecteam_api.user()` | n/a | **monkeypatch** `processor.user` → nombre fijo | real (técnico real) |
| `informe_pdf_profesional()` | n/a | **monkeypatch** `processor.informe_pdf_profesional` → base64 dummy | real (genera PDF) |
| `OdooClient` | n/a | **OdooSpy** (registra, no envía) | real (test-Odoo) |
| `form_entries.db` | DB temporal | no se invoca (`check_new_sub` está fuera de `process_entrys`) | DB temporal o copia |

> **Detalle crítico de monkeypatching:** `processor.py` hace
> `from connecteam_api import user`, `from data_processing import detalle_op, inbox`,
> `from report_generator import informe_pdf_profesional` (líneas 6-8). Esos nombres
> quedan **rebindeados en el namespace `processor`**. Por eso se parchea
> `processor.user` / `processor.informe_pdf_profesional`, **no** `connecteam_api.user`.
> Parchear el módulo origen no tiene efecto sobre la referencia ya importada.

---

## 2. El OdooSpy

`OdooSpy` implementa la **misma interfaz** que `OdooClient` (`create`, `write`,
`search`, `search_read`, `read`, `message_post`, `message_subscribe`,
`action_feedback`, `execute_kw`) pero:

- **No abre conexión** ni autentica.
- **Registra** cada llamada en `self.calls` (lista de objetos `Call(method, model, args, kwargs)`).
- **Devuelve respuestas programables**: los tests pre-cargan qué debe devolver cada
  `search`/`search_read` para simular el estado de Odoo (equipo existe, solicitudes
  activas, etc.).

```mermaid
sequenceDiagram
    participant T as Test (L2)
    participant PE as process_entrys
    participant SPY as OdooSpy
    participant U as processor.user (patched)
    participant P as informe_pdf (patched)

    T->>SPY: queue_response("search_read","maintenance.equipment",[{id:42,...}])
    T->>SPY: queue_response("search","maintenance.request",[101])
    T->>PE: process_entrys(df, key, resumen, exito, spy)
    PE->>U: user(key, uid)
    U-->>PE: "Diego Marchant"
    PE->>SPY: search_read("maintenance.equipment", domain)
    SPY-->>PE: [{id:42, x_studio_location: 7, ...}]
    PE->>P: informe_pdf_profesional(...)
    P-->>PE: "ZHVtbXk="  (base64 dummy)
    PE->>SPY: write("maintenance.request",[101],{stage_id:5, close_date:...})
    SPY-->>PE: True
    PE-->>T: (retorna)
    T->>SPY: assert calls contiene write(...) con stage_id=5
```

Programar respuestas de `search`/`search_read` es lo que permite construir las
**precondiciones** ("hay una solicitud activa cercana", "no hay equipo", etc.) sin Odoo.

---

## 3. Flujo de datos de prueba (fixtures)

```mermaid
flowchart LR
    A["form.json<br/>(schema real Connecteam)"] --> B[ordenar_respuestas]
    C["fixtures/*.json<br/>(submission con la forma de all_submission)"] --> B
    B --> D["DataFrame plano<br/>(columnas = títulos de preguntas)"]
    D --> E{Capa}
    E -->|L1| F[Asserts sobre el DataFrame]
    E -->|L2| G["process_entrys + OdooSpy"]
    E -->|L3| H["process_entrys + test-Odoo real"]
```

Dos fuentes de DataFrame:

1. **Fixtures JSON** (`simulated_submissions/`, generadas por `form_simulator.py`):
   forma idéntica a `all_submission()`. Se pasan por `ordenar_respuestas(schema, sub)`
   para obtener el DataFrame real. **Preferido** porque ejercita también el parser.
2. **DataFrame fabricado a mano** en el test: filas/columnas construidas directamente
   siguiendo la convención `{i}.2.{equipo} TIPO (SUB) | Campo`. Útil para casos límite
   difíciles de capturar interactivamente.

> El catálogo de fixtures vive en [`scaffolding/integration/README.md`](../scaffolding/integration/README.md)
> y se cruza con los casos en cada doc de módulo.

---

## 4. Capa L3 — integración contra test-Odoo

```mermaid
sequenceDiagram
    participant T as Test (L3)
    participant CFG as config.py (URL_TEST)
    participant ODOO as Test-Odoo (real)

    Note over T: requiere RUN_ODOO_INTEGRATION=1<br/>si no, el test se SKIP-ea
    T->>CFG: leer URL_TEST/DB_TEST/USER_TEST
    T->>ODOO: authenticate()
    ODOO-->>T: uid
    T->>ODOO: process_entrys(df_fixture, ...)  (escribe de verdad)
    T->>ODOO: search_read('maintenance.request', [['x_name','=', ...]])
    ODOO-->>T: registro creado
    T->>T: assert campos + cleanup (archive/unlink del registro de prueba)
```

**Salvaguardas L3:**

- Se ejecuta **solo** con `RUN_ODOO_INTEGRATION=1` (gate explícito) y marker `integration`.
- `config.py` debe tener **activo el bloque `URL_TEST`** (no el productivo). El smoke
  test L3 verifica al inicio que `ODOO_URL` contiene el host de test y aborta si no.
- Idealmente cada test L3 **limpia** lo que creó (o usa OTs con prefijo reservado de QA),
  para no inflar el test-Odoo. Documentado como convención, no siempre automatizable
  porque `process_entrys` no devuelve los IDs que creó.

---

## 5. Por qué `process_entrys` no se parte en unidades

`process_entrys` es una sola función con el loop principal y las 5 ramas de módulo
inline (sin sub-funciones extraíbles). Testear "solo el módulo MC" significa, hoy,
**invocar toda la función** con un DataFrame que solo contenga trabajo MC. El spy
filtra el ruido: assertas únicamente sobre las llamadas Odoo relevantes.

> **Recomendación de testabilidad (mejora futura, fuera de alcance de QA):** extraer
> cada módulo a una función `_procesar_mc(df_visita, ctx, odoo)` permitiría unit tests
> directos. Mientras no ocurra, L2 con spy es el sustituto pragmático.
```
