import sys
import asyncio

# Forzar a Windows a usar el selector clásico por si haces pruebas locales
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import streamlit as st
import requests
from datetime import datetime 
import io

# Librerías oficiales para la construcción precisa del PDF a 2 columnas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# Configuración inicial de la interfaz (Tu base estable)
st.set_page_config(page_title="Sistema de Pedidos", page_icon="🛍️", layout="wide")

# ==========================================
# CONFIGURACIÓN DEL ENLACE DE CONEXIÓN DIRECTO
# ==========================================
# REEMPLAZA ESTA URL POR TU URL REAL DE GOOGLE APPS SCRIPT
URL_WEB_APP = "https://script.google.com/macros/s/AKfycbyEuyPtExmCSmKF7NVdj9n2UWgoJQBOUyE0-2PQW9zSW3M1GN6puvTBdvRgtwO4r2bc/exec"

# ==========================================
# CARGA DE DATOS DESDE GOOGLE SHEETS
# ==========================================
@st.cache_data(ttl=15) # Mantiene caché estable por 15 segundos para dar velocidad
def cargar_datos_completos():
    try:
        response = requests.get(f"{URL_WEB_APP}?action=leer_todo", timeout=12)
        return response.json()
    except Exception as e:
        st.error(f"Error crítico al conectar con la base de datos de Google: {e}")
        return None

datos_base = cargar_datos_completos()

if datos_base is None:
    st.stop()

# Desempaquetado de las tablas devueltas por Google
df_productos = datos_base.get("productos", [])
lista_usuarios = [u["usuario"] for u in datos_base.get("usuarios", []) if "usuario" in u]
df_tiendas_completo = datos_base.get("tiendas", [])

# ==========================================
# INTERFAZ DE USUARIO Y FILTRADO AVANZADO
# ==========================================
st.title("🛍️ Sistema de Solicitud de Pedidos")

st.sidebar.header("Identificación")
usuario_activo = st.sidebar.selectbox("Seleccione su Usuario:", lista_usuarios)

# REQUERIMIENTO: El usuario solo puede escoger la tienda que tiene asignada
lista_tiendas_filtradas = [
    t for t in df_tiendas_completo 
    if str(t.get("usuario", "")).lower() == str(usuario_activo).lower()
]

# Control de bloqueo amigable si un usuario no cuenta con sucursales asignadas
if not lista_tiendas_filtradas:
    st.warning(f"⚠️ El usuario **{usuario_activo}** no tiene ninguna tienda asignada en Google Sheets.")
    st.stop()

# Desplegable de sucursales restringido estrictamente a su asignación
tienda_seleccionada = st.sidebar.selectbox(
    "Seleccione su Tienda:", 
    lista_tiendas_filtradas, 
    format_func=lambda t: f"{t.get('codigo_tienda', '')} - {t.get('tienda', '')}"
)

codigo_tienda_activo = tienda_seleccionada.get('codigo_tienda', '')
nombre_tienda_activo = tienda_seleccionada.get('tienda', '')

# REQUERIMIENTO: Forzar cantidades a 0 en pantalla al cambiar de tienda o usuario
llave_limpieza = f"tienda_{usuario_activo}_{codigo_tienda_activo}"
if "tienda_actual" not in st.session_state or st.session_state["tienda_actual"] != llave_limpieza:
    st.session_state["tienda_actual"] = llave_limpieza
    st.session_state["codigos_enviados"] = []    # Evita duplicados bloqueando reenvíos
    st.session_state["historial_pdf_items"] = [] # Acumula todos los productos del día para el PDF
    st.session_state["pdf_listo"] = None         # Guarda el PDF generado de la sesión
    st.session_state["ref_pdf"] = ""            # Guarda la referencia del PDF
    # Borramos cualquier rastro numérico de sesiones anteriores para obligar al renderizado en 0
    for key in list(st.session_state.keys()):
        if key.startswith("cant_"):
            del st.session_state[key]

st.write(f"Sesión activa: **{usuario_activo}** | Tienda: **[{codigo_tienda_activo}] {nombre_tienda_activo}**")
st.divider()

# ==========================================
# FUNCIÓN GENERADORA DEL REPORTE PDF (SOLUCIÓN DEFINITIVA DE FOTOS)
# ==========================================
def generar_pdf_pedidos(referencia, fecha, tienda_nombre, lista_items):
    buffer = io.BytesIO()
    # Margen de 0.5 pulgadas para aprovechar la hoja al máximo
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    story = []
    
    styles = getSampleStyleSheet()
    
    estilo_titulo = ParagraphStyle(
        'TituloPDF', fontName='Helvetica-Bold', fontSize=14, leading=16, alignment=TA_CENTER, spaceAfter=6
    )
    estilo_meta = ParagraphStyle(
        'MetaPDF', fontName='Helvetica', fontSize=10, leading=12, alignment=TA_CENTER, spaceAfter=15
    )
    estilo_celda = ParagraphStyle(
        'CeldaPDF', fontName='Helvetica', fontSize=10, leading=11, alignment=TA_LEFT
    )
    
    # Encabezado principal
    story.append(Paragraph(f"<b>REPORTE DE SOLICITUD DE PEDIDO</b>", estilo_titulo))
    story.append(Paragraph(f"<b>Tienda:</b> {tienda_nombre} &nbsp;|&nbsp; <b>Fecha:</b> {fecha} &nbsp;|&nbsp; <b>ID Único:</b> {referencia}", estilo_meta))
    
    # Importamos las herramientas nativas de procesamiento local de ReportLab y red
    from reportlab.platypus import Image as RLImage
    import urllib.request
    
    # Convertimos la lista plana de artículos seleccionados en pares para simular 2 columnas
    pares_productos = []
    for i in range(0, len(lista_items), 2):
        item_izq = lista_items[i]
        item_der = lista_items[i+1] if (i+1) < len(lista_items) else None
        pares_productos.append((item_izq, item_der))
    
    tabla_datos = []
    for izq, der in pares_productos:
        fila_bloque = []
        
        # --- COLUMNA IZQUIERDA ---
        id_foto_izq = str(izq.get('id_drive', '')).strip()
        texto_izq = f"<b>Código:</b> {izq['codigo']}<br/><b>Nombre:</b> {izq['nombre']}<br/><b>Cant:</b> {izq['cantidad']}"
        p_texto_izq = Paragraph(texto_izq, estilo_celda)
        
        p_img_izq = Paragraph("❌ Sin foto", estilo_celda)
        if id_foto_izq and id_foto_izq not in ["", "0", "0.0", "None", "Sin Foto"]:
            try:
                url_descarga_izq = f"https://googleusercontent.com{id_foto_izq}"
                # Creamos una petición simulando un navegador web para saltar bloqueos de Google
                req = urllib.request.Request(url_descarga_izq, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    img_data_izq = io.BytesIO(response.read())
                    p_img_izq = RLImage(img_data_izq, width=40, height=40)
            except Exception:
                pass
        fila_bloque.extend([p_img_izq, p_texto_izq])
        
        # --- COLUMNA DERECHA ---
        if der:
            id_foto_der = str(der.get('id_drive', '')).strip()
            texto_der = f"<b>Código:</b> {der['codigo']}<br/><b>Nombre:</b> {der['nombre']}<br/><b>Cant:</b> {der['cantidad']}"
            p_texto_der = Paragraph(texto_der, estilo_celda)
            
            p_img_der = Paragraph("❌ Sin foto", estilo_celda)
            if id_foto_der and id_foto_der not in ["", "0", "0.0", "None", "Sin Foto"]:
                try:
                    url_descarga_der = f"https://googleusercontent.com{id_foto_der}"
                    req = urllib.request.Request(url_descarga_der, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=5) as response:
                        img_data_der = io.BytesIO(response.read())
                        p_img_der = RLImage(img_data_der, width=40, height=40)
                except Exception:
                    pass
            fila_bloque.extend([p_img_der, p_texto_der])
        else:
            fila_bloque.extend(["", ""])
            
        tabla_datos.append(fila_bloque)
        
    # Ancho total asignado equilibrado: [Foto, Texto, Foto, Texto]
    anchos_columnas = [45, 225, 45, 225]
    tabla_catalogo = Table(tabla_datos, colWidths=anchos_columnas)
    tabla_catalogo.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('INNERGRID', (0,0), (-1,-1), 0.25, colors.whitesmoke)
    ]))
    story.append(tabla_catalogo)
    
    # Bloque de Firma de Recepción
    story.append(Spacer(1, 40))
    estilo_firma = ParagraphStyle('FirmaPDF', fontName='Helvetica', fontSize=10, alignment=TA_CENTER)
    datos_firma = [
        [Paragraph("_____________________________<br/>Firma de Despacho", estilo_firma), 
         Paragraph("_____________________________<br/>Firma de Recepción", estilo_firma)]
    ]
    anchos_firmas = [270, 270]
    tabla_firma = Table(datos_firma, colWidths=anchos_firmas)
    tabla_firma.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER')
    ]))
    story.append(tabla_firma)
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()



# ==========================================
# PANEL DE ENVIÓ CENTRALIZADO CON NÚMERO DE PEDIDO ÚNICO
# ==========================================
st.sidebar.markdown("---")
st.sidebar.subheader("Confirmación de Solicitud")

if carrito_solicitudes:
    st.sidebar.write(f"Artículos seleccionados: **{len(carrito_solicitudes)}**")
    
    # Botón de envío global que genera una referencia simplificada por fecha para modificar/eliminar
    if st.sidebar.button("🚀 Enviar Pedido Completo", use_container_width=True):
        ahora = datetime.now()
        fecha_actual = ahora.strftime("%Y-%m-%d %H:%M:%S")
        
        # Estructura del ID único optimizada: solo AñoMesDía (sin hora) para agrupar reportes del día
        id_pedido_referencia = f"PED-{ahora.strftime('%Y%m%d')}-{codigo_tienda_activo}-{usuario_activo.upper()}"
        exito_operacion = True
        
        for codigo_item, info_item in carrito_solicitudes.items():
            datos_pedido = {
                "fecha": fecha_actual,
                # Inyectamos el ID de referencia único junto al código de la tienda
                "codigo_tienda": f"{id_pedido_referencia} | {codigo_tienda_activo}",
                "tienda": nombre_tienda_activo,
                "codigo": codigo_item,
                "cantidad": info_item["cantidad"],
                "usuario": usuario_activo
            }
            
            try:
                res = requests.post(URL_WEB_APP, json=datos_pedido, timeout=10)
                if res.status_code == 200:
                    # Marcamos como enviado el código para bloquear duplicados
                    st.session_state["codigos_enviados"].append(str(codigo_item))
                    
                    # Consolidamos el artículo en el historial acumulativo del PDF diario
                    existe_en_historial = False
                    for item_pdf in st.session_state["historial_pdf_items"]:
                        if item_pdf["codigo"] == info_item["codigo"]:
                            item_pdf["cantidad"] += info_item["cantidad"]
                            existe_en_historial = True
                            break
                            
                    if not existe_en_historial:
                        st.session_state["historial_pdf_items"].append(info_item)
                else:
                    exito_operacion = False
            except Exception:
                exito_operacion = False
                
        if exito_operacion and st.session_state["historial_pdf_items"]:
            st.sidebar.success("🎉 ¡Pedido guardado exitosamente!")
            st.balloons() # Animación corregida en plural
            
            # Construcción e inyección automática del PDF acumulativo completo en memoria
            pdf_data = generar_pdf_pedidos(id_pedido_referencia, fecha_actual, nombre_tienda_activo, st.session_state["historial_pdf_items"])
            st.session_state["pdf_listo"] = pdf_data
            st.session_state["ref_pdf"] = id_pedido_referencia
            
            # Limpia los datos de la interfaz refrescando los campos no enviados a ceros
            st.rerun()
        else:
            st.sidebar.error("Error al procesar el almacenamiento en Google Sheets.")
else:
    if not st.session_state["codigos_enviados"]:
        st.sidebar.caption("Modifica cantidades en el catálogo para procesar un pedido.")

# Renderizado automático del botón de descarga del PDF si ya se generó el lote acumulado
if st.session_state["pdf_listo"] is not None:
    st.sidebar.markdown("---")
    st.sidebar.subheader("📄 Documentación Generada")
    st.sidebar.info(f"Ref: {st.session_state['ref_pdf']}")
    st.sidebar.write(f"Total productos en reporte: **{len(st.session_state['historial_pdf_items'])}**")
    
    st.sidebar.download_button(
        label="📥 Descargar Reporte PDF",
        data=st.session_state["pdf_listo"],
        file_name=f"Pedido_{st.session_state['ref_pdf']}.pdf",
        mime="application/pdf",
        use_container_width=True
    )
