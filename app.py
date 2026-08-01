import streamlit as st
import requests
from datetime import datetime 

# Configuración de pantalla
st.set_page_config(page_title="Sistema de Pedidos Pro", page_icon="🛍️", layout="wide")

# URL de tu macro de Google Apps Script
URL_WEB_APP = "https://script.google.com/macros/s/AKfycbyEuyPtExmCSmKF7NVdj9n2UWgoJQBOUyE0-2PQW9zSW3M1GN6puvTBdvRgtwO4r2bc/exec"

# ==========================================e:

# CARGA Y CONTROL DE CACHÉ DE DATOS
# ==========================================
@st.cache_data(ttl=10) # Cache bajo para detectar cambios rápidos en las asignaciones
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
# INTERFAZ Y LOGICA DE FILTRADO
# ==========================================
st.title("🛍️ Gestión de Pedidos por Tienda Asignada")

# Panel Lateral de Control
st.sidebar.header("🔑 Autenticación de Usuario")
usuario_activo = st.sidebar.selectbox("Seleccione su Usuario:", lista_usuarios)

# FILTRO CRÍTICO: Filtrar la lista de tiendas donde el campo 'usuario' coincida con el activo
tiendas_asignadas = [
    t for t in df_tiendas_completo 
    if str(t.get("usuario", "")).lower() == str(usuario_activo).lower()
]

# Control de flujo si el usuario no posee sucursales asignadas en la lista
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

# CONTROL DE RESETEO: Si cambia de tienda o usuario, forzar que los inputs se limpien
llave_sesion_limpieza = f"pedido_{usuario_activo}_{codigo_tienda_activo}"
if "llave_actual" not in st.session_state or st.session_state["llave_actual"] != llave_sesion_limpieza:
    st.session_state["llave_actual"] = llave_sesion_limpieza
    # Resetea el carrito interno de cantidades temporales en memoria
    st.session_state["carrito_cantidades"] = {}

st.write(f"Sesión activa: **{usuario_activo}** | Sucursal Autorizada: **[{codigo_tienda_activo}] {nombre_tienda_activo}**")
st.divider()

# ==========================================
# DESPLIEGUE DEL CATÁLOGO DE ARTÍCULOS
# ==========================================
st.subheader("📋 Formulario de Artículos")

# Contenedor para almacenar lo que el usuario digite en esta sesión actual
cantidades_actuales = {}

for prod in df_productos:
    cod_prod = prod.get('codigo', '')
    col1, col2, col3 = st.columns([1, 2, 1.5])
    
    with col1:
        id_foto = str(prod.get('id_imagen_drive', '')).strip()
        if id_foto and id_foto not in ["", "0", "0.0", "None", "Sin Foto"]:
            st.image(f"https://googleusercontent.com{id_foto}", width=110)
        else:
            st.info("📸 Sin foto")
            
    with col2:
        st.markdown(f"### {prod.get('nombre', 'Producto')}項目")
        st.caption(f"Código de Artículo: {cod_prod}")
        
    with col3:
        # Se define una llave dinámica única para que Streamlit renderice el input desde 0
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
# BOTÓN DE PROCESAMIENTO Y ENVÍO DE PEDIDO CENTRAL
# ==========================================
st.sidebar.markdown("---")
st.sidebar.subheader("Confirmación General")

if cantidades_actuales:
    st.sidebar.write(f"Items seleccionados: **{len(cantidades_actuales)}**")
    
    if st.sidebar.button("🚀 Enviar Pedido Completo", use_container_width=True):
        # 1. Generamos la fecha exacta del lote
        ahora = datetime.now()
        fecha_registro = ahora.strftime("%Y-%m-%d %H:%M:%S")
        
        # 2. CREACIÓN DEL NÚMERO DE PEDIDO ÚNICO DE REFERENCIA (Llave primaria para Modificar/Eliminar)
        # Formato: PED-AñoMesDia-HoraMinSeg-CodigoTienda-Usuario
        id_pedido_referencia = f"PED-{ahora.strftime('%Y%m%d-%H%M%S')}-{codigo_tienda_activo}-{usuario_activo.upper()}"
        
        exito_envios = True
        
        # Enviar cada artículo del lote de forma consecutiva compartiendo el mismo ID de pedido
        for cod_art, cant_art in cantidades_actuales.items():
            datos_pedido = {
                "fecha": fecha_registro,
                "codigo_tienda": f"{id_pedido_referencia} | {codigo_tienda_activo}", # Guardamos el ID de referencia al inicio del campo
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
            st.balloon()
            # Forzamos una recarga limpia para resetear todos los controles gráficos a cero de inmediato
            st.toast(f"Referencia de búsqueda generada: {id_pedido_referencia}")
            st.rerun()
        else:
            st.sidebar.error("Ocurrió un inconveniente al guardar algunas líneas en Google Sheets.")
else:
    st.sidebar.caption("Suma cantidades en el catálogo para habilitar el envío.")
