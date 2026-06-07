#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador de Informes de Trabajo  ·  WE TECHS
------------------------------------------------------------------
Construye el PDF con la identidad visual de WE TECHS a partir de los
datos de una Orden de Trabajo (OT).

El punto de entrada `informe_pdf_profesional(...)` conserva la firma que
usan `processor.py` (5 llamadas) y `pdf_generator.py`, de modo que el
resto del pipeline no necesita cambios. Internamente arma el diccionario
`datos` + la lista `fotos` y delega en el layout de marca.

Adaptaciones respecto al diseño base de referencia:
  - El logo se descarga desde `LOGO_URL` (config) — no hay asset local.
  - Si no están los .ttf de Lexend Deca en ./fonts cae a Helvetica.
  - Las fotos llegan como URLs (Connecteam); se descargan a memoria.
  - Devuelve un `io.BytesIO` (no escribe a disco) para adjuntarlo a Odoo.
"""

import io
import os
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, StyleSheet1
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table,
    TableStyle, Image, Flowable, PageBreak,
)
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from PIL import Image as PILImage, ImageOps

from config import LOGO_URL


# ----------------------------------------------------------------------
# TIPOGRAFÍA  ·  Lexend Deca
# ----------------------------------------------------------------------
_FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")


def _registrar_fuentes():
    """Registra Lexend Deca (Regular/SemiBold/Bold). Si no están los .ttf,
    cae a Helvetica para no romper la generación."""
    try:
        pdfmetrics.registerFont(TTFont("LexendDeca",
                                       os.path.join(_FONTS, "LexendDeca-Regular.ttf")))
        pdfmetrics.registerFont(TTFont("LexendDeca-SemiBold",
                                       os.path.join(_FONTS, "LexendDeca-SemiBold.ttf")))
        pdfmetrics.registerFont(TTFont("LexendDeca-Bold",
                                       os.path.join(_FONTS, "LexendDeca-Bold.ttf")))
        pdfmetrics.registerFontFamily(
            "LexendDeca", normal="LexendDeca", bold="LexendDeca-Bold",
            italic="LexendDeca", boldItalic="LexendDeca-Bold")
        return "LexendDeca", "LexendDeca-SemiBold", "LexendDeca-Bold"
    except Exception:
        return "Helvetica", "Helvetica-Bold", "Helvetica-Bold"


FUENTE, FUENTE_MED, FUENTE_BOLD = _registrar_fuentes()

# ----------------------------------------------------------------------
# PALETA DE MARCA  ·  WE TECHS
# ----------------------------------------------------------------------
NARANJA      = colors.HexColor("#F26522")   # primario
NARANJA_MED  = colors.HexColor("#F47F47")
NARANJA_CLARO= colors.HexColor("#F9B291")
DURAZNO      = colors.HexColor("#FDE5DA")   # fondo suave
TEAL         = colors.HexColor("#0097A7")   # acento secundario
TINTA        = colors.HexColor("#2B2B2D")   # texto principal
GRIS         = colors.HexColor("#5A5B5D")   # texto secundario
GRIS_MED     = colors.HexColor("#939598")   # texto tenue / labels
GRIS_LINEA   = colors.HexColor("#E4E5E6")   # líneas / bordes
GRIS_FONDO   = colors.HexColor("#F6F7F8")   # relleno tarjetas
BLANCO       = colors.white

MARGEN       = 18 * mm
ANCHO_PAGINA, ALTO_PAGINA = A4
ANCHO_UTIL   = ANCHO_PAGINA - 2 * MARGEN
INSET_FICHA  = 0                            # caja de detalle a ancho completo (al margen)
ANCHO_FICHA  = ANCHO_UTIL - 2 * INSET_FICHA


# ----------------------------------------------------------------------
# LOGO  ·  descargado desde LOGO_URL (cacheado en memoria)
# ----------------------------------------------------------------------
_LOGO_CACHE = {"reader": None, "ratio": None, "intentado": False}


def _logo_reader():
    """Descarga el logo una sola vez y devuelve (ImageReader, alto/ancho).
    Si falla, devuelve (None, None) y el marco se dibuja sin logo."""
    if _LOGO_CACHE["intentado"]:
        return _LOGO_CACHE["reader"], _LOGO_CACHE["ratio"]
    _LOGO_CACHE["intentado"] = True
    try:
        resp = requests.get(LOGO_URL, timeout=10)
        resp.raise_for_status()
        data = io.BytesIO(resp.content)
        reader = ImageReader(data)
        w, h = reader.getSize()
        _LOGO_CACHE["reader"] = reader
        _LOGO_CACHE["ratio"] = (h / w) if w else 0.78
    except Exception as e:
        print(f"Error al cargar el logo desde la URL: {e}")
        _LOGO_CACHE["reader"] = None
        _LOGO_CACHE["ratio"] = None
    return _LOGO_CACHE["reader"], _LOGO_CACHE["ratio"]


# ----------------------------------------------------------------------
# ESTILOS DE TEXTO
# ----------------------------------------------------------------------
def construir_estilos():
    ss = StyleSheet1()
    ss.add(ParagraphStyle("Titulo", fontName=FUENTE_MED, fontSize=20,
                           leading=26, textColor=TINTA, spaceAfter=2))
    ss.add(ParagraphStyle("Subtitulo", fontName=FUENTE, fontSize=13.5,
                           leading=17, textColor=GRIS, spaceAfter=0))
    ss.add(ParagraphStyle("Intro", fontName=FUENTE, fontSize=9.5,
                           leading=14.5, textColor=GRIS))
    ss.add(ParagraphStyle("Seccion", fontName=FUENTE_BOLD, fontSize=12.5,
                           leading=15, textColor=TINTA, spaceBefore=2,
                           spaceAfter=2))
    ss.add(ParagraphStyle("Eyebrow", fontName=FUENTE_MED, fontSize=8.5,
                           leading=11, textColor=NARANJA, spaceAfter=3))
    ss.add(ParagraphStyle("Label", fontName=FUENTE_BOLD, fontSize=6.8,
                           leading=9, textColor=GRIS_MED))
    ss.add(ParagraphStyle("Valor", fontName=FUENTE, fontSize=9.2,
                           leading=11.5, textColor=TINTA))
    ss.add(ParagraphStyle("ValorEq", fontName=FUENTE_BOLD, fontSize=9.2,
                           leading=11.5, textColor=TINTA))
    ss.add(ParagraphStyle("ObsLabel", fontName=FUENTE_BOLD, fontSize=7,
                           leading=10, textColor=NARANJA, spaceAfter=2))
    ss.add(ParagraphStyle("Obs", fontName=FUENTE, fontSize=8.8,
                           leading=12.8, textColor=GRIS, alignment=TA_JUSTIFY))
    ss.add(ParagraphStyle("Cap", fontName=FUENTE_BOLD, fontSize=8.5,
                           leading=11, textColor=TINTA))
    ss.add(ParagraphStyle("CapSub", fontName=FUENTE, fontSize=7.8,
                           leading=10.5, textColor=GRIS_MED))
    ss.add(ParagraphStyle("Chip", fontName=FUENTE_BOLD, fontSize=9,
                           leading=11, textColor=BLANCO))
    return ss


STYLES = construir_estilos()


# ----------------------------------------------------------------------
# FLOWABLES PERSONALIZADOS
# ----------------------------------------------------------------------
class TituloSeccion(Flowable):
    """Encabezado de sección: punto naranja + título (motivo circular de marca)."""
    def __init__(self, texto, ancho=ANCHO_UTIL):
        super().__init__()
        self.texto = texto
        self.ancho = ancho
        self.height = 17

    def wrap(self, *a):
        return self.ancho, self.height

    def draw(self):
        c = self.canv
        c.setFillColor(NARANJA)
        c.circle(4, 6, 4, fill=1, stroke=0)
        c.setFillColor(BLANCO)
        c.circle(4, 6, 1.6, fill=1, stroke=0)
        c.setFillColor(TINTA)
        c.setFont(FUENTE_MED, 12.5)
        c.drawString(15, 2.5, self.texto)


class Chip(Flowable):
    """Etiqueta tipo 'chip' naranja para destacar un dato clave (p. ej. tipo de trabajo)."""
    def __init__(self, etiqueta, valor):
        super().__init__()
        self.etiqueta = etiqueta
        self.valor = valor
        self.height = 22

    def wrap(self, *a):
        return ANCHO_UTIL, self.height

    def draw(self):
        c = self.canv
        pad = 9
        c.setFont(FUENTE_BOLD, 7.5)
        w_lab = stringWidth(self.etiqueta.upper(), FUENTE_BOLD, 7.5)
        c.setFont(FUENTE_BOLD, 10)
        w_val = stringWidth(self.valor, FUENTE_BOLD, 10)
        total = w_lab + w_val + pad * 3
        c.setFillColor(NARANJA)
        c.roundRect(0, 0, total, 20, 10, fill=1, stroke=0)
        c.setFillColor(colors.Color(1, 1, 1, 0.85))
        c.setFont(FUENTE_BOLD, 7.5)
        c.drawString(pad, 6.5, self.etiqueta.upper())
        c.setFillColor(BLANCO)
        c.setFont(FUENTE_BOLD, 10)
        c.drawString(pad + w_lab + pad, 6, self.valor)


# ----------------------------------------------------------------------
# CABECERA Y PIE (en cada página)
# ----------------------------------------------------------------------
def _dibujar_marco(canv, doc):
    canv.saveState()

    # ---- Cabecera ----
    top = ALTO_PAGINA - MARGEN
    # logo (descargado desde LOGO_URL)
    reader, ratio = _logo_reader()
    if reader is not None:
        lw = 34 * mm
        lh = lw * (ratio or 0.78)
        canv.drawImage(reader, MARGEN, top - lh + 4, width=lw, height=lh,
                       mask="auto", preserveAspectRatio=True)
    # meta a la derecha (no bold: usa el peso medio)
    canv.setFont(FUENTE_MED, 8.5)
    canv.setFillColor(NARANJA)
    canv.drawRightString(ANCHO_PAGINA - MARGEN, top - 4,
                         "INFORME DE TRABAJOS")
    canv.setFont(FUENTE, 7.5)
    canv.setFillColor(GRIS_MED)
    canv.drawRightString(ANCHO_PAGINA - MARGEN, top - 15,
                         doc.meta.get("ref", ""))
    # regla fina (sello de marca)
    y_linea = top - 22 * mm
    canv.setStrokeColor(TINTA)
    canv.setLineWidth(1.1)
    canv.line(MARGEN, y_linea, ANCHO_PAGINA - MARGEN, y_linea)
    canv.setStrokeColor(NARANJA)
    canv.setLineWidth(1.1)
    canv.line(MARGEN, y_linea, MARGEN + 38 * mm, y_linea)

    # ---- Pie ----
    yb = MARGEN - 4
    canv.setStrokeColor(GRIS_LINEA)
    canv.setLineWidth(0.6)
    canv.line(MARGEN, yb + 10, ANCHO_PAGINA - MARGEN, yb + 10)
    canv.setFont(FUENTE, 7)
    canv.setFillColor(GRIS_MED)
    canv.drawString(MARGEN, yb, "Documento generado automáticamente · "
                    + doc.meta.get("proyecto", ""))
    canv.setFont(FUENTE, 7)
    canv.setFillColor(GRIS)
    canv.drawRightString(ANCHO_PAGINA - MARGEN, yb, f"Página {doc.page}")
    canv.restoreState()


# ----------------------------------------------------------------------
# COMPONENTES DE CONTENIDO
# ----------------------------------------------------------------------
def _es_vacio(texto):
    return (texto or "").strip().lower() in ("", "nan", "none", "n/a", "-")


def ficha_servicio(datos):
    """UNA sola estructura compacta: datos del servicio + observaciones."""

    # --- Grilla de datos (compacta, 2 columnas) ---
    campos = [
        ("OT", datos.get("ot", "—"), False),
        ("Fecha de realización", datos.get("fecha", "—"), False),
        ("Técnico responsable", datos.get("tecnico", "—"), False),
        ("Cliente", datos.get("cliente", "—"), False),
        ("Proyecto", datos.get("proyecto", "—"), False),
    ]
    # El alcance solo se incluye cuando el módulo entrega uno real
    # (MC, MP y R-Intercambio pasan alcance=False).
    if not _es_vacio(str(datos.get("alcance") or "")) and datos.get("alcance") is not False:
        campos.append(("Alcance", datos.get("alcance"), False))
    campos += [
        ("Equipo / instrumento", datos.get("equipo", "—"), False),
        ("Modelo", datos.get("modelo", "—"), False),
        ("N° de serie", datos.get("serie", "—"), False),
    ]
    # Relleno para que la grilla quede en filas pares
    if len(campos) % 2:
        campos.append(("", "", False))

    def celda(label, valor, destacar):
        if not label:
            return Table([[Spacer(1, 1)]], colWidths=[ANCHO_FICHA / 2 - 18])
        estilo_val = "ValorEq" if destacar else "Valor"
        inner = Table(
            [[Paragraph(label.upper(), STYLES["Label"])],
             [Paragraph(str(valor), STYLES[estilo_val])]],
            colWidths=[ANCHO_FICHA / 2 - 18])
        inner.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (0, 0), 0),
            ("TOPPADDING", (0, 1), (0, 1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        return inner

    filas = []
    for i in range(0, len(campos), 2):
        filas.append([celda(*campos[i]), celda(*campos[i + 1])])
    grilla = Table(filas, colWidths=[ANCHO_FICHA / 2, ANCHO_FICHA / 2])
    grilla.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, 0), 0),
        ("TOPPADDING", (0, 1), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    # --- Bloque de observaciones ---
    def obs(label, texto):
        if _es_vacio(texto):
            cuerpo = Paragraph(
                '<i>Sin observaciones registradas.</i>',
                ParagraphStyle("ObsVacia", parent=STYLES["Obs"],
                               textColor=GRIS_MED))
        else:
            cuerpo = Paragraph(str(texto).strip(), STYLES["Obs"])
        return [Paragraph(label.upper(), STYLES["ObsLabel"]), cuerpo]

    obs_rows = obs("Observaciones al equipo", datos.get("obs_equipo"))
    obs_rows += [Spacer(1, 8)]
    obs_rows += obs("Observaciones generales", datos.get("obs_generales"))
    obs_tabla = Table([[x] for x in obs_rows], colWidths=[ANCHO_FICHA - 36])
    obs_tabla.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    # --- Contenedor único ---
    card = Table([[grilla], [obs_tabla]], colWidths=[ANCHO_FICHA])
    card.hAlign = "CENTER"
    card.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GRIS_FONDO),
        ("BOX", (0, 0), (-1, -1), 0.7, GRIS_LINEA),
        ("LINEBELOW", (0, 0), (0, 0), 0.7, GRIS_LINEA),
        ("LEFTPADDING", (0, 0), (-1, -1), 18),
        ("RIGHTPADDING", (0, 0), (-1, -1), 18),
        ("TOPPADDING", (0, 0), (0, 0), 14),
        ("BOTTOMPADDING", (0, 0), (0, 0), 14),
        ("TOPPADDING", (0, 1), (0, 1), 13),
        ("BOTTOMPADDING", (0, 1), (0, 1), 14),
    ]))
    return card


def galeria_fotos(fotos):
    """Lista de 1 columna con foto enmarcada a ancho completo + leyenda.

    Cada `foto` es un dict con:
      - "img"     : objeto file-like (BytesIO) con la imagen ya descargada
      - "titulo"  : rótulo principal (opcional)
      - "detalle" : texto secundario (opcional)
    """
    cards = []
    col_w = ANCHO_UTIL                       # una sola columna a ancho completo
    max_h = 150 * mm                          # alto máximo para fotos verticales

    for f in fotos:
        try:
            f["img"].seek(0)
            with PILImage.open(f["img"]) as _pil:
                iw, ih = _pil.size
            # Escala al ancho de columna y limita el alto (sin deformar ni letterbox)
            w = col_w
            h = col_w * (ih / iw) if iw else max_h
            if h > max_h:
                h = max_h
                w = max_h * (iw / ih) if ih else col_w
            f["img"].seek(0)
            img = Image(f["img"], width=w, height=h)
            img.hAlign = "CENTER"
        except Exception:
            img = Spacer(col_w, col_w * 0.6)
        leyenda = Table(
            [[Paragraph(f.get("titulo", ""), STYLES["Cap"])],
             [Paragraph(f.get("detalle", "").replace("\n", "<br/>"), STYLES["CapSub"])]],
            colWidths=[col_w])
        leyenda.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (0, 0), 7),
            ("TOPPADDING", (0, 1), (0, 1), 1),
            ("BOTTOMPADDING", (0, 0), (0, 0), 1),
            ("BOTTOMPADDING", (0, 1), (0, 1), 9),
        ]))
        card = Table([[img], [leyenda]], colWidths=[col_w])
        card.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.7, GRIS_LINEA),
            ("BACKGROUND", (0, 1), (0, 1), BLANCO),
            # La foto se centra (horizontal y vertical) dentro de su celda.
            ("ALIGN", (0, 0), (0, 0), "CENTER"),
            ("VALIGN", (0, 0), (0, 0), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LINEBELOW", (0, 0), (0, 0), 2.5, NARANJA),
        ]))
        cards.append(card)

    # Una tarjeta por fila (separadas para que el salto de página caiga
    # entre fotos y no dentro de una).
    filas = [[c] for c in cards]
    grid = Table(filas, colWidths=[col_w])
    grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, 0), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))
    return grid


# ----------------------------------------------------------------------
# DESCARGA Y VALIDACIÓN DE IMÁGENES (URLs de Connecteam)
# ----------------------------------------------------------------------
def _descargar_fotos(urls, punto):
    """Descarga y valida las imágenes de la lista de URLs. Devuelve una lista
    de dicts {img, titulo, detalle} lista para `galeria_fotos`. Las imágenes
    rotas o inaccesibles se omiten silenciosamente (no rompen el informe)."""
    fotos = []
    idx = 0
    for url in urls or []:
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = io.BytesIO(resp.content)
            # Abrir, corregir la orientación EXIF (fotos de celular que vienen
            # acostadas) y re-guardar ya rotada: ReportLab ignora el flag EXIF,
            # así que hay que aplicar la rotación a los píxeles.
            with PILImage.open(data) as pil_img:
                pil_img = ImageOps.exif_transpose(pil_img)
                if pil_img.mode not in ("RGB", "L"):
                    pil_img = pil_img.convert("RGB")
                norm = io.BytesIO()
                pil_img.save(norm, format="JPEG", quality=88)
            norm.seek(0)
            idx += 1
            fotos.append({
                "img": norm,
                "titulo": f"Registro fotográfico {idx}",
                "detalle": punto or "",
            })
        except Exception as e:
            print(f"Error al procesar imagen {url}: {e}")
            continue
    return fotos


# ----------------------------------------------------------------------
# FORMATEO DE FECHA  (igual que el informe original)
# ----------------------------------------------------------------------
def _formatear_fecha(fecha):
    """Convierte 'YYYY-MM-DD HH:MM:SS' (UTC) a 'dd/mm/YYYY' hora de Chile.
    Si no puede parsear, devuelve el texto original."""
    try:
        dt = datetime.strptime(str(fecha), "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        return dt.astimezone(ZoneInfo("America/Santiago")).strftime("%d/%m/%Y")
    except Exception:
        return str(fecha)


# ----------------------------------------------------------------------
# PUNTO DE ENTRADA  ·  firma compatible con processor.py / pdf_generator.py
# ----------------------------------------------------------------------
def informe_pdf_profesional(numero_visita, ot, tecnico, proyecto, fecha, cliente,
                            tipo_equipo, modelo, serial, trabajo, alcance, punto,
                            obs_especifica, obs_generales, imagenes, equipo):
    """
    Genera el informe PDF con la identidad visual de WE TECHS y devuelve un
    `io.BytesIO`. La firma se mantiene idéntica a la versión anterior para no
    afectar a `processor.py` (5 llamadas) ni a `pdf_generator.py`.

    - `trabajo`  : código de trabajo (MC/MP/I/CF/E) → se traduce a texto.
    - `alcance`  : texto o False (los módulos que no aplican pasan False).
    - `imagenes` : lista de URLs (Connecteam) o lista vacía.
    """
    id_tipo_mantencion = {
        'MC': 'Mantención correctiva',
        'MP': 'Mantención preventiva',
        'I':  'Instalación',
        'CF': 'Configuración',
        'E':  'Extracción',
    }
    tipo_trabajo = id_tipo_mantencion.get(trabajo, str(trabajo))

    datos = {
        "ot": ot,
        "nodo": punto,
        "tecnico": tecnico,
        "cliente": cliente,
        "proyecto": proyecto,
        "fecha": _formatear_fecha(fecha),
        "equipo": tipo_equipo,
        "modelo": modelo,
        "serie": serial,
        "tipo_trabajo": tipo_trabajo,
        "alcance": alcance,
        "obs_equipo": obs_especifica,
        "obs_generales": obs_generales,
    }

    fotos = _descargar_fotos(imagenes, str(punto))

    buffer = io.BytesIO()
    doc = BaseDocTemplate(
        buffer, pagesize=A4,
        leftMargin=MARGEN, rightMargin=MARGEN,
        topMargin=MARGEN + 26 * mm, bottomMargin=MARGEN + 6,
        title=f"Informe OT-{ot} · {punto}",
        author="WE TECHS",
    )
    doc.meta = {
        "ref": f"OT-{ot}  ·  {punto}",
        "proyecto": str(proyecto or ""),
    }
    frame = Frame(MARGEN, MARGEN + 6, ANCHO_UTIL,
                  ALTO_PAGINA - (MARGEN + 26 * mm) - (MARGEN + 6),
                  id="cuerpo")
    doc.addPageTemplates([
        PageTemplate(id="base", frames=[frame], onPage=_dibujar_marco)
    ])

    el = []
    # Eyebrow que enfatiza el tipo de objeto del informe
    el.append(Paragraph("TRABAJOS SOBRE EQUIPOS E INSTRUMENTOS", STYLES["Eyebrow"]))
    el.append(Paragraph("Informe de Trabajos", STYLES["Titulo"]))
    sub = str(punto or "")
    if tipo_equipo:
        sub = f"{sub} · {tipo_equipo}" if sub else str(tipo_equipo)
    el.append(Paragraph(sub, STYLES["Subtitulo"]))
    el.append(Spacer(1, 6))
    # Destacado superior = TIPO DE TRABAJO
    el.append(Chip("Tipo de trabajo", tipo_trabajo))
    el.append(Spacer(1, 18))

    # Estructura única: datos del servicio + observaciones
    el.append(TituloSeccion("Detalle del servicio y observaciones"))
    el.append(Spacer(1, 8))
    el.append(ficha_servicio(datos))
    el.append(Spacer(1, 16))

    # Registro fotográfico (en página propia)
    if fotos:
        el.append(PageBreak())
        el.append(TituloSeccion("Registro fotográfico"))
        el.append(Spacer(1, 4))
        el.append(Paragraph(
            "Evidencia de terreno del trabajo realizado.",
            STYLES["Intro"]))
        el.append(Spacer(1, 10))
        el.append(galeria_fotos(fotos))

    doc.build(el)
    buffer.seek(0)
    return buffer
