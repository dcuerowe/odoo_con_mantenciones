# Documentación Técnica — `processor.py`

> **Archivo:** `pipeline_registro_II/processor.py` · **~4 346 líneas** · Última revisión: 2026-05-26

---

## 1. Visión General

`processor.py` es el **núcleo de procesamiento** del pipeline de registro de mantenciones. Su función es transformar las respuestas de formularios Connecteam en registros operativos dentro de Odoo ERP, generando informes PDF y notificaciones a lo largo del proceso.

```mermaid
flowchart LR
    A[Connecteam Forms] --> B[process_entrys]
    B --> C{Tipo de Trabajo}
    C --> D[MC - Correctiva]
    C --> E[CF - Configuración]
    C --> F[R - Reemplazo/Extracción]
    C --> G[I - Instalación]
    C --> H[MP - Preventiva]
    D & E & F & G & H --> I[Odoo ERP]
    D & E & F & G & H --> J[Informe PDF]
    D & E & F & G & H --> K[Notificaciones inbox]
```

> **Nota:** Existía un módulo `CI` (Calibración) independiente que fue **absorbido por el módulo R** (rama `alcance_R == "Ciclo de calibración"`). En el código actual no existe `elif id == "CI":`; las solicitudes de Calibración se siguen creando, pero desde R.

---

## 2. Función Principal: `process_entrys()`

### 2.1 Firma y Parámetros

```python
def process_entrys(ordered_responses, API_key_c, resumen, exito, odoo_client, sharepoint_client=None)
```

| Parámetro            | Tipo                 | Descripción                                                 |
| --------------------- | -------------------- | ------------------------------------------------------------ |
| `ordered_responses` | `pd.DataFrame`     | Respuestas del formulario Connecteam ordenadas               |
| `API_key_c`         | `str`              | API key de Connecteam para resolver usuarios                 |
| `resumen`           | `list`             | Acumulador de operaciones con**anomalías**            |
| `exito`             | `list`             | Acumulador de operaciones**exitosas**                  |
| `odoo_client`       | `OdooClient`       | Cliente XML-RPC para interactuar con Odoo                    |
| `sharepoint_client` | `SharepointClient` | *(Deshabilitado)* Cliente para subir archivos a SharePoint |

### 2.2 Dependencias Externas

| Módulo              | Función                      | Propósito                                         |
| -------------------- | ----------------------------- | -------------------------------------------------- |
| `connecteam_api`   | `user()`                    | Resolver ID de usuario → nombre del técnico      |
| `data_processing`  | `detalle_op()`              | Registrar detalle de operación (éxito/anomalía) |
| `data_processing`  | `inbox()`                   | Crear notificación interna en Odoo                |
| `report_generator` | `informe_pdf_profesional()` | Generar informe PDF del trabajo realizado          |

---

## 3. Estructuras de Datos y Configuraciones Globales

*(Definidas dentro del loop principal, líneas 41–81)*

### 3.1 Tipos de Trabajo Soportados

```python
id_tipo_de_trabajo = ['MP', 'MC', 'I', 'CI', 'CF']  # ⚠ no incluye 'R'
```

Ramas realmente implementadas en el loop principal (`for id in id_tipos_realizados`):

| ID     | Nombre Completo                  | `maintenance_type` en Odoo                                   |
| ------ | -------------------------------- | -------------------------------------------------------------- |
| `MC` | Mantención Correctiva           | `corrective`                                                 |
| `MP` | Mantención Preventiva           | `preventive`                                                 |
| `I`  | Instalación                     | `False` (sin tipo)                                           |
| `CF` | Configuración                   | `preventive`                                                 |
| `R`  | Reemplazo/Extracción            | `preventive` para Calibración interna; `False` para Extracción/Instalación |

> **Inconsistencia conocida:** `id_tipo_de_trabajo` no se actualizó al agregar R y el filtro `id_tipos_interes` (L160-164) excluye 'R'. Hoy ese filtro no se usa para iterar (el loop real es sobre `id_tipos_realizados`), por lo que R se procesa igual, pero la lista queda desfasada.

> **CI ya no es módulo propio:** `id_mantencion` aún define `'R': 'Reemplazo/Extracción'` y `'E': 'Calibración'` (este último, semánticamente equivocado — E es Extracción). El R-block ignora `id_mantencion` y escribe literales `'Extracción'`, `'Calibración'`, `'Instalación'` en `x_studio_tipo_de_trabajo`.

### 3.2 Subtipos por Módulo

| Módulo | Lista de subtipos      | Significado de cada letra                          |
| ------- | ---------------------- | -------------------------------------------------- |
| MP      | `MP_type = ['T', 'I']` | Tablero, Instrumento (Dispositivo)                 |
| I       | `I_type  = ['I', 'T']` | Instrumento (Dispositivo), Tablero                 |
| R       | `R_type  = ['E', 'I']` | Extracción (equipo que sale), Instalación (equipo que entra) |

### 3.3 Mapeo de Operadores

Diccionario `operators` que mapea **nombre del técnico** → **ID de contacto en Odoo** (modelo `res.partner`). Se usa para asignar el campo `x_studio_tcnico` en las solicitudes de mantenimiento.

### 3.4 Estados de Solicitud en Odoo (`stage_id`)

| ID | Estado     | Significado en el pipeline            |
| -- | ---------- | ------------------------------------- |
| 3  | En proceso | Trabajo iniciado, pendiente de cierre |
| 4  | Desechar   | Equipo dado de baja                   |
| 5  | Finalizado | Trabajo completado exitosamente       |

---

## 4. Flujo de Iteración General

```mermaid
flowchart TD
    A[Iterar ordered_responses] --> B[Resolver usuario Connecteam]
    B --> C[Detectar puntos visitados por prefijo numérico]
    C --> D[Loop por cada punto visitado i]
    D --> E[Extraer tipos de trabajo realizados]
    E --> F[Parsear nombre de proyecto y punto de monitoreo]
    F --> G[Contar instancias por tipo: MC, CF, R-E, R-I, MP-I, MP-T, I-I, I-T]
    G --> H[Extraer imágenes y observaciones generales]
    H --> I[Loop por cada tipo de trabajo realizado]
    I --> J{"¿Tipo?"}
    J -->|MC| K[Módulo MC]
    J -->|CF| L[Módulo CF]
    J -->|R| M[Módulo R]
    J -->|I| N[Módulo I]
    J -->|MP| O[Módulo MP]
```

### 4.1 Detección de Puntos Visitados (L84–91)

Se escanean las columnas del DataFrame buscando aquellas que comienzan con un dígito. Cada dígito único representa un **punto de monitoreo visitado**.

```
Columna "1.2 Tipo de trabajo" → punto visitado "1"
Columna "2.1 Punto de monitoreo" → punto visitado "2"
```

### 4.2 Resolución del Punto de Monitoreo (L112–147)

```mermaid
flowchart TD
    A{"¿Punto == 'No encontrado'?"}
    A -->|Sí| B[Usar campo manual 'Indicar nombre del punto']
    A -->|Sí| C[Extraer proyecto desde columna separada]
    A -->|No| D[Extraer proyecto desde corchetes via regex]
    A -->|No| E[Limpiar nombre del punto eliminando proyecto entre corchetes]
```

El formato esperado en Connecteam es: `Nombre del Punto [Nombre del Proyecto]`

### 4.3 Conteo de Instancias por Tipo (L166–253)

Para cada tipo de trabajo se cuentan las instancias usando el patrón de columnas:

```
{punto}.2.{equipo} {TIPO} ({SUBTIPO}) | Campo
```

Ejemplo: `1.2.3 MP (I) | Modelo` → tercera instancia de MP tipo Instrumento en el punto 1.

Se generan diccionarios de conteo:

- `conteo_MP = {'I': n, 'T': m}` — MP por subtipo
- `conteo_I  = {'I': n, 'T': m}` — Instalación por subtipo
- `conteo_R  = {'E': n, 'I': m}` — Reemplazo por subtipo
- `conteo_instancias_MC`, `conteo_instancias_CF`, `conteo_instancias_CI`, `conteo_instancias_E` — contadores simples (CI y E ya no tienen rama propia; sus contadores quedaron como código muerto)

### 4.4 Variables Globales del Punto (L263–269)

Extraídas una vez por punto visitado y reutilizadas en todos los módulos:

| Variable     | Fuente                               |
| ------------ | ------------------------------------ |
| `proyecto` | Columna `{i}.1 Proyecto`           |
| `punto`    | Columna `{i}.1 Punto de monitoreo` |
| `ot`       | Columna `#` (número de OT)        |
| `fecha`    | Columna `Fecha visita`             |
| `tecnico`  | Columna `user` (nombre resuelto)   |
| `cliente`  | Columna `Nombre del Cliente`       |

---

## 5. Pipeline Transversal de Validaciones

Todos los módulos (MC, CF, CI, I, MP) comparten un **pipeline de validación** previo a la creación/actualización de solicitudes en Odoo. Este patrón se repite con variaciones menores en cada módulo.

```mermaid
flowchart TD
    A[Buscar equipo por S/N en maintenance.equipment] --> B{"¿Equipo encontrado?"}
    B -->|No| C[Buscar en stock.move.line si hay transferencia pendiente]
    C -->|Sí| D["inbox: 'Creación en espera'"]
    C -->|No| E["inbox: 'S/N no encontrado'"]
    B -->|Sí| F[Validar ubicación del equipo]
    F --> G{"¿location == False?"}
    G -->|Sí| H[message_post: Sin evento de instalación]
    G -->|No| I{"¿location != punto actual?"}
    I -->|Sí| J[message_post: Cambio de ubicación]
    I -->|No| K[Continuar con lógica del módulo]
    H --> K
    J --> K
    K --> L[Validar existencia del punto en Odoo]
    L --> M{"¿Punto existe?"}
    M -->|No| N[inbox: Punto no existe en sistema]
    M -->|Sí| O[Proceder con solicitudes]
```

### 5.1 Validación de Ubicación del Equipo

Se consulta `x_studio_location` del equipo. Hay **tres escenarios**:

1. **Sin ubicación (`False`)**: El equipo no tiene un evento de instalación previo. Se notifica vía `message_post` y se registra en `inbox` con prioridad `'N'` (Notificación).
2. **Ubicación diferente**: El equipo está registrado en otro punto. Se notifica el cambio vía `message_post` y se registra en `inbox` como "Cambio de ubicación".
3. **Ubicación coincide**: Flujo normal, sin notificaciones adicionales.

### 5.2 Validación del Punto de Monitoreo

Se busca en `x_maintenance_location` un registro cuyo `x_name` coincida con `[{proyecto}] {punto}`. Si no existe, se registra anomalía y se envía `inbox` con prioridad `'M'` (Manual).

### 5.3 Fallback por S/N No Encontrado

Cuando el serial no se encuentra en `maintenance.equipment`, se busca en `stock.move.line` con dominio:

- `location_usage = 'transit'`
- `location_dest_usage = 'customer'`
- `lot_id.name = serial`
- `state not in ['done', 'cancel']`

Si hay movimiento pendiente → "Creación en espera". Si no → "S/N no encontrado".

---

## 6. Módulo MC — Mantención Correctiva

**Líneas:** 283–882 · **Prefijo columnas:** `{i}.2.{equipo} MC | Campo`

### 6.1 Campos Extraídos

| Campo            | Clave formulario                           |
| ---------------- | ------------------------------------------ |
| `modelo_MC`    | `MC \| Modelo`                            |
| `tipo_MC`      | `MC \| Activo a intervenir`               |
| `serial_MC`    | `MC \| N° de serie`                      |
| `operativo_MC` | `MC \| ¿Equipo operativo tras trabajos?` |
| `obs_MC`       | `MC \| Observación`                      |

### 6.2 Lógica de Solicitudes

```mermaid
flowchart TD
    A[Buscar solicitudes MC del equipo] --> B["Filtrar: corrective + Mantención Correctiva"]
    B --> C{"¿Hay solicitudes activas?"}
    C -->|"Sí - interruptor=False"| D[Actualizar solicitud existente]
    C -->|"No - interruptor=True"| E[Crear nueva solicitud]
  
    D --> D1{"¿Operativo?"}
    D1 -->|Sí| D2["stage_id=5, close_date, feedback actividad"]
    D1 -->|No| D3["stage_id=3, adjuntar informe"]
  
    E --> E1{"¿Operativo?"}
    E1 -->|No| E2[Crear con stage_id=3 En proceso]
    E1 -->|Sí| E3["Crear con stage_id=5 Finalizado + close_date + feedback actividad"]
```

**Mecanismo del interruptor MC**: Se itera sobre todas las solicitudes correctivas del equipo. Si alguna tiene `schedule_date`, no está finalizada (!=5) ni desechada (!=4), el interruptor se cierra (`False`) y se **actualiza** esa solicitud. Si todas están cerradas, se **crea** una nueva.

### 6.3 Diferencia por Estado Operativo

| Operativo     | stage_id       | Acciones adicionale                                                   |
| ------------- | -------------- | --------------------------------------------------------------------- |
| **Sí** | 5 (Finalizado) | Asignar `close_date`, `x_studio_tcnico`, cerrar `mail.activity` |
| **No**  | 3 (En proceso) | Adjuntar PDF como `ir.attachment`, `message_post` con ubicación  |

---

## 7. Módulo CF — Configuración

**Líneas:** 884–1589 · **Prefijo columnas:** `{i}.2.{equipo} CF | Campo`

### 7.1 Campos Extraídos

Mismos que MC más: `alcance_CF` → `CF | Tipo de Ajuste`

### 7.2 Lógica de Solicitudes

```mermaid
flowchart TD
    A["Buscar solicitudes CF: preventive + Configuración"] --> B{"¿Existen solicitudes?"}
    B -->|Sí| C["Filtrar activas: no archivadas, con fecha, stage != 4,5"]
    C --> D{"¿Hay solicitudes de interés?"}
    D -->|Sí| E{"¿Alguna en proceso stage=3?"}
    E -->|Sí| F[Usar esa solicitud]
    E -->|No| G[Seleccionar la más cercana a la fecha del trabajo]
    G --> G1[Archivar solicitudes anteriores a la seleccionada]
    D -->|No| H[Crear nueva solicitud]
    B -->|No| H
  
    F & G --> I{"¿Operativo?"}
    I -->|Sí| J["Actualizar a stage=5 + close_date"]
    I -->|No| K["Actualizar a stage=3 + adjuntar PDF"]
  
    H --> L{"¿Operativo?"}
    L -->|Sí| M["Crear con stage=5 + close_date + feedback"]
    L -->|No| N["Crear con stage=3 + adjuntar PDF"]
```

### 7.3 Selección Inteligente de Solicitud

A diferencia de MC, CF implementa un **algoritmo de selección por proximidad temporal**:

1. **Prioridad 1**: Solicitud en estado "En proceso" (`stage_id=3`)
2. **Prioridad 2**: Solicitud con `schedule_date` más cercana a la `fecha` del trabajo
3. **Efecto colateral**: Las solicitudes con fecha anterior a la seleccionada se **archivan** automáticamente (`archive=True`)

### 7.4 Descripción del Request

El campo `description` se compone como HTML:

```html
<p><b>{alcance_CF}</b></p><p>{obs_CF}</p>
```

---

## 8. Módulo R — Reemplazo/Extracción

**Líneas:** 1631–2913 · **Prefijo columnas:** `{i}.2.{equipo} R | Campo` (generales) y `{i}.2.{equipo} R ({t}) | Campo` (específicos del subtipo)

> Este módulo absorbió la lógica del antiguo módulo CI. Una operación de reemplazo se modela como un par de subtrabajos: la pieza que sale (`t = 'E'`) y la pieza que entra (`t = 'I'`).

### 8.1 Doble Iteración (Extracción + Instalación)

```python
R_type = ['E', 'I']
for t in R_type:
    for equipo in range(1, conteo_R[t]+1):
```

### 8.2 Campos Extraídos

| Campo         | Origen                              | Clave |
|---------------|-------------------------------------|-------|
| `modelo_R`    | Específico `R ({t})`                | `R ({t}) \| Modelo` |
| `serial_R`    | Específico `R ({t})`                | `R ({t}) \| N° de serie` |
| `tipo_R`      | General                             | `R \| Tipo equipo/instrumento a reemplazar` |
| `obs_R`       | General                             | `R \| Observación` |
| `alcance_R`   | General                             | `R \| Motivo de reemplazo` |
| `destino_R`   | Específico `R (E)` (solo E)         | `R (E) \| Destino` (`None` cuando `t == 'I'`) |
| `trabajo_R`   | Asignado a `t`                      | — |

### 8.3 Bifurcación por Motivo del Reemplazo

R implementa un modelo bifásico basado en `alcance_R`:

```mermaid
flowchart TD
    A{"alcance_R"}
    A -->|"Ciclo de calibración"| B[Flujo de calibración]
    A -->|"Otro motivo (daño / cambio)"| C[Flujo de daño]

    B --> B1{"t"}
    B1 -->|E| BE[Equipo retirado para calibrar]
    B1 -->|I| BI[Equipo de reemplazo instalado]

    C --> C1{"t"}
    C1 -->|E| CE[Extracción por daño]
    C1 -->|I| CI[Instalación de reemplazo]
```

### 8.4 Flujo "Ciclo de Calibración" + `t = 'E'`

Subbifurca por `destino_R`:

```mermaid
flowchart TD
    A{"destino_R"}
    A -->|"Laboratorio | Metrocal"| B[Buscar solicitudes CI 'Calibración']
    A -->|"Bodega cliente / otro"| Z[Crear solo Extracción]

    B --> B1{"¿Existen solicitudes CI?"}
    B1 -->|Sí| C[Seleccionar la más cercana a fecha + archivar anteriores]
    C --> C1["update: stage=3, team=2 Metrocal, x_studio_tcnico=5118"]
    C1 --> C2["Crear Extracción stage=5 + close_date + feedback actividad"]
    C2 --> C3["Mover equipo a x_studio_location=593 (Laboratorio)"]

    B1 -->|No| D["Crear Calibración stage=3 + team=2 Metrocal"]
    D --> D1["Crear Extracción stage=5 + close_date + feedback"]
    D1 --> D2["Mover equipo a x_studio_location=593"]

    Z --> Z1["Crear Extracción stage=5 + close_date + feedback"]
    Z1 --> Z2["Mover equipo a x_studio_location=594 (Bodega cliente)"]
```

### 8.5 Flujo "Ciclo de Calibración" + `t = 'I'`

El equipo que **entra** al punto en reemplazo del que salió a calibrar:

1. Buscar solicitudes `preventive` + `Calibración` del equipo.
2. Si alguna está en proceso (`stage_id=3`) tomarla; si no, la más cercana a `fecha` (y archivar anteriores).
3. Actualizar esa solicitud a `stage=5`, team Metrocal, técnico Metrocal.
4. Crear solicitud de **Instalación** (`stage=5` + `close_date` + feedback de actividad).
5. Actualizar `x_studio_location` del equipo a `id_punto` con `assign_date=fecha`.

### 8.6 Flujo "Otro motivo" (daño / cambio operativo)

```mermaid
flowchart TD
    A{"t"}
    A -->|E| B["Crear Extracción (stage=5 inicial 4, luego write a 5) + close_date"]
    B --> B1["new_location_E: 594 si destino='Bodega cliente', 593 si 'Laboratorio | Metrocal', si no False"]
    B1 --> B2["archive=True salvo alcance_R == 'Otro'"]

    A -->|I| C["Crear Instalación stage=5 + close_date + feedback"]
    C --> C1["Actualizar x_studio_location=id_punto, assign_date=fecha"]
```

### 8.7 Followers Específicos del Módulo R

Toda solicitud creada en R agrega como followers a:

- `5205`: Felipe Riquelme
- `172`: Rodrigo López

(El `inbox()` base sigue notificando a 147/172/158.)

### 8.8 Particularidades y Trampas

- **Reemplaza al antiguo módulo CI**: la lógica de Extracción → Calibración → Re-instalación se mueve aquí, partida por subtipo `t` y por `alcance_R == "Ciclo de calibración"`.
- **No usa `id_mantencion[id]`**: cada request escribe literales `'Extracción'`, `'Calibración'`, `'Instalación'` en `x_studio_tipo_de_trabajo`.
- **Ubicaciones hardcoded**: `593 = Laboratorio | Metrocal`, `594 = Bodega cliente`. Cambian entre productivo y test.
- **Team/técnico Metrocal hardcoded**: `maintenance_team_id = 2`, `x_studio_tcnico = 5118`.
- **Conteo de prefijos R**: usa `+4` igual que el resto, pero ` R (E) |` no encaja con la convención (corta en `R (`); el `len()` igual da el resultado correcto porque sólo cuenta únicos por equipo.
- **`filter(like=filtro_general)` con `filtro_general = "{i}.2.{equipo} R"`** trae también columnas `R (E) |`/`R (I) |`, por lo que `columnas_equipo_R` queda con duplicados (no rompe porque `to_dict` colapsa, pero es frágil).

---

## 9. Módulo I — Instalación

**Líneas:** 2917–3605 · **Prefijo columnas:** `{i}.2.{equipo} I ({t}) | Campo`

### 9.1 Doble Iteración (Instrumento + Tablero)

```python
for t in I_type:  # ['I', 'T']
    for equipo in range(1, conteo_I[t]+1):
```

### 9.2 Campos Extraídos

| Campo           | Clave formulario                                                                                                    |
| --------------- | ------------------------------------------------------------------------------------------------------------------- |
| `modelo_I`    | `I ({t}) \| Modelo`                                                                                                |
| `tipo_I`      | `I ({t}) \| Tipo de {dispositivo/tablero}`                                                                         |
| `serial_I`    | `I ({t}) \| N° de serie`                                                                                          |
| `operativo_I` | `I ({t}) \| ¿Equipo operativo tras trabajos?`                                                                     |
| `obs_I`       | `I ({t}) \| Observación`                                                                                          |
| `alcance_I`   | Hardcoded `'IH \| Habilitación de equipo'` para `t='I'`, o campo `Alcance de la intervención` para `t='T'` |

### 9.3 Gestión de Ubicación (Diferencia clave con otros módulos)

Instalación es el **único módulo que escribe directamente** en `x_studio_location` del equipo:

```mermaid
flowchart TD
    A{"¿Ubicación actual?"}
    A -->|False| B["Escribir nueva ubicación + assign_date"]
    A -->|Diferente al punto| C["Actualizar ubicación + message_post cambio + inbox Notificación"]
    A -->|Igual| D[Sin cambios de ubicación]
    B & C & D --> E[Buscar solicitudes de instalación]
```

### 9.4 Lógica de Solicitudes

```mermaid
flowchart TD
    A["Buscar solicitudes: maintenance_type=False + Instalación"] --> B{"¿Hay solicitudes?"}
    B -->|Sí| C[Filtrar activas no archivadas/finalizadas/desechadas]
    C --> D{"¿Hay solicitudes de interés?"}
    D -->|Sí| E["Tomar la primera solicitud activa"]
    D -->|No| F[Crear nueva solicitud]
    B -->|No| F
  
    E --> G{"¿Operativo?"}
    G -->|Sí| H["stage=5 + close_date + feedback actividad"]
    G -->|No| I["Adjuntar PDF + message_post ubicación en solicitud existente"]
  
    F --> J{"¿Operativo?"}
    J -->|Sí| K["Crear con stage=5 + close_date + feedback"]
    J -->|No| L["Crear con stage=3 + adjuntar PDF + message_post"]
```

> **Nota**: A diferencia de CF/MP/CI, la selección de solicitud en I **no usa proximidad temporal**, sino que toma la primera solicitud activa encontrada.

---

## 10. Módulo MP — Mantención Preventiva

**Líneas:** 3608–4345 · **Prefijo columnas:** `{i}.2.{equipo} MP ({t}) | Campo`

### 10.1 Doble Iteración (Instrumento + Tablero)

Igual que Instalación, itera sobre `MP_type = ['T', 'I']`.

### 10.2 Campos Extraídos

| Campo            | Clave formulario                                                |
| ---------------- | --------------------------------------------------------------- |
| `modelo_MP`    | `MP ({t}) \| Modelo`                                           |
| `tipo_MP`      | `MP ({t}) \| {Dispositivo/Tablero} a intervenir`               |
| `serial_MP`    | `MP ({t}) \| N° de serie`                                     |
| `operativo_MP` | `MP ({t}) \| ¿{Dispositivo/Tablero} operativo tras trabajos?` |
| `obs_MP`       | `MP ({t}) \| Observación`                                     |

### 10.3 Lógica de Solicitudes

Estructura idéntica a CF con selección por proximidad temporal y archivado automático. Flujo:

1. Buscar solicitudes: `preventive` + `Mantención Preventiva`
2. Filtrar activas (no archivadas, con fecha, `stage != 4,5`)
3. Si hay solicitudes de interés → priorizar `stage=3`, si no → la más cercana temporalmente + archivar anteriores
4. Si no hay solicitudes → crear nueva + log "Sin plan de mantenimiento"
5. Si operativo=Sí → `stage=5` + `close_date` + feedback. Si No → `stage=3` + adjuntar PDF

### 10.4 Registro "Sin Plan de Mantenimiento"

Cuando el equipo **no tiene solicitudes activas ni históricas**, además de crear la solicitud, se registra en `resumen`:

```
'Equipo sin plan de mantenimiento en sistema'
```

---

## 11. Acciones Transversales Post-Procesamiento

### 11.1 Generación de Informe PDF

Todos los módulos vigentes (MC, CF, R, I, MP) generan un informe profesional vía `informe_pdf_profesional()` con parámetros: punto, OT, técnico, proyecto, fecha, cliente, tipo, modelo, serial, tipo de trabajo, alcance, punto, observaciones, imágenes y número de equipo.

El PDF se codifica en **base64** para adjuntarse como `ir.attachment` o almacenarse en `x_studio_informe`.

> **Nota R:** R pasa `t` (`'E'` o `'I'`) como argumento `trabajo`, no `'R'`. El diccionario `id_tipo_mantención` en `report_generator.py` mapea esas letras a 'extracción' / 'instalación'.

### 11.2 Nomenclatura de Archivos

```
informe_OT-{ot}_{punto}_{tipo}_{equipo}.pdf            # MC, CF, I
informe_OT-{ot}_{punto}_{tipo}_{subtipo}_{equipo}.pdf  # MP (incluye T/I)
informe_OT-{ot}_{punto}_R_{equipo}.pdf                  # R (un PDF por par E/I)
```

### 11.3 Registro en Inbox (`inbox()`)

| Prioridad     | Código | Significado                                     |
| ------------- | ------- | ----------------------------------------------- |
| Automática   | `'A'` | Operación exitosa, sin intervención requerida |
| Manual        | `'M'` | Requiere revisión/acción manual               |
| Notificación | `'N'` | Informativa, posible anomalía a validar        |

### 11.4 Gestión de Actividades (`mail.activity`)

Cuando una solicitud se finaliza (`stage=5`), el pipeline busca y cierra la actividad asociada mediante `action_feedback`.

---

## 12. Tabla Comparativa de Módulos

| Característica                  | MC             | CF                 | R                                                  | I            | MP             |
| -------------------------------- | -------------- | ------------------ | -------------------------------------------------- | ------------ | -------------- |
| **Subtipo**                      | No             | No                 | Sí (`E`/`I`)                                       | Sí (`I`/`T`) | Sí (`I`/`T`)   |
| **Genera PDF**                   | Sí             | Sí                 | Sí                                                 | Sí           | Sí             |
| **Modelo bifásico**              | No             | No                 | Sí (Calibración vs Daño × E/I)                     | No           | No             |
| **Selección por proximidad**     | No             | Sí                 | Sí (sub-flujo CI interno)                          | No (primera) | Sí             |
| **Archiva solicitudes viejas**   | No             | Sí                 | Sí (en sub-flujo CI)                               | No           | Sí             |
| **Escribe ubicación equipo**     | No             | No                 | Sí (593/594/id_punto)                              | Sí           | No             |
| **`maintenance_type` Odoo**      | `corrective`   | `preventive`       | `preventive` (Calibración) / `False` (Ext/Inst)    | `False`      | `preventive`   |
| **Campo alcance**                | No             | `Tipo de Ajuste`   | `Motivo de reemplazo`                              | Condicional  | No             |
| **Valida stock.move.line**       | Sí             | Sí                 | Sí                                                 | Sí           | Sí             |

---

## 13. Modelos Odoo Utilizados

| Modelo                     | Uso                                                           |
| -------------------------- | ------------------------------------------------------------- |
| `maintenance.equipment`  | Búsqueda de equipos por S/N, lectura/escritura de ubicación |
| `maintenance.request`    | Creación y actualización de solicitudes de mantenimiento    |
| `x_maintenance_location` | Validación de existencia de puntos de monitoreo              |
| `mail.activity`          | Cierre de actividades asociadas a solicitudes                 |
| `ir.attachment`          | Adjuntar informes PDF a solicitudes                           |
| `stock.move.line`        | Verificar transferencias pendientes (fallback S/N)            |

---

## 14. Manejo de Errores

El pipeline utiliza bloques `try/except` anidados con `traceback.print_exc()` para diagnóstico. Los errores **no detienen** la ejecución global; se registra el error y se continúa con `continue` al siguiente equipo/tipo/punto.

| Nivel                                 | Comportamiento ante error          |
| ------------------------------------- | ---------------------------------- |
| Resolución de usuario                | Asigna `"Usuario no encontrado"` |
| Búsqueda de equipo                   | `continue` al siguiente equipo   |
| Creación/actualización de solicitud | `continue` al siguiente equipo   |
| Notificación (message_post)          | `print` del error, no interrumpe |
| Cierre de actividad                   | `continue`, no crítico          |
