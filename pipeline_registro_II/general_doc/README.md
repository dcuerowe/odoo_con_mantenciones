# Pipeline de Registro — Connecteam → Odoo

Pipeline en Python que extrae las respuestas de formularios de mantención/instalación
desde **Connecteam**, las aplana y transforma, y crea/actualiza solicitudes de
mantenimiento (más informes PDF) en **Odoo** vía XML-RPC. Las salidas a
SharePoint/Excel existen pero están **deshabilitadas** en `main.py`.

> La lógica de negocio completa vive en `processor.py`. **No se documenta aquí**:
> ver [`processor_documentation.md`](./processor_documentation.md) para el detalle de
> `process_entrys()`, los módulos por tipo de trabajo (MC, CF, R, I, MP), los
> algoritmos de selección de solicitudes y los mapeos de campos Odoo.

---

## 1. Visión general del flujo

```mermaid
flowchart TD
    A[main.py: job] --> B[OdooClient.authenticate]
    A --> C[connecteam_api.form_structure]
    A --> D[connecteam_api.all_submission]
    C & D --> E[data_processing.ordenar_respuestas]
    E --> F[data_processing.check_new_sub]
    F -->|nuevas OTs| G[processor.process_entrys]
    F -->|dedupe| H[(form_entries.db)]
    G --> I[data_processing.detalle_op]
    G --> J[data_processing.inbox]
    G --> K[report_generator.informe_pdf_profesional]
    G --> L[(Odoo ERP)]
    J --> L
    K --> L
```

1. **`form_structure()`** baja el esquema del formulario (mapa `questionId → título`).
2. **`all_submission()`** baja las últimas 20 submissions.
3. **`ordenar_respuestas()`** aplana las respuestas anidadas en un `DataFrame`.
4. **`check_new_sub()`** descarta las OTs ya procesadas (estado en `form_entries.db`).
5. **`process_entrys()`** es el corazón: por cada OT/punto/equipo valida en Odoo,
   crea/actualiza solicitudes, genera el PDF y registra notificaciones en el inbox.

---

## 2. Puntos de entrada

| Script               | Rol                                                                                                  |
| -------------------- | ---------------------------------------------------------------------------------------------------- |
| `main.py`            | **Entrada automática.** `job()` corre en GitHub Actions (cron `0 11 * * 1-6`); detecta OTs nuevas vía `check_new_sub` y las procesa. SharePoint/Excel comentado. |
| `main_practice.py`   | **Entrada manual / pruebas.** Menú interactivo. Opción 1: procesar OTs específicas con **doble filtro** (OT → punto a procesar dentro de la OT). |

> La opción 1 de `main_practice.py` permite, tras elegir las OTs, seleccionar qué
> **puntos** procesar dentro de cada OT (los puntos se identifican por el prefijo
> numérico de las columnas, mismo criterio que `process_entrys`).

---

## 3. Scripts del pipeline

| Script                       | Función                                                                                                        |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `config.py`                  | Carga `.env`, fija `FORM_ID`, credenciales Odoo (toggle prod/test comentado) y URLs de SharePoint/logo.         |
| `connecteam_api.py`          | Cliente HTTP de Connecteam: `form_structure()`, `all_submission()` (últimas 20), `filter_submissions()` (por fecha, hoy hardcodeado), `submissions_by_date_range()` (paginado), `user()` (resuelve nombre del técnico). |
| `odoo_client.py`             | Wrapper XML-RPC (`OdooClient`): `authenticate`, `search`, `search_read`, `read`, `create`, `write`, `message_post`, `message_subscribe`, `action_feedback`. |
| `data_processing.py`         | `ordenar_respuestas()` (aplana submissions → DataFrame), `check_new_sub()` (dedupe contra SQLite), `detalle_op()` (acumula filas de resumen), `inbox()` (crea registros `x_inbox_integracion` + followers + adjuntos). |
| `processor.py`               | **Núcleo de negocio.** Ver [`processor_documentation.md`](./processor_documentation.md). |
| `report_generator.py`        | Genera el informe PDF profesional con ReportLab (`informe_pdf_profesional()`).                                  |
| `pdf_generator.py`           | CLI manual para generar PDFs sueltos (busca OT en Connecteam o formulario desde cero); guarda en `informes_pdf/`. |
| `excel_manager.py`           | *(Deshabilitado)* Inserta filas de resumen en la tabla Excel de SharePoint (`send_data`/`modify_excel_file`).   |
| `sharepoint_client.py`       | *(Deshabilitado)* Clase `Sharepoint`: descarga/sube archivos vía Microsoft Graph.                               |
| `conn_sharepoint.py`         | *(Deshabilitado)* Autenticación MSAL y helpers GET/PUT contra Graph.                                            |
| `form_simulator.py`          | Simulador de formularios Connecteam: arma submissions a mano desde `form.json` para probar el pipeline real.    |

---

## 4. Estado y persistencia

- **`form_entries.db`** (SQLite, tabla `processed_entries`) es el estado de dedupe.
  Se **commitea** desde CI tras cada corrida: ese commit es cómo persiste el estado
  entre ejecuciones. No agregarlo a `.gitignore` ni resetearlo (reprocesaría todo).
- Los errores **no detienen** el pipeline: cada equipo/módulo va envuelto en
  `try/except + traceback.print_exc() + continue`.

---

## 5. Convención de columnas del formulario

- Los puntos visitados se detectan por columnas que empiezan con un dígito
  (p. ej. `1.2 Tipo de trabajo` → punto `1`).
- Las columnas por equipo siguen `{punto}.2.{equipo} {TIPO} ({SUBTIPO}) | {Campo}`
  (p. ej. `1.2.3 MP (I) | Modelo`).
- El proyecto va embebido como `Punto [Proyecto]` y se extrae por regex.

---

## 6. Modelos Odoo tocados

`maintenance.equipment`, `maintenance.request`, `x_maintenance_location`,
`x_inbox_integracion`, `mail.activity`, `ir.attachment`, `stock.move.line`,
`res.partner`. Los campos `x_studio_*` son campos custom de Odoo Studio; sus nombres
no son estables entre upgrades de Odoo.

---

## 7. Documentación relacionada

- [`processor_documentation.md`](./processor_documentation.md) — detalle técnico de `processor.py`.
- `../qa/README.md` — estrategia y suite de pruebas (L1/L2/L3).
- `../qa/RESULTADOS.md` — resultados de QA y observaciones (`OBS-*`).
- `../qa/correcciones_QA.md` — bitácora de correcciones derivadas de QA.
