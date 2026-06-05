# Correcciones QA

Bitácora de correcciones aplicadas al pipeline a partir de las observaciones de QA
(`OBS-*` definidas en [`RESULTADOS.md`](./RESULTADOS.md) § Debilidades). Cada entrada
documenta el defecto, la causa, el cambio y la prueba que lo respalda.

---

## Serial numérico con ceros a la izquierda se elimina en la normalización · 2026-06-05

**Severidad:** Media · **Archivos:** `processor.py` (helper `normalizar_serial`) · **Estado:** Implementado

### Contexto

En Odoo **no existen** S/N numéricos que empiecen por `0`, pero el formulario de
Connecteam puede traer el serial tipeado con ceros a la izquierda (p. ej.
`"04245245"`). Esto dejaba el serial inconsistente con el `serial_no` real de Odoo
(`"4245245"`):

- Si pandas lo conserva como string `"04245245"`, la búsqueda numérica (substring
  `like '%04245245%'`) **no calza** con `"4245245"` (el `0` no está en el dato real).
- Si pandas lo infiere como número, el `0` se pierde antes de llegar a la normalización
  y solo se "rescataba" por casualidad vía substring cuando había un único candidato.

Es el caso que la corrección *"Búsqueda de equipo por patrón…"* (2026-05-29) dejó
explícitamente fuera de alcance en sus Notas.

### Cambio

`normalizar_serial` ahora, **después** de limpiar el float y los espacios, elimina los
ceros a la izquierda **solo** cuando el serial es puramente numérico (`str.isdigit()`):

```python
serial = str(serial).strip()
if serial.isdigit():
    serial = serial.lstrip('0') or '0'
return serial
```

- `"04245245"` → `"4245245"`; `"0024000"` → `"24000"`.
- El fallback `or '0'` evita un string vacío si el serial fuera todo ceros (`"000"` → `"0"`).
- Los serials **alfanuméricos** no se tocan: `"WE0000221"` y `"0WE221"` se preservan
  intactos (su lógica de ceros vive en el fallback WE de `_buscar_equipo_por_serial`).

Al normalizar el cero líder en origen, la búsqueda contra Odoo se hace siempre con el
serial real (`"4245245"`) y deja de depender del rescate frágil por substring (que
fallaba cuando había varios candidatos numéricos sin match exacto).

### Verificación

- `qa/scaffolding/unit/test_normalizar_serial.py` ampliado con los casos de cero
  líder: `"04245245"→"4245245"`, `"0024000"→"24000"`, `"  007  "→"7"`, `"000"→"0"`,
  y los alfanuméricos preservados (`"WE0000221"`, `"0WE221"`).
- Nuevo test L2 de flujo `qa/scaffolding/component/test_process_entrys_ot260_serial_cero.py`
  (escenario **OT 260, punto ET-0F**):
  - `test_ot260_serial_cero_se_normaliza_antes_de_buscar`: el dominio del `search_read`
    usa `"4245245"` y el `"04245245"` original **nunca** llega a Odoo.
  - `test_ot260_serial_cero_encuentra_equipo_y_crea_solicitud`: con el equipo real
    cargado como `"4245245"`, se encuentra y se crea la `maintenance.request` (no cae
    en "S/N no encontrado").

```bash
/Users/dacm/we/.venv/bin/python -m pytest \
  qa/scaffolding/unit/test_normalizar_serial.py \
  qa/scaffolding/component/test_process_entrys_ot260_serial_cero.py -q
# 16 passed
```

### Notas

- Supone que Odoo nunca almacena numéricos con cero líder (confirmado como regla de
  negocio). Si alguna vez existiera un `serial_no = "04245245"` real, dejaría de
  encontrarse — riesgo aceptado según la regla actual.

---

## Test TC-TR-15 desactualizado: wasHidden con dato real se conserva · 2026-06-05

**Severidad:** Baja (suite de QA, sin impacto en producción) · **Archivos:** `qa/scaffolding/unit/test_data_processing.py` · **Estado:** Corregido

### Contexto

El commit `bf53451` ("conservar respuestas con wasHidden si tienen dato real") cambió
`ordenar_respuestas`: una respuesta marcada `wasHidden=True` ya **no** se descarta si
trae dato real (Connecteam no reevalúa la visibilidad al editar la rama condicional de
una submission y devuelve casillas rellenadas con `wasHidden=True`). El descarte solo
ocurre cuando además no hay dato (`not _tiene_dato(...)`, `data_processing.py:44`).

El test `test_hidden_no_genera_columna` (TC-TR-15) quedó desactualizado: usaba un
`wasHidden=True` **con** `value="y"` pero seguía exigiendo que la columna se omitiera,
contradiciendo el nuevo contrato. Fallaba contra el código vigente.

### Corrección

Se separó TC-TR-15 en dos casos que reflejan el contrato real:

- `test_hidden_sin_dato_no_genera_columna`: `wasHidden=True` + `value=""` → columna
  omitida (comportamiento histórico para ramas no visitadas).
- `test_hidden_con_dato_si_genera_columna`: `wasHidden=True` + `value="y"` → columna
  conservada con su valor (contrato `bf53451`).

Es una corrección **solo de pruebas**; `processor.py`/`data_processing.py` no cambian.

```bash
/Users/dacm/we/.venv/bin/python -m pytest qa/scaffolding/unit qa/scaffolding/component -q
# 106 passed
```

---

## Instalación: omitir notificación de cambio de ubicación cuando viene de "Bodega cliente" · 2026-05-30

**Severidad:** Baja (reducción de ruido operacional) · **Archivos:** `processor.py` (módulo I) · **Estado:** Implementado

### Contexto

En el módulo de **Instalación**, cuando el equipo tenía una `x_studio_location` distinta
al punto donde se está instalando, el pipeline notificaba "Cambio de ubicación" por dos
vías:

1. `message_post` en el chatter del equipo (`maintenance.equipment`).
2. `inbox` con la etiqueta `Cambio de ubicación` (`x_inbox_integracion`).

El caso "el equipo venía de Bodega cliente y se está instalando en un punto" es el
**flujo esperado** de una instalación (el equipo estaba en bodega esperando ser
puesto en terreno), no una anomalía. La notificación generaba ruido en la bandeja
del revisor.

### Cambio

Si `location_I == "Bodega cliente"` (`display_name` de `x_maintenance_location` id `594`,
verificado contra el Odoo test), se **omiten** el `message_post` y el `inbox` de
"Cambio de ubicación". El resto del flujo se mantiene:

- El `write` de la nueva ubicación en `maintenance.equipment` sigue ocurriendo.
- `detalle_op` registra el movimiento en `resumen` para auditoría local.
- La rama de instalación (creación/actualización de la `maintenance.request`) corre
  normalmente después.

Para cualquier otra ubicación previa distinta al punto, el comportamiento histórico
queda intacto: chatter + inbox de "Cambio de ubicación".

### Verificación

- Nuevo test L2: `test_i_desde_bodega_cliente_no_notifica_cambio` valida que con
  `loc_name="Bodega cliente"`:
  - La ubicación del equipo SÍ se reescribe al `PUNTO_ID`.
  - NO aparece la etiqueta `Cambio de ubicación` en el `x_inbox_integracion`.
  - NO se publica un `message_post` con el header "Cambio de ubicación" en el chatter.
- El test existente `test_i_ubicacion_distinta_mueve_y_notifica` sigue verde (cualquier
  otra ubicación previa sí emite la notificación).

```bash
/Users/dacm/we/.venv/bin/python -m pytest qa/scaffolding/component qa/scaffolding/unit -q
# 97 passed
```

### Notas

- El check usa la cadena literal `"Bodega cliente"` (el `display_name`), no el id `594`.
  Es consistente con `processor.py:2903`, que ya compara contra esa cadena para
  `destino_R`. Una migración a otro Odoo que renombre esa ubicación rompería este
  filtro (riesgo análogo a OBS-9: IDs/strings hardcodeados).
- El cambio solo aplica al **módulo I**. El sub-flujo de instalación dentro del
  módulo R no emite hoy un `inbox` de "Cambio de ubicación" (solo escribe la
  ubicación silenciosamente), así que no necesita ajuste.

### Re-implementación · 2026-06-05

Al correr la suite completa se detectó que esta corrección **no estaba presente** en
`processor.py` (el bloque `elif location_I != '[proyecto] punto'` del módulo I no tenía
la excepción de "Bodega cliente"; nunca se commiteó o se perdió en `Cambios base`). El
test `test_i_desde_bodega_cliente_no_notifica_cambio` fallaba. Se re-implementó tal como
se describe arriba: el `write` de ubicación y `detalle_op` corren siempre, y el
`attachment` + `message_post` + `inbox` de "Cambio de ubicación" se omiten cuando
`location_I == "Bodega cliente"`. Suite completa en verde (106 passed).

---

## Búsqueda de equipo: fallback WE con tolerancia a ceros · 2026-05-29

**Severidad:** Media · **Archivos:** `processor.py` (helper `_buscar_equipo_por_serial`) · **Estado:** Implementado

### Contexto

Sonda contra el Odoo test con `serial_form = "WE0000000797"` reveló que el técnico
había tipeado un serial WE con la **cantidad de ceros equivocada** entre `WE` y la
cola numérica `797`. El equipo en Odoo está cargado como `WE000000000797` (9 ceros);
la búsqueda exacta no calzaba y el equipo "desaparecía", aunque el número lógico
(`WE797`) es el mismo.

Como el form es alfanumérico, la nueva lógica de substring para serials puramente
numéricos no aplica.

### Cambio

Agregamos un **fallback** dentro del camino alfanumérico, **solo** cuando el
`serial_form` tiene la forma `WE + dígitos`. Si la búsqueda exacta no encuentra
nada, normalizamos los ceros entre `WE` y la cola y reintentamos:

1. Computamos `cola = serial[2:].lstrip('0') or '0'` (p. ej. `"WE0000000797"` → `"797"`).
2. Buscamos en Odoo con dominio `[('serial_no','!=',False), ('serial_no','like', f'WE%{cola}')]`.
3. Filtramos en Python: el serial Odoo debe ser `WE + dígitos` y su cola (idem
   normalización) debe **igualar** la del form.
4. Si hay **exactamente 1** match → ese equipo. Si hay 0 o >1 → no encontrado.

### Lo que rescata y lo que NO

| Caso (form) | Odoo | Antes | Ahora |
| ----------- | ---- | ----- | ----- |
| `WE0000000797` | `WE000000000797` (id 221) | 0 | **id 221** |
| `WE0000001038` | `24000WE0001038` (id 917) | 0 | 0 (a propósito) |
| `WE0001038`    | `24000WE0001038` (id 917) | 0 | 0 (a propósito) |

El fallback **no** intenta rescatar formas con prefijos distintos al `WE` (p. ej. el
prefijo `24000WE…`). Eso fue una decisión explícita: la opción más amplia (cola
numérica vía árbol numérico) traía riesgo de falsos positivos por substring.
Para esos casos el técnico debe tipear el serial completo o, si el form es
puramente la cola numérica (`"1038"`), entra por el camino de la búsqueda numérica
ya cubierto en la corrección anterior.

### Verificación

- 6 unitarios L1 nuevos en `qa/scaffolding/unit/test_buscar_equipo_por_serial.py`:
  - `test_we_serial_con_ceros_distintos_se_resuelve` (caso documentado).
  - `test_we_serial_prefijo_24000WE_no_calza` (NO debe rescatar prefijos distintos).
  - `test_we_fallback_multiples_we_logicos_es_no_encontrado` (ambigüedad).
  - `test_we_exacto_no_dispara_fallback` (si exact calza, no se ejecuta).
  - `test_we_con_letras_despues_no_dispara_fallback`.
  - `test_we_solo_no_dispara_fallback`.
- Sondeo manual contra el Odoo test: `WE0000000797` resuelve a id 221.

```bash
/Users/dacm/we/.venv/bin/python -m pytest qa/scaffolding/component qa/scaffolding/unit -q
# 96 passed
```

---

## Búsqueda de equipo por patrón cuando el serial es puramente numérico · 2026-05-29

**Severidad:** Alta (resuelve cuello de botella OBS-11 ampliado) · **Archivos:** `processor.py` (helper + 5 módulos) · **Estado:** Implementado

### Contexto

OBS-11 ya garantizó que el serial llegue como string al `search_read` (normalización
float→string). Pero hay un caso real frecuente: el técnico tipea en el formulario un
serial numérico "corto" (p. ej. `24000`), mientras que el equipo en Odoo está cargado
con el formato extendido WE (`24000WE0000221`). La búsqueda exacta `serial_no = '24000'`
no calza y el equipo "desaparece" para el pipeline.

### Cambio de lógica

Cuando el serial del formulario es **puramente numérico** (`str.isdigit()`), la
búsqueda exacta se reemplaza por una búsqueda **por substring** dentro de un
**universo restringido**: equipos cuyo `serial_no` es puramente numérico **o**
contiene `"WE"` (mayúsculas).

Sobre el conjunto de coincidencias se aplica este árbol de decisión:

```
matches    = equipos del universo cuyo serial_no CONTIENE serial_form
numericas  = [m | m.serial_no.isdigit()]
wes        = [m | "WE" in m.serial_no]
exactas    = [m | m.serial_no == serial_form]

len(matches) == 0                            → no encontrado (fallback stock.move.line)
len(matches) == 1                            → ese equipo
∃ una numérica EXACTA (==serial_form)        → esa (regla universal)
>1 numéricas exactas                          → no encontrado (duplicado real en Odoo)
solo numéricas (sin WE), sin exacta           → no encontrado
solo WE (sin numéricas)                       → no encontrado
mixto, len(serial_form) > 4, sin exacta       → no encontrado
mixto, len(serial_form) ≤ 4, exactamente 1 WE → esa WE
mixto, len(serial_form) ≤ 4, >1 WE            → no encontrado
```

Si el serial **no** es puramente numérico (alfanumérico, p. ej. `24000WE0000221`,
`SN-XYZ`), se mantiene la búsqueda exacta histórica — sin cambios.

### Implementación

Nuevo helper `processor._buscar_equipo_por_serial(odoo_client, serial)` que
encapsula el árbol y devuelve una lista de 0 o 1 dict (drop-in del `search_read`
previo). Los 5 módulos (MC, CF, R, I, MP) reemplazaron su `search_read` inline por
una llamada al helper.

- **Server-side**: dominio `[('serial_no','!=',False), ('serial_no','like','%{serial}%')]`
  para el camino numérico (evita el pull-all flaggeado en `RESULTADOS.md`).
- **Python-side**: filtro de universo (.isdigit() / 'WE' in s) y el árbol.
- **`limit=1`** se quitó de MC, CF y MP porque el conteo importa para decidir entre
  las ramas.
- **`stock.move.line` fallback**: queda con `lot_id.name = serial` exacto (no se
  propaga la lógica de substring para evitar falsos positivos en "Creación en espera").

### Verificación

- 17 unitarios L1 directos del helper en
  `qa/scaffolding/unit/test_buscar_equipo_por_serial.py` cubriendo cada rama del
  árbol: ruta exacta alfanumérica, 0/1 match numérico, exacta universal (gana en
  cualquier caso), duplicado real, solo numéricas/solo WE, mixto con `len > 4`,
  mixto con `len ≤ 4` (1 WE o varias WE), y filtro de universo (serials fuera
  como `we24000` o `ABC24000` se descartan).
- `test_mc_serial_float_se_normaliza_obs11` actualizado al nuevo shape del dominio
  (de `=` exacto a `like` con `%24000%`).
- Tests existentes con serials alfanuméricos (`SN-XYZ`, `SN-CF`, `SN-E`, etc.) usan
  la ruta exacta intacta — siguen en verde.

```bash
/Users/dacm/we/.venv/bin/python -m pytest qa/scaffolding/component qa/scaffolding/unit -q
# 90 passed
```

### Notas

- Una matching `m.serial_no` no puede estar simultáneamente en `numericas` y `wes`
  (`.isdigit()` excluye letras). Las dos particiones del universo son disjuntas.
- "WE" es **case-sensitive** (mayúsculas), como aparece en los datos reales del QA.
- Para serials puramente numéricos con **ceros a la izquierda** (p. ej. `"00024"`),
  ver la corrección *"Serial numérico con ceros a la izquierda…"* (2026-06-05):
  `normalizar_serial` ahora los elimina en origen, dado que en Odoo no existen S/N
  numéricos que empiecen por 0.

---

## Archivado por proximidad no cierra la mail.activity · 2026-05-29

**Severidad:** Media · **Archivos:** `processor.py` (CF, MP y sub-flujo CI en R) · **Estado:** Corregido

### Síntoma

Tras revisar los registros del ambiente test creados por QA, las solicitudes que la
lógica de proximidad **archiva** (CF, MP y el sub-flujo CI dentro del módulo R) se
quedaban con su `mail.activity` **abierta**. La solicitud aparecía archivada en Odoo
pero la actividad asociada seguía colgando como pendiente.

### Causa raíz

El bucle de archivado de cada módulo solo ejecutaba
`odoo_client.write('maintenance.request', [x], {'archive': True})`. La actividad
asociada (`mail.activity`) no se buscaba ni se cerraba con `action_feedback`. El
patrón ya existía para la solicitud **elegida** después del update (CF L1213-1227,
MP L4003-4017, etc.), pero no se replicó para las archivadas.

### Corrección

Nuevo helper `processor._archivar_y_cerrar_actividad(odoo_client, request_id, ref_nombre)`
que:

1. Escribe `archive=True` sobre la solicitud.
2. Busca su `mail.activity` por `res_model='maintenance.request', res_id=request_id`.
3. Si existe, llama a `action_feedback` para cerrarla.

Cada uno de los 4 bloques de archivado (CF, R-CI con `t='E'`, R-CI con `t='I'`, MP)
se reemplazó por una sola línea que invoca al helper, lo que también elimina la
duplicación del bucle inline en los cuatro módulos.

### Verificación

- Nuevos tests L2 que reflejan el escenario de proximidad y aseguran el cierre de
  la actividad de la solicitud archivada:
  - `test_cf_archivado_cierra_actividad`
  - `test_mp_archivado_cierra_actividad`
- Tests de proximidad existentes (`test_cf_proximidad_archiva_anterior`,
  `test_mp_proximidad_archiva_anterior`) siguen verdes — el helper preserva el
  `write({'archive': True})` que estos validan.

```bash
/Users/dacm/we/.venv/bin/python -m pytest qa/scaffolding/component qa/scaffolding/unit -q
# 73 passed
```

---

## Actualización por proximidad no escribe el técnico · 2026-05-29

**Severidad:** Media · **Archivos:** `processor.py` (CF y MP) · **Estado:** Corregido

### Síntoma

Tras revisar los registros del ambiente test creados por QA, las solicitudes
actualizadas por la rama de **proximidad** (CF y MP, tanto `operativo=Sí` como
`operativo=No`) no quedaban con el **técnico que realizó el trabajo** asignado:
el campo `x_studio_tcnico` no se actualizaba. La fecha de cierre, estado e informe
se escribían correctamente, pero el técnico quedaba vacío o con el valor antiguo.

### Causa raíz

Los dicts de update en esa rama omitían `x_studio_tcnico`:

```python
# CF L1173-1176 (antes)         # CF L1246-1248 (antes)
update_CF = {                    update_CF = {
    'stage_id': 5,                   'stage_id': 3,
    'x_studio_informe': ...,     }
}
# (mismo patrón en MP L3963-3966 y L4036-4038)
```

En cambio, el flujo de **creación** (cuando no había solicitudes previas, p. ej.
CF L1398, MP L3562) sí lo escribía. La omisión solo afectaba a la rama de
actualización por proximidad.

> Nota: el sub-flujo CI dentro de R **no** se modifica: ahí el técnico es Metrocal
> (`x_studio_tcnico = 5118`) por regla de negocio, y eso ya se escribía correctamente.

### Corrección

Se agregó `'x_studio_tcnico': operators[tecnico]` a los 4 dicts de update por
proximidad en CF y MP (Sí/No en cada uno). `operators[tecnico]` es el `res.partner`
mapeado del nombre del técnico resuelto desde Connecteam.

### Verificación

- Nuevos tests L2 que aseguran que la actualización por proximidad escribe el técnico:
  - `test_cf_proximidad_actualiza_tecnico_operativo_si`
  - `test_cf_proximidad_actualiza_tecnico_operativo_no`
  - `test_mp_proximidad_actualiza_tecnico_operativo_si`
  - `test_mp_proximidad_actualiza_tecnico_operativo_no`
- Cada uno verifica que el `write` a la solicitud elegida incluye
  `x_studio_tcnico == 145` (id de "Diego Marchant", técnico del fixture
  `patch_externals`).

```bash
/Users/dacm/we/.venv/bin/python -m pytest qa/scaffolding/component qa/scaffolding/unit -q
# 73 passed
```

---

## OBS-11 — Serial numérico no normalizado antes de la búsqueda exacta · 2026-05-29

**Severidad:** Alta · **Archivos:** `processor.py` (módulos MC, CF, R, I, MP) · **Estado:** Corregido

### Síntoma

Cada módulo resuelve el equipo con una búsqueda **exacta** del serial
(`search_read('maintenance.equipment', [['serial_no', '=', serial_X]])`). Un serial
puramente numérico que pandas infiere como `float` (p.ej. `24000.0`) se buscaba tal
cual contra el campo char `serial_no` (`"24000"`) → no calzaba → el equipo "desaparecía"
aunque existiera y todo el módulo caía al fallback "S/N no encontrado", sin crear ni
actualizar la solicitud. Es el cuello de botella del pipeline: sin match de serial,
nada más ocurre.

### Causa raíz

El bloque "asegurar que el serial pase de float a int" corría **después** de capturar
`serial_X` y solo mutaba el `dict` (`dic_trabajo_X`), no la variable usada en el
`search_read`. No había `.strip()` ni conversión a string. Los serials alfanuméricos
(`24000WE0000221`) se salvaban solo porque nunca entraban a esa conversión.

```python
serial_MC = dic_trabajo_MC['... | N° de serie']   # float 24000.0
# ...
for llave, valor in dic_trabajo_MC.items():        # muta el dict, NO serial_MC
    if isinstance(valor, float):
        dic_trabajo_MC[llave] = int(valor)
# ...
search_read('maintenance.equipment', [['serial_no', '=', serial_MC]])  # busca 24000.0
```

### Corrección

Nuevo helper `processor.normalizar_serial()` que convierte el serial a string limpio
(quita el `.0` de los float enteros y los espacios) y se aplica **en la captura** del
serial en los cinco módulos, antes del `search_read`:

```python
def normalizar_serial(serial):
    if serial is None:
        return serial
    if isinstance(serial, float) and serial.is_integer():
        serial = int(serial)
    return str(serial).strip()

# en cada módulo:
serial_MC = normalizar_serial(dic_trabajo_MC['... | N° de serie'])
```

El bloque float→int del `dict` se conserva: sigue normalizando otras claves
(`dic_trabajo_X['#']`) que se usan más adelante.

### Verificación

- Testigo MC actualizado para exigir el serial normalizado:
  `test_mc_serial_float_se_normaliza_obs11` (antes `..._no_se_normaliza_obs11`, que
  caracterizaba el defecto). Ahora afirma que la búsqueda usa `"24000"` (string).
- Nuevo unitario L1 del helper: `qa/scaffolding/unit/test_normalizar_serial.py`
  (float entero, int, string, alfanumérico, espacios, float no entero, `None`).

```bash
/Users/dacm/we/.venv/bin/python -m pytest \
  qa/scaffolding/unit/test_normalizar_serial.py \
  qa/scaffolding/component/test_process_entrys_mc.py -q
# verde

# Suite completa L1+L2 sin regresiones:
/Users/dacm/we/.venv/bin/python -m pytest qa/scaffolding/component qa/scaffolding/unit -q
# 67 passed
```

### Notas

- El fix normaliza el serial usado también en el informe PDF, el inbox y `detalle_op`,
  lo que es consistente (mismo valor limpio en todas las salidas).
- Un float no entero (p.ej. `24000.5`) conserva los decimales como string (`"24000.5"`);
  no se espera ese caso en serials reales.

---

## OBS-7 — Columnas no únicas en el módulo R · 2026-05-29

**Severidad:** Media · **Archivo:** `processor.py` (módulo R) · **Estado:** Corregido

### Síntoma

En el módulo R, al armar el DataFrame por equipo se disparaba el warning de pandas
`DataFrame columns are not unique, some columns will be omitted` (reproducido por QA:
14 warnings en la corrida del módulo R). Riesgo de que `to_dict()` omitiera columnas
y se tomara el valor equivocado al aplanar.

### Causa raíz

El selector general usaba coincidencia por substring:

```python
filtro_general = f"{i}.2.{equipo} R"
columnas_general = df_trabajo.filter(like=filtro_general).columns.to_list()
filtro_R_E = f"{i}.2.{equipo} R ({t})"
columnas_R_E = df_trabajo.filter(like=filtro_R_E).columns.to_list()
columnas_equipo_R = columnas_general + columnas_R_E
```

Como `"{i}.2.{equipo} R"` es substring de `"{i}.2.{equipo} R (E)"` y `"… R (I)"`,
`columnas_general` ya contenía las columnas del subtipo. Al concatenarlas con
`columnas_R_E` esas columnas quedaban **duplicadas** → etiquetas no únicas →
warning y posible omisión en `to_dict()`.

### Corrección

Selección explícita: las columnas **generales** se filtran por el separador
`R | ` (que no matchea `R (E) |` ni `R (I) |`), y las del subtipo en curso se
agregan aparte. Así no hay etiquetas duplicadas.

```python
filtro_general = f"{i}.2.{equipo} R"
# columnas generales: solo "R | ..." (el separador evita arrastrar "R (E)"/"R (I)")
columnas_general = df_trabajo.filter(like=f"{filtro_general} |").columns.to_list()
columnas_R_E = df_trabajo.filter(like=filtro_R_E).columns.to_list()
columnas_equipo_R = columnas_general + columnas_R_E
```

### Verificación

Prueba relacionada: `qa/scaffolding/component/test_process_entrys_r.py` (7 casos del
módulo R). Ejecutada tratando los `UserWarning` como error para confirmar que el
warning de columnas no únicas desapareció:

```bash
/Users/dacm/we/.venv/bin/python -m pytest \
  qa/scaffolding/component/test_process_entrys_r.py -q -W error::UserWarning
# 7 passed
```

Suite completa L1+L2 sin regresiones:

```bash
/Users/dacm/we/.venv/bin/python -m pytest \
  qa/scaffolding/component qa/scaffolding/unit -q
# 59 passed
```

### Notas

- Fuera de alcance: **OBS-1** (punto de dos dígitos detectado por `col[0]`) sigue
  presente; la detección de prefijo numérico no cambió, para mantener consistencia
  con `process_entrys`.
