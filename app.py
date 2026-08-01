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

# Configuración inicial de la interfaz
st.set_page_config(page_title="Sistema de Pedidos Pro", page_icon="🛍️", layout="wide")

# URL de tu macro de Google Apps Script
URL_WEB_APP = "https://script.google.com/macros/s/AKfycbyEuyPtExmCSmKF7NVdj9n2UWgoJQBOUyE0-2PQW9zSW3M1GN6puvTBdvRgtwO4r2bc/exec"

# ==========================================
# CARGA DE DATOS DESDE GOOGLE SHEETS
# ==========================================
@st.cache_data(ttl=15)
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

df_productos = datos_base.get("productos", [])
lista_usuarios = [u["usuario"] for u in datos_base.get("usuarios", []) if "usuario" in u]
df_tiendas_completo = datos_base.get("tiendas", [])

# ==========================================
# INTERFAZ DE USUARIO Y CONTROL DE SESIÓN
# ==========================================
st.title("🛍️ Sistema de Solicitud de Pedidos")

st.sidebar.header("Identificación")
usuario_active = st.sidebar.selectbox("Seleccione su Usuario:", lista_usuarios)

lista_tiendas_filtradas = [
    t for t in df_tiendas_completo 
    if str(t.get("usuario", "")).lower() == str(usuario_active).lower()
]

if not lista_tiendas_filtradas:
    st.warning(f"⚠️ El usuario **{usuario_active}** no tiene ninguna tienda asignada.")
    st.stop()

tienda_seleccionada = st.sidebar.selectbox(
    "Seleccione su Tienda:", 
    lista_tiendas_filtradas, 
    format_func=lambda t: f"{t.get('codigo_tienda', '')} - {t.get('tienda', '')}"
)

codigo_tienda_activo = tienda_seleccionada.get('codigo_tienda', '')
nombre_tienda_activo = tienda_seleccionada.get('tienda', '')

# CONTROL DE RESETEO Y CONTROL DE DUPLICADOS
llave_limpieza = f"tienda_{usuario_active}_{codigo_tienda_activo}"
if "tienda_actual" not in st.session_state or st.session_state["tienda_actual"] != llave_limpieza:
    st.session_state["tienda_actual"] = llave_limpieza
    st.session_state["codigos_enviados"] = []  # Historial de lo ya enviado en la sesión actual
    st.session_state["pdf_listo"] = None       # Almacenamiento del PDF generado
    st.session_state["ref_pdf"] = ""          # Referencia del último pedido
    for key in list(st.session_state.keys()):
        if key.startswith("cant_"):
            del st.session_state[key]

st.write(f"Sesión activa: **{usuario_active}** | Tienda: **[{codigo_tienda_activo}] {nombre_tienda_activo}**")
st.divider()

# ==========================================
# FUNCIÓN GENERADORA DEL REPORTE PDF CORREGIDA
# ==========================================
def generar_pdf_pedidos(referencia, fecha, tienda_nombre, lista_items):
    buffer = io.BytesIO()
    # Margen de 0.5 pulgadas para aprovechar la hoja al máximo
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    story = []
    
    styles = getSampleStyleSheet()
    
    estilo_titulo = ParagraphStyle(
        'TituloPDF',
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=16,
        alignment=TA_CENTER,
        spaceAfter=6
    )
    
    estilo_meta = ParagraphStyle(
        'MetaPDF',
        fontName='Helvetica',
        fontSize=10,
        leading=12,
        alignment=TA_CENTER,
        spaceAfter=15
    )
    
    estilo_celda = ParagraphStyle(
        'CeldaPDF',
        fontName='Helvetica',
        fontSize=10,
        leading=11,
        alignment=TA_LEFT
    )
    
    # Encabezado principal
    story.append(Paragraph(f"<b>REPORTE DE SOLICITUD DE PEDIDO</b>", estilo_titulo))
    story.append(Paragraph(f"<b>Tienda:</b> {tienda_nombre} &nbsp;|&nbsp; <b>Fecha:</b> {fecha} &nbsp;|&nbsp; <b>ID Único:</b> {referencia}", estilo_meta))
    
    # Importamos el componente nativo de imágenes de ReportLab de forma local
    from reportlab.platypus import Image as RLImage
    
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
        
        # Descarga e inserción segura de la imagen izquierda
        p_img_izq = Paragraph("❌ Sin foto", estilo_celda)
        if id_foto_izq and id_foto_izq not in ["", "0", "0.0", "None", "Sin Foto"]:
            try:
                img_res = requests.get(f"https://googleusercontent.com{id_foto_izq}", timeout=5)
                if img_res.status_code == 200:
                    img_data = io.BytesIO(img_res.content)
                    p_img_izq = RLImage(img_data, width=40, height=40)
            except Exception:
                pass
                
        fila_bloque.extend([p_img_izq, p_texto_izq])
        
        # --- COLUMNA DERECHA ---
        if der:
            id_foto_der = str(der.get('id_drive', '')).strip()
            texto_der = f"<b>Código:</b> {der['codigo']}<br/><b>Nombre:</b> {der['nombre']}<br/><b>Cant:</b> {der['cantidad']}"
            p_texto_der = Paragraph(texto_der, estilo_celda)
            
            # Descarga e inserción segura de la imagen derecha
            p_img_der = Paragraph("❌ Sin foto", estilo_celda)
            if id_foto_der and id_foto_der not in ["", "0", "0.0", "None", "Sin Foto"]:
                try:
                    img_res = requests.get(f"https://googleusercontent.com{id_foto_der}", timeout=5)
                    if img_res.status_code == 200:
                        img_data = io.BytesIO(img_res.content)
                        p_img_der = RLImage(img_data, width=40, height=40)
                except Exception:
                    pass
                    
            fila_bloque.extend([p_img_der, p_texto_der])
        else:
            fila_bloque.extend(["", ""])
            
        tabla_datos.append(fila_bloque)
        
    # Anchos fijos de columnas arreglados: [FotoIzq, InfoIzq, FotoDer, InfoDer] -> 540 puntos utilizables
    anchos_columnas = [50, 220, 50, 220]
    
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
    # Anchos fijos de columnas para las firmas arreglados: 270 puntos por firma
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
# DESPLIEGUE DEL CATÁLOGO DE PRODUCTOS
# ==========================================
st.subheader("Catálogo de Productos")

carrito_solicitudes = {}

for prod in df_productos:
    col1, col2, col3 = st.columns([1, 2, 1.5])
    cod_art = str(prod.get('codigo', ''))
    
    with col1:
        id_foto = str(prod.get('id_imagen_drive', '')).strip()
        if id_foto and id_foto not in ["", "0", "0.0", "None", "Sin Foto"]:
            url_directa_foto = f"https://googleusercontent.com{id_foto}"
            st.image(url_directa_foto, width=130)
        else:
            st.warning("Sin ID de foto")
            
    with col2:
        st.markdown(f"### {prod.get('nombre', 'Producto Sin Nombre')}")
        st.caption(f"Código de Artículo: {cod_art}")
        
        if cod_art in st.session_state["codigos_enviados"]:
            st.success("✅ Este artículo ya fue guardado en Google Sheets")
            
    with col3:
        ya_procesado = cod_art in st.session_state["codigos_enviados"]
        
        cantidad = st.number_input(
            "Cantidad a pedir:", 
            min_value=0, 
            step=1, 
            key=f"cant_{cod_art}",
            disabled=ya_procesado
        )
        if cantidad > 0 and not ya_procesado:
            carrito_solicitudes[cod_art] = {
                "codigo": cod_art,
                "nombre": prod.get('nombre', 'Producto'),
                "cantidad": cantidad,
                "id_drive": id_foto
            }
                
    st.divider()

# ==========================================
# PANEL LATERAL: PROCESAMIENTO Y DOCUMENTO
# ==========================================
st.sidebar.markdown("---")
st.sidebar.subheader("Confirmación de Solicitud")

if carrito_solicitudes:
    st.sidebar.write(f"Nuevos artículos por enviar: **{len(carrito_solicitudes)}**")
    
    if st.sidebar.button("🚀 Enviar Pedido Completo", use_container_width=True):
        ahora = datetime.now()
        fecha_actual = ahora.strftime("%Y-%m-%d %H:%M:%S")
        id_pedido_referencia = f"PED-{ahora.strftime('%Y%m%d-%H%M%S')}-{codigo_tienda_activo}-{usuario_active.upper()}"
        # Inicialización de banderas y listas de control
        exito_operacion = True
        lista_pdf_items = []
        
        # Iteración sobre cada producto agregado al carrito
        for cod_item, info in carrito_solicitudes.items():
            datos_pedido = {
                "fecha": fecha_actual,
                "codigo_tienda": f"{id_pedido_referencia} | {codigo_tienda_activo}",
                "tienda": nombre_tienda_activo,
                "codigo": cod_item,
                "cantidad": info["cantidad"],
                "usuario": usuario_active
            }
            
            try:
                # Envío de la fila hacia Google Apps Script
                res = requests.post(URL_WEB_APP, json=datos_pedido, timeout=10)
                if res.status_code == 200:
                    # Agregamos al historial para bloquear duplicados y al reporte PDF
                    st.session_state["codigos_enviados"].append(cod_item)
                    lista_pdf_items.append(info)
                else:
                    exito_operacion = False
            except Exception:
                exito_operacion = False
                
        # Validación de éxito para la generación del documento final
        if exito_operacion and lista_pdf_items:
            st.sidebar.success("🎉 ¡Pedido guardado exitosamente!")
            st.balloons()
            
            # Construcción del archivo PDF en memoria
            pdf_data = generar_pdf_pedidos(id_pedido_referencia, fecha_actual, nombre_tienda_activo, lista_pdf_items)
            st.session_state["pdf_listo"] = pdf_data
            st.session_state["ref_pdf"] = id_pedido_referencia
            
            # Recarga la página manteniendo los estados bloqueados
            st.rerun()
        else:
            st.sidebar.error("Error al procesar el almacenamiento en algunas líneas.")
else:
    if not st.session_state["codigos_enviados"]:
        st.sidebar.caption("Modifica cantidades en el catálogo para procesar un pedido.")

# Visualización persistente del botón para descargar el PDF
if st.session_state["pdf_listo"] is not None:
    st.sidebar.markdown("---")
    st.sidebar.subheader("📄 Documentación Generada")
    st.sidebar.info(f"Ref: {st.session_state['ref_pdf']}")
    
    st.sidebar.download_button(
        label="📥 Descargar Reporte PDF",
        data=st.session_state["pdf_listo"],
        file_name=f"Pedido_{st.session_state['ref_pdf']}.pdf",
        mime="application/pdf",
        use_container_width=True
    )
