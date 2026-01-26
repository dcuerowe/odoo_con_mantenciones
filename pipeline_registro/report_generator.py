import io
import requests
import pandas as pd
from reportlab.lib.pagesizes import letter, A4, legal
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.platypus.flowables import HRFlowable
from reportlab.lib.utils import ImageReader
from datetime import datetime
from io import BytesIO
from config import LOGO_URL
from PIL import Image as PILImage

def crear_estilos_personalizados():
    """
    Crea y retorna una colección de estilos personalizados para usar en documentos PDF con ReportLab.
    """

    styles = getSampleStyleSheet()
    
    # Estilo para el título principal
    styles.add(ParagraphStyle(
        name='TituloPrincipal',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.black,
        spaceAfter=20,
        spaceBefore=10,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    ))
    
    # Estilo para subtítulos
    styles.add(ParagraphStyle(
        name='Subtitulo',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.black,
        spaceAfter=12,
        spaceBefore=16,
        fontName='Helvetica-Bold'
    ))
    
    # Estilo para información de fecha
    styles.add(ParagraphStyle(
        name='InfoFecha',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.grey,
        alignment=TA_RIGHT,
        spaceAfter=20,
        fontName='Helvetica-Oblique'
    ))
    
    # Estilo para texto de introducción
    styles.add(ParagraphStyle(
        name='Introduccion',
        parent=styles['Normal'],
        fontSize=11,
        alignment=TA_JUSTIFY,
        spaceAfter=16,
        spaceBefore=8,
        leftIndent=0,
        rightIndent=0
    ))
    
    # Estilo para el pie de página
    styles.add(ParagraphStyle(
        name='PiePagina',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=TA_CENTER
    ))
    
    return styles

def crear_tabla_profesional(dataframe_trabajo, styles):
    """
    Crea una tabla profesional en formato ReportLab a partir de los datos de un DataFrame.
    """

    campos = {
        'OT:': dataframe_trabajo.iloc[0,0],
        'Técnico:': dataframe_trabajo.iloc[0,1],
        'Proyecto:': dataframe_trabajo.iloc[0,2],
        'Fecha de realización:': dataframe_trabajo.iloc[0,3],
        'Cliente:': dataframe_trabajo.iloc[0,4],
        'Equipo/instrumento:': dataframe_trabajo.iloc[0,5],
        'Modelo:': dataframe_trabajo.iloc[0,6],
        'N° de serie:': dataframe_trabajo.iloc[0,7]

    }

    df_campos = pd.DataFrame(campos, index=[0])
    
    # Preparar datos para la tabla
    df_vertical = df_campos.T.reset_index()
    df_vertical.columns = ['Campo', 'Respuesta']
    
    # Crear encabezados de tabla
    headers = ['Campo', 'Respuesta']
    data_list = [headers]
    
    # Agregar datos con formato mejorado
    for _, row in df_vertical.iterrows():
        campo = str(row['Campo'])
        respuesta = str(row['Respuesta'])
        data_list.append([campo, respuesta])
    
    # Convertir a Paragraphs para mejor control del formato
    data_for_table = []
    for i, row in enumerate(data_list):
        if i == 0:  # Encabezados
            formatted_row = [Paragraph(f"<b>{str(cell)}</b>", styles['Normal']) for cell in row]
        else:  # Datos
            # Campo en negrita, respuesta normal
            campo_cell = Paragraph(f"<b>{str(row[0])}</b>", styles['Normal'])
            respuesta_cell = Paragraph(str(row[1]), styles['Normal'])
            formatted_row = [campo_cell, respuesta_cell]
        data_for_table.append(formatted_row)
    
    # Crear tabla con anchos optimizados
    table = Table(data_for_table, colWidths=[5*cm, 12*cm], repeatRows=1)
    

    COLOR_NARANJA_WETECHS = HexColor("#EA6500")
    table_style = TableStyle([

        # Encabezado
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_NARANJA_WETECHS),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        
        # Filas de datos
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        
        # Bordes y espaciado
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        
        # Alternar colores de fila para mejor legibilidad
        #('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
    ])
    
    table.setStyle(table_style)
    return table

def add_header_first_page(canvas, doc):
    # --- 1. Cargar el logo desde la URL ---
    # URL del logo de We-Techs
    # LOGO_URL imported from config

    try:
        response = requests.get(LOGO_URL)
        response.raise_for_status() # Lanza un error si la descarga falla
        logo_bytes = io.BytesIO(response.content)
        # Define el tamaño del logo. Ajusta estos valores si es necesario.
        img_reader = ImageReader(logo_bytes)
        original_width, original_height = img_reader.getSize()

        # Define el ancho deseado en cm y calcula la altura proporcionalmente
        logo_width_cm = 2.5 * cm
        aspect_ratio = original_height / original_width
        logo_height_cm = logo_width_cm * aspect_ratio
    
    except Exception as e:
        print(f"Error al cargar el logo desde la URL: {e}")
        logo_bytes = None
    
    if logo_bytes:
        # Rebobinar el stream de bytes
        logo_bytes.seek(0)
        
        # *** CAMBIO CLAVE: USAR ImageReader ***
        # Pasamos el stream de bytes a ImageReader, que es el formato
        # que ReportLab espera para dibujar imágenes en memoria.
        logo_image = ImageReader(logo_bytes)
        
        x_pos = legal[0] - doc.rightMargin - logo_width_cm
        y_pos = legal[1] - doc.topMargin - logo_height_cm + 1.5 * cm
        
        # Ahora pasamos el objeto ImageReader a drawImage
        canvas.drawImage(
            logo_image,
            x=x_pos,
            y=y_pos,
            width=logo_width_cm,
            height=logo_height_cm,
            mask='auto'
        )

def agregar_imagenes_desde_url(story, lista_urls):
    """
    Agrega imágenes a una historia de ReportLab a partir de una lista de URLs.
    Incluye manejo de punteros de memoria y validación de imágenes.
    """
    max_width = A4[0] - 4 * cm 
    max_height = A4[1] - 4 * cm 

    for url in lista_urls:
        try:
            response = requests.get(url, timeout=10) # Agrega timeout por seguridad
            response.raise_for_status()
            
            # Crear el objeto BytesIO
            img_bytes = BytesIO(response.content)
            
            # --- VALIDACIÓN Y OBTENCIÓN DE TAMAÑO ---
            # Usamos PIL directamente para verificar que la imagen es válida
            # y obtener sus dimensiones sin depender solo de ReportLab
            try:
                with PILImage.open(img_bytes) as pil_img:
                    pil_img.verify() # Verifica integridad del archivo
                    
                # Reabrimos porque verify() puede consumir el archivo
                img_bytes.seek(0) # <--- IMPORTANTE: Reiniciar puntero
                with PILImage.open(img_bytes) as pil_img:
                    img_width, img_height = pil_img.size
            except Exception as e:
                print(f"Imagen corrupta o inválida en {url}: {e}")
                continue # Saltar esta imagen si está rota

            # --- ESCALADO ---
            scale = min(max_width / img_width, max_height / img_height, 1.0)
            new_width = img_width * scale
            new_height = img_height * scale

            # --- PREPARACIÓN PARA REPORTLAB ---
            # Reiniciar el puntero a 0 OBLIGATORIAMENTE antes de dárselo a ReportLab
            img_bytes.seek(0) 

            story.append(PageBreak())
            # Pasamos el objeto BytesIO con el puntero en 0
            story.append(Image(img_bytes, width=new_width, height=new_height))
            
        except Exception as e:
            print(f"Error general al procesar imagen {url}: {e}")

def informe_pdf_profesional(numero_visita, tipo_trabajo, dataframe_visita, dataframe_trabajo, equipo):
    """
    Genera un informe PDF profesional detallando los trabajos realizados en una visita técnica.
    """
    id_tipo_mantención = {'MC': 'mantención correctiva',
                    'MP': 'mantención preventiva',
                    'I': 'instalación'}
    # Configuración del archivo
    
    buffer = io.BytesIO()

    # Usar A4
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=legal,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2.5*cm,
        bottomMargin=2*cm
    )
    
    # Obtener estilos personalizados
    styles = crear_estilos_personalizados()
    
    # Lista de elementos del documento
    story = []
    
    # ENCABEZADO DEL DOCUMENTO
    # Título principal
    punto_monitoreo = dataframe_visita.get(f'{numero_visita}.1 Punto de monitoreo', ['N/A'])[0]
    title = Paragraph(
        f"Informe de trabajos<br/>{punto_monitoreo}",
        styles['TituloPrincipal']
    )
    story.append(title)
    
    # Información del nodo y número de visita
    # Línea divisoria decorativa
    line = HRFlowable(width="100%", thickness=1, lineCap='round', color=colors.orange)
    story.append(line)
    story.append(Spacer(1, 12))
    
    # Fecha de generación
    try:
        current_date = datetime.now().strftime("%d de %B de %Y")
    except:
        current_date = datetime.now().strftime("%d de %m de %Y")
    
    date_text = Paragraph(
        f"Fecha de generación: {current_date}",
        styles['InfoFecha']
    )
    story.append(date_text)
    #story.append(Spacer(1, 20))
    
    # SECCIÓN DE INTRODUCCIÓN
    intro_subtitle = Paragraph("Detalle", styles['Subtitulo'])
    story.append(intro_subtitle)
    
    ot_number = dataframe_visita['#'][0]


    intro_text = Paragraph(
        f"Este documento presenta el detalle de las tareas de {id_tipo_mantención[tipo_trabajo]} "
        f"realizadas sobre el equipo/instrumento señalado en tabla. ",
        styles['Introduccion']

    )

    story.append(intro_text)
    story.append(Spacer(1, 20))
    
    # Tabla principal con datos
    report_table = crear_tabla_profesional(dataframe_trabajo, styles)
    story.append(report_table)
    story.append(Spacer(1, 30))
    
    observaciones_a_agregar = []

    # 1. Buscar y guardar observaciones técnicas en dataframe_trabajo
    obs_cols = [
        col for col in dataframe_trabajo.columns 
        if 'observación' in str(col).lower() or 'observaciones' in str(col).lower()
    ]
    for col in obs_cols:
        obs_text = dataframe_trabajo[col].iloc[0]
        if pd.notna(obs_text) and str(obs_text).strip() and str(obs_text).lower() != 'nan':
            observaciones_a_agregar.append({
                'type': "Observaciones al equipo",
                'text': str(obs_text)
            })
            # Si solo quieres la primera observación técnica encontrada, puedes usar 'break' aquí.
            break 

    # 2. Buscar y guardar observaciones generales en dataframe_visita
    res_cols = [col for col in dataframe_visita.columns if 'resolución' in str(col).lower()]
    for col in res_cols:
        obs_text = dataframe_visita[col].iloc[0]
        if pd.notna(obs_text) and str(obs_text).strip() and str(obs_text).lower() != 'nan':
            observaciones_a_agregar.append({
                'type': "Observaciones generales",
                'text': str(obs_text)
            })
            # Si solo quieres la primera observación general encontrada, puedes usar 'break' aquí.
            break

    # 3. Agregar todas las observaciones encontradas al informe
    if observaciones_a_agregar:
        for obs in observaciones_a_agregar:
            obs_subtitle = Paragraph(obs['type'], styles['Subtitulo'])
            story.append(obs_subtitle)
            obs_paragraph = Paragraph(f"• {obs['text']}", styles['Introduccion'])
            story.append(obs_paragraph)
            story.append(Spacer(1, 20))

    story.append(Spacer(1, 30))
    line2 = HRFlowable(width="100%", thickness=0.5, lineCap='round', color=colors.lightgrey)
    story.append(line2)
    story.append(Spacer(1, 12))
    
    
    footer_text = Paragraph(
        f"Documento generado automáticamente • OT-{ot_number} • "
        f"{dataframe_trabajo.iloc[0,2]}",
        styles['PiePagina']
    )
    story.append(footer_text)



    lista_imagenes = []
    imagenes = dataframe_visita[f'{numero_visita}.4 Fotos recinto'][0]
    for img in imagenes:
        lista_imagenes.append(img['url'])

    # Agregar imágenes desde URLs
    if lista_imagenes:
        agregar_imagenes_desde_url(story, lista_imagenes)

    doc.build(story, onFirstPage=add_header_first_page)

    buffer.seek(0)
    
    return buffer
