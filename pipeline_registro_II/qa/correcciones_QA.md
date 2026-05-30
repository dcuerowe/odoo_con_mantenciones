# Correcciones QA

Bitácora de correcciones aplicadas al pipeline a partir de las observaciones de QA
(`OBS-*` definidas en [`RESULTADOS.md`](./RESULTADOS.md) § Debilidades). Cada entrada
documenta el defecto, la causa, el cambio y la prueba que lo respalda.

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
