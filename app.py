import sys
import asyncio

# Forzar a Windows a usar el selector clásico por si haces pruebas locales
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import streamlit as st
import requests
from datetime import datetime 

# Configuración de pantalla
st.set_page_config(page_title="Sistema de Pedidos Pro", page_icon="🛍️", layout="wide")

# URL de tu macro de Google Apps Script
URL_WEB_APP = "https://script.google.com/macros/s/AKfycbyEuyPtExmCSmKF7NVdj9n2UWgoJQBOUyE0-2PQW9zSW3M1GN6puvTBdvRgtwO4r2bc/exec"

# ==========================================
# CARGA Y CONTROL DE CACHÉ DE DATOS
# ==========================================
@st.cache_data(ttl=10) 
def cargar_datos_completos():
    try:
        response = requests.get(f"{URL_WEB_APP}?action=leer_todo", timeout=10)
        return response.json()
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        return None

datos_base = cargar_datos_completos()
if datos_base is None:
    st.stop()

# Extracción de datos purificados
df_productos = datos_base.get("productos", [])
lista_usuarios = [u["usuario"] for u in datos_base.get("usuarios", []) if "usuario" in u]
df_tiendas_completo = datos_base.get("tiendas", [])

# ==========================================
# INTERFAZ Y LÓGICA DE FILTRADO
# ==========================================
st.title("🛍️ Gestión de Pedidos por Tienda Asignada")

# Panel Lateral de Control
st.sidebar.header("🔑 Autenticación de Usuario")
usuario_activo = st.sidebar.selectbox("Seleccione su Usuario:", lista_usuarios)

# FILTRO CRÍTICO: Filtrar la lista de tiendas por usuario activo
tiendas_asignadas = [
    t for t in df_tiendas_completo 
    if str(t.get("usuario", "")).lower() == str(usuario_activo).lower()
]

# Control de flujo si el usuario no posee sucursales asignadas
if not tiendas_asignadas:
    st.warning(f"⚠️ El usuario **{usuario_activo}** no tiene ninguna tienda asignada en el archivo central.")
    st.stop()

# Selector de Tienda restringido únicamente a sus asignaciones
tienda_seleccionada = st.sidebar.selectbox(
    "Seleccione su Tienda Asignada:", 
    tiendas_asignadas, 
    format_func=lambda t: f"{t.get('codigo_tienda', '')} - {t.get('tienda', '')}"
)

codigo_tienda_activo = tienda_seleccionada.get('codigo_tienda', '')
nombre_tienda_activo = tienda_seleccionada.get('tienda', '')

# CONTROL DE RESETEO: Limpieza estricta de formulario
llave_sesion_limpieza = f"pedido_{usuario_activo}_{codigo_tienda_activo}"
if "llave_actual" not in st.session_state or st.session_state["llave_actual"] != llave_sesion_limpieza:
    st.session_state["llave_actual"] = llave_sesion_limpieza
    st.session_state["carrito_cantidades"] = {}

st.write(f"Sesión activa: **{usuario_activo}** | Sucursal Autorizada: **[{codigo_tienda_activo}] {nombre_tienda_activo}**")
st.divider()

# ==========================================
# DESPLIEGUE DEL CATÁLOGO DE ARTÍCULOS
# ==========================================
st.subheader("📋 Formulario de Artículos")

# Contenedor para almacenar cantidades de esta sesión
cantidades_actuales = {}

for prod in df_productos:
    cod_prod = prod.get('codigo', '')
    col1, col2, col3 = st.columns([1, 2, 1.5])
    
    with col1:
        id_foto = str(prod.get('id_imagen_drive', '')).strip()
        # Validación de ID real para renderizar la imagen
        if id_foto and id_foto not in ["", "0", "0.0", "None", "Sin Foto"]:
            st.image(f"https://googleusercontent.com{id_foto}", width=120)
        else:
            st.info("📸 Sin foto")
            
    with col2:
        # CORREGIDO: Se removió el texto extraño que rompía el renderizado de la fila
        st.markdown(f"### {prod.get('nombre', 'Producto')}")
        st.caption(f"Código de Artículo: {cod_prod}")
        
    with col3:
        llave_input = f"input_{llave_sesion_limpieza}_{cod_prod}"
        
        cant_digitada = st.number_input(
            "Cantidad a solicitar:", 
            min_value=0, 
            step=1, 
            value=0,
            key=llave_input
        )
        if cant_digitada > 0:
            cantidades_actuales[cod_prod] = cant_digitada

    st.divider()

# ==========================================
# BOTÓN DE ENVÍO DE PEDIDO CENTRAL
# ==========================================
st.sidebar.markdown("---")
st.sidebar.subheader("Confirmación General")

if cantidades_actuales:
    st.sidebar.write(f"Items seleccionados: **{len(cantidades_actuales)}**")
    
    if st.sidebar.button("🚀 Enviar Pedido Completo", use_container_width=True):
        ahora = datetime.now()
        fecha_registro = ahora.strftime("%Y-%m-%d %H:%M:%S")
        
        # Generación del ID único global
        id_pedido_referencia = f"PED-{ahora.strftime('%Y%m%d-%H%M%S')}-{codigo_tienda_activo}-{usuario_activo.upper()}"
        
        exito_envios = True
        
        for cod_art, cant_art in cantidades_actuales.items():
            datos_pedido = {
                "fecha": fecha_registro,
                "codigo_tienda": f"{id_pedido_referencia} | {codigo_tienda_activo}", 
                "tienda": nombre_tienda_activo,
                "codigo": cod_art,
                "cantidad": cant_art,
                "usuario": usuario_activo
            }
            
            try:
                res = requests.post(URL_WEB_APP, json=datos_pedido, timeout=10)
                if res.status_code != 200:
                    exito_envios = False
            except Exception:
                exito_envios = False
                
        if exito_envios:
            st.sidebar.success("🎉 ¡Pedido Guardado Exitosamente!")
            # CORREGIDO: Llamada en plural corregida para evitar el error AttributeError
            st.balloons() 
            st.toast(f"Referencia generada: {id_pedido_referencia}")
            st.rerun()
        else:
            st.sidebar.error("Inconveniente al guardar líneas en Google Sheets.")
else:
    st.sidebar.caption("Suma cantidades en el catálogo para habilitar el envío.")
