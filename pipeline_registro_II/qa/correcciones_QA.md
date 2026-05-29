# Correcciones QA

Bitácora de correcciones aplicadas al pipeline a partir de las observaciones de QA
(`OBS-*` definidas en [`RESULTADOS.md`](./RESULTADOS.md) § Debilidades). Cada entrada
documenta el defecto, la causa, el cambio y la prueba que lo respalda.

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
