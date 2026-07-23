# Muestras de reportes — PMP (WE TECHS)

Vista previa editable de los correos que emiten las acciones programadas del
Programa de Mantención Preventiva:

- **SA-14 — Reporte semanal** → calendario semanal: una columna por día, con tarjetas por solicitud (punto de monitoreo, estado, equipos a intervenir).
- **SA-16 — Reporte mensual** → carta Gantt (puntos × días del mes).

Reproduce **exactamente** las plantillas HTML de `PLAN_IMPLEMENTACION.md`, pero
con datos de ejemplo para poder ajustarlos a mano.

## Cómo modificar los datos

1. Abrí `generar_muestras.py` y editá el bloque **`DATOS EDITABLES`** de arriba:
   - `SEMANAL` — una entrada por ocurrencia (`fecha`, `punto`, `estado`,
     `responsable`, `tecnico`, `equipos`). `estado` ∈ `draft` · `scheduled` · `in_progress`.
     Cada equipo es una tupla `(nombre, codigo_OT)`; la OT puede ir en `""`.
   - `MENSUAL_MES` — cualquier día del mes objetivo (define mes/año/nº de días).
   - `MENSUAL_CARGA` — tuplas `(punto, día_del_mes, nº_de_solicitudes)`.
2. Regenerá:

   ```bash
   /Users/dacm/we/.venv/bin/python generar_muestras.py
   ```

3. Abrí el resultado:

   ```bash
   open index.html          # los dos reportes juntos
   # o reporte_semanal.html / reporte_mensual.html por separado
   ```

## Archivos

| Archivo | Qué es |
|---|---|
| `generar_muestras.py` | Generador + **datos editables** (editá acá) |
| `reporte_semanal.html` | Salida renderizada del SA-14 |
| `reporte_mensual.html` | Salida renderizada del SA-16 (carta Gantt) |
| `index.html` | Los dos reportes apilados |

## Notas

- La tipografía **Lexend Deca** cae a **Arial** en la mayoría de clientes de correo
  (no se pueden embeber `.ttf` de forma fiable). La muestra refleja ese comportamiento real.
- El HTML usa **estilos inline** + `<table>` para sobrevivir a Outlook/Gmail;
  `border-radius` degrada a esquina recta en Outlook desktop (solo cosmético).
- Si querés editar el HTML directamente (para cambios de texto puntuales) también
  podés; pero para cambios de estructura conviene editar los datos y regenerar.
