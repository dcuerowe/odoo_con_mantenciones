# -*- coding: utf-8 -*-
"""
Muestras de los correos SA-14 (semanal) y SA-16 (carta Gantt mensual)
del Programa de Mantención Preventiva — WE TECHS.

Reproduce EXACTAMENTE las plantillas HTML de PLAN_IMPLEMENTACION.md, pero
tomando los datos del bloque editable de abajo (no de Odoo). Modificá los
datos a mano y volvé a correr:

    /Users/dacm/we/.venv/bin/python generar_muestras.py

Genera, en esta misma carpeta:
    reporte_semanal.html · reporte_mensual.html · index.html (los dos juntos)
"""
import datetime
import os
from datetime import date

# ══════════════════════════════════════════════════════════════════════
#  ░░  DATOS EDITABLES  ░░   (cambiá lo que quieras acá)
# ══════════════════════════════════════════════════════════════════════

# ---- SA-14 · REPORTE SEMANAL ------------------------------------------
# Una entrada por ocurrencia (un punto en una fecha).
#   estado: "draft" | "scheduled" | "in_progress"
#   equipos: lista de (nombre_equipo, codigo_OT).  OT puede ir en "" si no hay.
SEMANAL_TITULO = "Mantención de la próxima semana"
SEMANAL = [
    {
        "fecha": date(2026, 7, 13), "punto": "Río Maipo — Estación Norte",
        "estado": "scheduled", "responsable": "María González", "tecnico": "Pedro Rojas",
        "equipos": [
            ("Sonda multiparamétrica YSI EXO2", "PMP-0041 | Sonda EXO2"),
            ("Sensor de nivel VEGAPULS 61",     "PMP-0041 | Nivel VEGAPULS"),
            ("Caudalímetro Doppler SonTek-IQ",  "PMP-0041 | Caudalímetro"),
        ],
    },
    {
        "fecha": date(2026, 7, 13), "punto": "Planta Sur — Descarga 2",
        "estado": "scheduled", "responsable": "Ana Fuentes", "tecnico": "Luis Cárcamo",
        "equipos": [
            ("Transmisor de pH Hach SC200", "PMP-0042 | pH SC200"),
            ("Turbidímetro Hach TU5300",    "PMP-0042 | Turbidímetro"),
        ],
    },
    {
        "fecha": date(2026, 7, 14), "punto": "Embalse El Yeso — Toma",
        "estado": "in_progress", "responsable": "María González", "tecnico": "Pedro Rojas",
        "equipos": [
            ("Estación meteorológica Vaisala WXT536", "PMP-0043 | Estación Vaisala"),
            ("Barómetro Solinst Levelogger",          "PMP-0043 | Barómetro"),
        ],
    },
    {
        "fecha": date(2026, 7, 16), "punto": "Canal Las Mercedes — PK 12",
        "estado": "scheduled", "responsable": "Ana Fuentes", "tecnico": "Luis Cárcamo",
        "equipos": [
            ("Sonda multiparamétrica YSI EXO2", "PMP-0044 | Sonda EXO2"),
            ("Muestreador automático ISCO 6712", "PMP-0044 | Muestreador ISCO"),
            ("Sensor de oxígeno disuelto LDO",   "PMP-0044 | Oxígeno LDO"),
            ("Turbidímetro Hach TU5300",         "PMP-0044 | Turbidímetro"),
        ],
    },
    {
        "fecha": date(2026, 7, 17), "punto": "Planta Sur — Descarga 2",
        "estado": "draft", "responsable": "Ana Fuentes", "tecnico": "Luis Cárcamo",
        "equipos": [
            ("Muestreador automático ISCO 6712", ""),
        ],
    },
]

# ---- SA-16 · REPORTE MENSUAL (carta Gantt) ----------------------------
# Cualquier día del mes objetivo (define mes/año y nº de días).
MENSUAL_MES = date(2026, 7, 1)
# Carga: (punto, día_del_mes, nº_de_solicitudes_ese_día)
MENSUAL_CARGA = [
    ("Río Maipo — Estación Norte", 3, 3),  ("Río Maipo — Estación Norte", 17, 3),
    ("Planta Sur — Descarga 2",    5, 2),  ("Planta Sur — Descarga 2",    19, 2),
    ("Planta Sur — Descarga 2",   31, 1),
    ("Embalse El Yeso — Toma",    10, 2),  ("Embalse El Yeso — Toma",     24, 2),
    ("Canal Las Mercedes — PK 12", 8, 4),  ("Canal Las Mercedes — PK 12", 22, 4),
    ("Río Aconcagua — Puente",    14, 2),  ("Río Aconcagua — Puente",     28, 1),
    ("Bío-Bío — Captación 3",      7, 1),  ("Bío-Bío — Captación 3",      21, 2),
]

# ══════════════════════════════════════════════════════════════════════
#  ░░  MOTOR DE RENDER  ░░   (no necesitás tocar de acá para abajo)
# ══════════════════════════════════════════════════════════════════════

# Paleta oficial WE TECHS (idéntica a la del plan).
ORANGE, ORANGE2, INK, GREY = '#F26522', '#F47F47', '#2B2B2D', '#5A5B5D'
GMED, LINE, BG, PEACH, WHITE = '#939598', '#E4E5E6', '#F6F7F8', '#FDE5DA', '#FFFFFF'
FONT = "'Lexend Deca',Arial,Helvetica,sans-serif"
DIAS = ['LUNES', 'MARTES', 'MIÉRCOLES', 'JUEVES', 'VIERNES', 'SÁBADO', 'DOMINGO']
MESES_MIN = ['', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
             'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
MESES_MAY = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
             'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
INI = ['L', 'M', 'M', 'J', 'V', 'S', 'D']
EST = {'draft': ('Borrador', GMED), 'scheduled': ('Programada', ORANGE),
       'in_progress': ('En progreso', '#0097A7')}


def build_weekly():
    today = datetime.date.today()
    fechas = [o["fecha"] for o in SEMANAL]
    fmin = min(fechas)
    base_mon = fmin - datetime.timedelta(days=fmin.weekday())   # lunes de esa semana
    next_mon, next_sun = base_mon, base_mon + datetime.timedelta(days=6)
    DIA_AB = ['LUN', 'MAR', 'MIÉ', 'JUE', 'VIE', 'SÁB', 'DOM']

    por_dia = {}
    for o in SEMANAL:
        por_dia.setdefault(o["fecha"], []).append(o)

    # Semana laboral: Lun-Vie; sábado/domingo solo si tienen trabajo.
    dias = [base_mon + datetime.timedelta(days=i) for i in range(5)]
    for extra in (5, 6):
        d = base_mon + datetime.timedelta(days=extra)
        if por_dia.get(d):
            dias.append(d)

    total_eq = sum(len(o["equipos"]) for o in SEMANAL)
    puntos_set = {o["punto"] for o in SEMANAL}

    # --- Calendario: una columna por día laboral, tarjetas dentro ---
    cols = ""
    for d in dias:
        head_bg = PEACH if d.weekday() >= 5 else BG   # fin de semana sombreado
        ocs = por_dia.get(d, [])
        if ocs:
            cuerpo = ""
            for o in ocs:
                est_lbl, est_col = EST.get(o["estado"], (o["estado"], GMED))
                eq_html = "".join(
                    f'<div style="font:400 9px {FONT};color:{GREY};line-height:12.5px;padding:1.5px 0;">'
                    f'<span style="color:{ORANGE};font-weight:700;">·</span>&nbsp;{nombre}</div>'
                    for (nombre, _ot) in o["equipos"]) or (
                    f'<div style="font:italic 400 9px {FONT};color:{GMED};">Sin equipos</div>')
                cuerpo += (
                    f'<table width="100%" cellpadding="0" cellspacing="0" role="presentation" '
                    f'style="border:1px solid {LINE};border-top:3px solid {est_col};background:{WHITE};margin:0 0 7px;">'
                    f'<tr><td style="padding:7px 8px 8px;">'
                    f'<div style="font:700 10px {FONT};color:{INK};line-height:13px;">{o["punto"] or "Punto sin nombre"}</div>'
                    f'<div style="padding:5px 0 0;"><span style="display:inline-block;padding:2px 7px;border-radius:9px;'
                    f'background:{est_col};color:{WHITE};font:700 8px {FONT};letter-spacing:.3px;">{est_lbl.upper()}</span></div>'
                    f'<div style="padding:7px 0 3px;font:700 8px {FONT};color:{ORANGE};letter-spacing:.4px;">EQUIPOS ({len(o["equipos"])})</div>'
                    f'{eq_html}</td></tr></table>')
        else:
            cuerpo = (f'<div style="padding:16px 4px;text-align:center;font:400 9px {FONT};'
                      f'color:{GMED};">Sin trabajo</div>')
        cols += (
            f'<td width="126" style="width:126px;padding:0 3px;vertical-align:top;">'
            f'<table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="border:1px solid {LINE};background:{WHITE};">'
            f'<tr><td style="background:{head_bg};padding:6px 8px;border-bottom:1px solid {LINE};white-space:nowrap;">'
            f'<span style="font:700 9px {FONT};color:{GMED};letter-spacing:.5px;">{DIA_AB[d.weekday()]}</span>'
            f'&nbsp;<span style="font:700 13px {FONT};color:{INK};">{d.day}</span></td></tr>'
            f'<tr><td style="padding:7px 5px;vertical-align:top;">{cuerpo}</td></tr>'
            f'</table></td>')

    calendario = (f'<table cellpadding="0" cellspacing="0" role="presentation" '
                  f'style="table-layout:fixed;width:{len(dias) * 132}px;border-collapse:collapse;"><tr>{cols}</tr></table>')

    rango = (f'Semana del {next_mon.day} de {MESES_MIN[next_mon.month]} al '
             f'{next_sun.day} de {MESES_MIN[next_sun.month]} de {next_sun.year}')
    chip = (
        f'<table cellpadding="0" cellspacing="0" role="presentation" style="background:{ORANGE};border-radius:6px;"><tr>'
        f'<td style="padding:9px 18px;font:400 9px {FONT};color:{PEACH};letter-spacing:.6px;">OCURRENCIAS<br>'
        f'<span style="font:700 16px {FONT};color:{WHITE};">{len(SEMANAL)}</span></td>'
        f'<td style="border-left:1px solid {ORANGE2};padding:9px 18px;font:400 9px {FONT};color:{PEACH};letter-spacing:.6px;">PUNTOS<br>'
        f'<span style="font:700 16px {FONT};color:{WHITE};">{len(puntos_set)}</span></td>'
        f'<td style="border-left:1px solid {ORANGE2};padding:9px 18px;font:400 9px {FONT};color:{PEACH};letter-spacing:.6px;">EQUIPOS<br>'
        f'<span style="font:700 16px {FONT};color:{WHITE};">{total_eq}</span></td>'
        f'</tr></table>')

    return f'''<div style="margin:0;padding:24px 12px;background:{BG};">
<table align="center" width="700" cellpadding="0" cellspacing="0" role="presentation" style="width:700px;max-width:700px;margin:0 auto;background:{WHITE};">
<tr><td style="padding:26px 20px 30px;">
<table width="100%" cellpadding="0" cellspacing="0" role="presentation"><tr>
<td style="font:700 18px {FONT};color:{INK};letter-spacing:2px;">WE&nbsp;TECHS</td>
<td align="right" style="font:700 9px {FONT};color:{ORANGE};letter-spacing:1px;text-transform:uppercase;line-height:14px;">Reporte semanal<br>
<span style="font-weight:400;color:{GMED};">Programa de Mantención Preventiva</span></td>
</tr></table>
<div style="height:3px;width:118px;background:{ORANGE};font-size:0;line-height:0;">&nbsp;</div>
<div style="height:2px;background:{INK};font-size:0;line-height:0;">&nbsp;</div>
<div style="font:700 9px {FONT};color:{ORANGE};letter-spacing:1.5px;text-transform:uppercase;padding:20px 0 0;">Calendario semanal</div>
<div style="font:700 24px {FONT};color:{INK};padding:5px 0 0;">{SEMANAL_TITULO}</div>
<div style="font:400 13px {FONT};color:{GREY};padding:6px 0 0;">{rango}</div>
<div style="padding:16px 0 2px;">{chip}</div>
<div style="overflow-x:auto;padding:20px 0 2px;">{calendario}</div>
<div style="border-top:1px solid {LINE};margin:22px 0 0;padding:12px 0 0;font:400 10px {FONT};color:{GMED};line-height:15px;">
Programa de Mantención Preventiva — WE TECHS · Generado automáticamente el {today.day}/{today.month}/{today.year}. Correo automático, no responder.</div>
</td></tr></table></div>'''


def build_monthly():
    today = datetime.date.today()
    first = MENSUAL_MES.replace(day=1)
    if first.month == 12:
        nxt = first.replace(year=first.year + 1, month=1)
    else:
        nxt = first.replace(month=first.month + 1)
    n_dias = (nxt - first).days

    puntos, orden, celdas, tot_dia = set(), [], {}, {}
    for punto, d, c in MENSUAL_CARGA:
        if punto not in celdas:
            celdas[punto] = {}
            orden.append(punto)
        celdas[punto][d] = celdas[punto].get(d, 0) + c
        tot_dia[d] = tot_dia.get(d, 0) + c
    n_solicitudes = sum(tot_dia.values())
    finde = {d for d in range(1, n_dias + 1)
             if datetime.date(first.year, first.month, d).weekday() >= 5}
    CW = 19

    th = (f'<td style="padding:6px 12px;font:700 9px {FONT};color:{GMED};letter-spacing:.5px;'
          f'border-bottom:2px solid {INK};text-align:left;white-space:nowrap;">PUNTO DE MONITOREO</td>')
    for d in range(1, n_dias + 1):
        wk = d in finde
        th += (f'<td width="{CW}" style="width:{CW}px;padding:3px 0 5px;text-align:center;'
               f'font:700 9px {FONT};color:{INK if wk else GMED};border-bottom:2px solid {INK};'
               f'background:{PEACH if wk else WHITE};">{d}<br>'
               f'<span style="font-weight:400;font-size:7px;color:{GMED};">'
               f'{INI[datetime.date(first.year, first.month, d).weekday()]}</span></td>')
    th += (f'<td style="padding:6px 8px;font:700 9px {FONT};color:{INK};letter-spacing:.5px;'
           f'border-bottom:2px solid {INK};text-align:center;">TOT</td>')

    filas = ""
    for i, punto in enumerate(orden):
        rbg = WHITE if i % 2 == 0 else BG
        tot_p = sum(celdas[punto].values())
        celdas_html = ""
        for d in range(1, n_dias + 1):
            c = celdas[punto].get(d, 0)
            if c:
                celdas_html += (f'<td width="{CW}" style="width:{CW}px;padding:2px;text-align:center;'
                                f'border-right:1px solid {LINE};border-bottom:1px solid {LINE};background:{rbg};">'
                                f'<span style="display:block;background:{ORANGE};color:{WHITE};'
                                f'font:700 10px {FONT};border-radius:3px;padding:4px 0;">{c}</span></td>')
            else:
                celdas_html += (f'<td width="{CW}" style="width:{CW}px;border-right:1px solid {LINE};'
                                f'border-bottom:1px solid {LINE};background:{PEACH if d in finde else rbg};">&nbsp;</td>')
        filas += (f'<tr><td style="padding:7px 12px;font:600 11px {FONT};color:{INK};'
                  f'border-bottom:1px solid {LINE};background:{rbg};white-space:nowrap;">'
                  f'{punto or "Punto sin nombre"}</td>{celdas_html}'
                  f'<td style="padding:7px 8px;text-align:center;font:700 11px {FONT};color:{ORANGE};'
                  f'border-bottom:1px solid {LINE};background:{rbg};">{tot_p}</td></tr>')

    foot = (f'<td style="padding:7px 12px;font:700 9px {FONT};color:{GMED};letter-spacing:.5px;'
            f'border-top:2px solid {INK};">CARGA DIARIA</td>')
    for d in range(1, n_dias + 1):
        v = tot_dia.get(d, 0)
        foot += (f'<td width="{CW}" style="width:{CW}px;padding:4px 0;text-align:center;'
                 f'font:700 9px {FONT};color:{INK if v else LINE};border-top:2px solid {INK};'
                 f'background:{PEACH if d in finde else WHITE};">{v or "·"}</td>')
    foot += (f'<td style="padding:4px 8px;text-align:center;font:700 10px {FONT};color:{INK};'
             f'border-top:2px solid {INK};">{n_solicitudes}</td>')

    gantt = (f'<table cellpadding="0" cellspacing="0" role="presentation" '
             f'style="border-collapse:collapse;border:1px solid {LINE};">'
             f'<tr>{th}</tr>{filas}<tr>{foot}</tr></table>')

    chip = (
        f'<table cellpadding="0" cellspacing="0" role="presentation" style="background:{ORANGE};border-radius:6px;"><tr>'
        f'<td style="padding:9px 18px;font:400 9px {FONT};color:{PEACH};letter-spacing:.6px;">PUNTOS<br>'
        f'<span style="font:700 16px {FONT};color:{WHITE};">{len(orden)}</span></td>'
        f'<td style="border-left:1px solid {ORANGE2};padding:9px 18px;font:400 9px {FONT};color:{PEACH};letter-spacing:.6px;">SOLICITUDES<br>'
        f'<span style="font:700 16px {FONT};color:{WHITE};">{n_solicitudes}</span></td>'
        f'<td style="border-left:1px solid {ORANGE2};padding:9px 18px;font:400 9px {FONT};color:{PEACH};letter-spacing:.6px;">DÍAS ACTIVOS<br>'
        f'<span style="font:700 16px {FONT};color:{WHITE};">{len(tot_dia)}</span></td>'
        f'</tr></table>')

    return f'''<div style="margin:0;padding:24px 12px;background:{BG};">
<table align="center" width="720" cellpadding="0" cellspacing="0" role="presentation" style="width:720px;max-width:720px;margin:0 auto;background:{WHITE};">
<tr><td style="padding:26px 30px 30px;">
<table width="100%" cellpadding="0" cellspacing="0" role="presentation"><tr>
<td style="font:700 18px {FONT};color:{INK};letter-spacing:2px;">WE&nbsp;TECHS</td>
<td align="right" style="font:700 9px {FONT};color:{ORANGE};letter-spacing:1px;text-transform:uppercase;line-height:14px;">Reporte mensual<br>
<span style="font-weight:400;color:{GMED};">Programa de Mantención Preventiva</span></td>
</tr></table>
<div style="height:3px;width:118px;background:{ORANGE};font-size:0;line-height:0;">&nbsp;</div>
<div style="height:2px;background:{INK};font-size:0;line-height:0;">&nbsp;</div>
<div style="font:700 9px {FONT};color:{ORANGE};letter-spacing:1.5px;text-transform:uppercase;padding:20px 0 0;">Carta Gantt mensual</div>
<div style="font:700 24px {FONT};color:{INK};padding:5px 0 0;">{MESES_MAY[first.month]} {first.year}</div>
<div style="font:400 13px {FONT};color:{GREY};padding:6px 0 0;">Distribución de la mantención preventiva por punto de monitoreo</div>
<div style="padding:16px 0 2px;">{chip}</div>
<div style="overflow-x:auto;padding:20px 0 0;">{gantt}</div>
<div style="padding:12px 0 0;font:400 10px {FONT};color:{GMED};line-height:15px;">
<span style="display:inline-block;width:9px;height:9px;background:{ORANGE};border-radius:2px;vertical-align:middle;"></span>&nbsp;el número indica las solicitudes programadas ese día en el punto&nbsp;&nbsp;·&nbsp;&nbsp;fin de semana sombreado.</div>
<div style="border-top:1px solid {LINE};margin:22px 0 0;padding:12px 0 0;font:400 10px {FONT};color:{GMED};line-height:15px;">
Programa de Mantención Preventiva — WE TECHS · Generado automáticamente el {today.day}/{today.month}/{today.year}. Correo automático, no responder.</div>
</td></tr></table></div>'''


def doc(titulo, body):
    return (f"<!doctype html><html lang='es'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<title>{titulo}</title></head>"
            f"<body style='margin:0;background:{BG};'>{body}</body></html>")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    semanal, mensual = build_weekly(), build_monthly()
    sep = ("<div style=\"max-width:720px;margin:0 auto;padding:26px 12px 6px;"
           "font:700 11px 'Lexend Deca',Arial,sans-serif;color:#939598;letter-spacing:1px;"
           "text-transform:uppercase;\">%s</div>")
    salidas = {
        "reporte_semanal.html": doc("PMP · Reporte semanal — WE TECHS", semanal),
        "reporte_mensual.html": doc("PMP · Reporte mensual — WE TECHS", mensual),
        "index.html": doc(
            "PMP · Muestras de reportes — WE TECHS",
            (sep % "SA-14 · Reporte semanal") + semanal
            + (sep % "SA-16 · Reporte mensual — carta Gantt") + mensual),
    }
    for nombre, html in salidas.items():
        with open(os.path.join(here, nombre), "w", encoding="utf-8") as f:
            f.write(html)
        print("escrito:", nombre)


if __name__ == "__main__":
    main()
