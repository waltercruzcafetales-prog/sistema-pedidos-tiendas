import streamlit as st
import requests
from datetime import datetime 

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

# REQUERIMIENTO 1: El usuario solo puede escoger la tienda que tiene asignada
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

# REQUERIMIENTO 2: Forzar cantidades a 0 en pantalla al cambiar de tienda o usuario
llave_limpieza = f"tienda_{usuario_activo}_{codigo_tienda_activo}"
if "tienda_actual" not in st.session_state or st.session_state["tienda_actual"] != llave_limpieza:
    st.session_state["tienda_actual"] = llave_limpieza
    # Borramos cualquier rastro numérico de sesiones anteriores para obligar al renderizado en 0
    for key in list(st.session_state.keys()):
        if key.startswith("cant_"):
            del st.session_state[key]

st.write(f"Sesión activa: **{usuario_activo}** | Tienda: **[{codigo_tienda_activo}] {nombre_tienda_activo}**")
st.divider()

st.subheader("Catálogo de Productos")

# Diccionario interno temporal para agrupar los artículos antes de enviar
carrito_solicitudes = {}

for prod in df_productos:
    col1, col2, col3 = st.columns([1, 2, 1.5])
    cod_art = prod.get('codigo', '')
    
    with col1:
        id_foto = str(prod.get('id_imagen_drive', '')).strip()
        
        # MANTENIDO: Lógica idéntica de visualización que sí te cargó las fotos
        if id_foto and id_foto not in ["", "0", "0.0", "None", "Sin Foto"]:
            url_directa_foto = f"https://lh3.googleusercontent.com/d/{id_foto}"
            st.image(url_directa_foto, width=130)
        else:
            st.warning("Sin ID de foto")
            
    with col2:
        # CORREGIDO: Removido el carácter de texto plano que desalineaba las cajas
        st.markdown(f"### {prod.get('nombre', 'Producto Sin Nombre')}")
        st.caption(f"Código de Artículo: {cod_art}")
        
    with col3:
        # El input arranca estrictamente en 0 y guarda la persistencia de forma segura
        cantidad = st.number_input(
            "Cantidad a pedir:", 
            min_value=0, 
            step=1, 
            key=f"cant_{cod_art}"
        )
        if cantidad > 0:
            carrito_solicitudes[cod_art] = cantidad
                
    st.divider()

# ==========================================
# PANEL DE ENVIÓ CENTRALIZADO CON NÚMERO DE PEDIDO ÚNICO
# ==========================================
st.sidebar.markdown("---")
st.sidebar.subheader("Confirmación de Solicitud")

if carrito_solicitudes:
    st.sidebar.write(f"Artículos seleccionados: **{len(carrito_solicitudes)}**")
    
    # REQUERIMIENTO 3: Botón de envío global que genera una referencia para modificar/eliminar
    if st.sidebar.button("🚀 Enviar Pedido Completo", use_container_width=True):
        ahora = datetime.now()
        fecha_actual = ahora.strftime("%Y-%m-%d %H:%M:%S")
        
        # Estructura del ID único: PED-AñoMesDia-HoraMinutoSegundo-Tienda-Usuario
        id_pedido_referencia = f"PED-{ahora.strftime('%Y%m%d-%H%M%S')}-{codigo_tienda_activo}-{usuario_activo.upper()}"
        
        exito_operacion = True
        
        for codigo_item, cantidad_item in carrito_solicitudes.items():
            datos_pedido = {
                "fecha": fecha_actual,
                # Inyectamos el ID de referencia único junto al código de la tienda
                "codigo_tienda": f"{id_pedido_referencia} | {codigo_tienda_activo}",
                "tienda": nombre_tienda_activo,
                "codigo": codigo_item,
                "cantidad": cantidad_item,
                "usuario": usuario_activo
            }
            
            try:
                res = requests.post(URL_WEB_APP, json=datos_pedido, timeout=10)
                if res.status_code != 200:
                    exito_operacion = False
            except Exception:
                exito_operacion = False
                
        if exito_operacion:
            st.sidebar.success("🎉 ¡Pedido guardado exitosamente!")
            st.balloons() # Animación corregida en plural
            st.toast(f"Referencia de control generada: {id_pedido_referencia}")
            # Limpia los datos de pantalla de inmediato refrescando el formulario a ceros
            st.rerun()
        else:
            st.sidebar.error("Error al procesar el almacenamiento en Google Sheets.")
else:
    st.sidebar.caption("Modifica cantidades en el catálogo para procesar un pedido.")
