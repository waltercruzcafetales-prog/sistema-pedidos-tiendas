import streamlit as st
import requests
from datetime import datetime 

# Configuración inicial de la interfaz
st.set_page_config(page_title="Sistema de Pedidos", page_icon="🛍️", layout="wide")

# ==========================================
# CONFIGURACIÓN DEL ENLACE DE CONEXIÓN DIRECTO
# ==========================================
# REEMPLAZA ESTA URL POR TU URL REAL DE GOOGLE APPS SCRIPT
URL_WEB_APP = "https://script.google.com/macros/s/AKfycbyEuyPtExmCSmKF7NVdj9n2UWgoJQBOUyE0-2PQW9zSW3M1GN6puvTBdvRgtwO4r2bc/exec"

# ==========================================
# CARGA DE DATOS DESDE GOOGLE SHEETS
# ==========================================
@st.cache_data(ttl=60) # Actualiza los datos del catálogo cada 60 segundos
def cargar_datos_completos():
    try:
        response = requests.get(f"{URL_WEB_APP}?action=leer_todo", timeout=10)
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
lista_tiendas = datos_base.get("tiendas", [])

# ==========================================
# INTERFAZ DE USUARIO
# ==========================================
st.title("🛍️ Sistema de Solicitud de Pedidos")

st.sidebar.header("Identificación")
usuario_activo = st.sidebar.selectbox("Seleccione su Usuario:", lista_usuarios)

tienda_seleccionada = st.sidebar.selectbox(
    "Seleccione su Tienda:", 
    lista_tiendas, 
    format_func=lambda t: f"{t.get('codigo_tienda', '')} - {t.get('tienda', '')}"
)

codigo_tienda_activo = tienda_seleccionada.get('codigo_tienda', '')
nombre_tienda_activo = tienda_seleccionada.get('tienda', '')

st.write(f"Sesión activa: **{usuario_activo}** | Tienda: **[{codigo_tienda_activo}] {nombre_tienda_activo}**")
st.divider()

st.subheader("Catálogo de Productos")

for prod in df_productos:
    col1, col2, col3 = st.columns([1, 2, 1.5])
    
    with col1:
        id_foto = str(prod.get('id_imagen_drive', '')).strip()
        
        if id_foto and id_foto != "None" and id_foto != "":
            # MÉTODO PRÁCTICO: Creamos la URL directa usando el servidor de Google
            url_directa_foto = f"https://lh3.googleusercontent.com/d/{id_foto}"
            
            # Pasamos la URL directamente a st.image
            st.image(url_directa_foto, width=130)
        else:
            st.warning("Sin ID de foto")
            
    with col2:
        st.markdown(f"### {prod.get('nombre', 'Producto Sin Nombre')}")
        st.caption(f"Código de Artículo: {prod.get('codigo', 'N/A')}")
        
    with col3:
        cantidad = st.number_input(
            "Cantidad a pedir:", 
            min_value=0, 
            step=1, 
            key=f"cant_{prod.get('codigo', '')}"
        )
        
        if st.button("🛒 Solicitar", key=f"btn_{prod.get('codigo', '')}"):
            if cantidad > 0:
                fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                datos_pedido = {
                    "fecha": fecha_actual,
                    "codigo_tienda": codigo_tienda_activo,
                    "tienda": nombre_tienda_activo,
                    "codigo": prod.get('codigo', ''),
                    "cantidad": cantidad,
                    "usuario": usuario_activo
                }
                
                try:
                    res = requests.post(URL_WEB_APP, json=datos_pedido, timeout=10)
                    if res.status_code == 200:
                        st.success(f"¡Pedido guardado! {cantidad} unidad(es) de {prod.get('codigo', '')}")
                    else:
                        st.error("Google rechazó el almacenamiento de la fila.")
                except Exception as e:
                    st.error(f"No se pudo enviar el registro: {e}")
            else:
                st.error("Por favor, ingresa una cantidad mayor a 0.")
                
    st.divider()
