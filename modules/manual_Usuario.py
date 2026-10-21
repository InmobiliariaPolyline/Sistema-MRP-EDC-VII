import streamlit as st

def show():
    st.title("📖 Manual y Guía de Usuario - Flujo Operativo MRP")
    st.markdown("""
    Esta guía explica el **ciclo de vida completo y ordenado** dentro del Sistema MRP:
    desde el alta de datos maestros iniciales hasta el análisis de costos y cierre de proyectos.
    """)

    st.divider()

    # --- FLUJO SECUENCIAL VISUAL ---
    st.subheader("🔄 Mapa del Flujo Operativo")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.caption("1️⃣ INICIO")
        st.info("**Datos Maestros**\nMateriales y Proveedores")
    with col2:
        st.caption("2️⃣ PLANIFICACIÓN")
        st.info("**Proyectos**\nCreación de Obras")
    with col3:
        st.caption("3️⃣ ABASTECIMIENTO")
        st.info("**Compras**\nÓrdenes de Compra")
    with col4:
        st.caption("4️⃣ OPERACIÓN")
        st.info("**Almacén y Obra**\nStock y Asistencia")
    with col5:
        st.caption("5️⃣ FIN / CONTROL")
        st.info("**Análisis**\nReportes e Historial")

    st.divider()

    # --- PESTAÑAS DETALLADAS DEL FLUJO ---
    tab1, tab2, tab3, tab4, tab5, tab_faq = st.tabs([
        "1️⃣ Inicio: Datos Maestros",
        "2️⃣ Obras y Proyectos",
        "3️⃣ Compras y Proveedores",
        "4️⃣ Almacén y Personal",
        "5️⃣ Análisis y Auditoría",
        "❓ Ayuda y FAQ"
    ])

    # ETA PA 1
    with tab1:
        st.header("Paso 1: Configuración de Datos Maestros (Inicio)")
        st.write("""
        Antes de generar pedidos u obras, el sistema necesita conocer los **insumos y aliados comerciales**. 
        Sin estos datos preexistentes no es posible cotizar ni comprar.
        """)
        
        with st.expander("📦 Módulo Materiales", expanded=True):
            st.markdown("""
            - **Propósito:** Definir el catálogo de insumos utilizados en la empresa (ej. cemento, varillas, agregados).
            - **Acción del usuario:** Registrar el nombre del material, unidad de medida (m3, kg, unidad) y especificaciones técnicas.
            """)

        with st.expander("🚚 Módulo Proveedores"):
            st.markdown("""
            - **Propósito:** Registrar el directorio de empresas proveedoras de materiales y servicios.
            - **Acción del usuario:** Dar de alta RUC/DNI, razón social, contactos principales y condiciones comerciales.
            """)

    # ETAPA 2
    with tab2:
        st.header("Paso 2: Planificación de Obras")
        st.write("""
        Una vez configurados los materiales y proveedores, se procede a crear el destino final de los insumos.
        """)
        
        with st.expander("🏗️ Módulo Obras", expanded=True):
            st.markdown("""
            - **Propósito:** Dar de alta los proyectos activos (residenciales, edificaciones, habilitaciones urbanas).
            - **Acción del usuario:** Registrar la obra, ubicar su dirección/zona, asignar responsables y proyectar los requerimientos iniciales.
            """)

    # ETAPA 3
    with tab3:
        st.header("Paso 3: Ciclo de Compras y Abastecimiento")
        st.write("""
        Cuando una obra requiere materiales, se activa la lógica central del MRP mediante la compra formal.
        """)
        
        with st.expander("🧾 Módulo Órdenes de Compra", expanded=True):
            st.markdown("""
            - **Propósito:** Adquirir los materiales necesarios vinculando la **Obra de Destino** con el **Proveedor seleccionado**.
            - **Pasos para emitir una orden:**
                1. Crear un nuevo requerimiento / orden.
                2. Seleccionar la Obra que solicita el pedido.
                3. Elegir el Proveedor adjudicado.
                4. Seleccionar los materiales del catálogo y detallar cantidades y precios acordados.
                5. Confirmar y emitir el documento.
            """)

    # ETAPA 4
    with tab4:
        st.header("Paso 4: Recepción, Almacén y Operación Diaria")
        st.write("""
        Control de la ejecución física en el sitio de trabajo y recepción de los recursos adquiridos.
        """)
        
        with st.expander("🏬 Módulo Inventario", expanded=True):
            st.markdown("""
            - **Propósito:** Registrar el ingreso físico de los materiales comprados al almacén de obra y controlar las salidas/despachos.
            - **Acción del usuario:** Confirmar recepción contra la Orden de Compra y monitorear el stock disponible para evitar desabastecimientos.
            """)

        with st.expander("👷 Módulos Asistencia y Trabajadores"):
            st.markdown("""
            - **Propósito:** Control del recurso humano operativo en cada frente de obra.
            - **Acción del usuario:** Registrar la asistencia diaria del personal para el cálculo posterior de productividad e imprevistos de mano de obra.
            """)

    # ETAPA 5
    with tab5:
        st.header("Paso 5: Análisis, Auditoría y Respaldo (Fin)")
        st.write("""
        El ciclo se completa evaluando el desempeño financiero y operativo, además de resguardar la información.
        """)
        
        with st.expander("📊 Módulo Reportes", expanded=True):
            st.markdown("""
            - **Propósito:** Evaluar consumos, desviaciones de presupuesto y rendimiento de compras.
            - **Resultado:** Indicadores clave de desempeño (KPIs) sobre el uso del presupuesto por obra.
            """)

        with st.expander("📜 Módulos Historial y Respaldo"):
            st.markdown("""
            - **Historial:** Auditoría completa de quién creó, modificó o eliminó registros en la plataforma.
            - **Respaldo:** Generación de copias de seguridad de la base de datos para garantizar la integridad de la información.
            """)

    # AYUDA
    with tab_faq:
        st.header("Soporte y Preguntas Frecuentes")
        st.markdown("""
        - **¿Qué pasa si los cambios no se ven reflejados?**  
          Haz clic en el botón **'Actualizar datos'** en la esquina inferior del menú lateral.
        - **¿Cómo cambio mis credenciales de acceso?**  
          Haz clic en **'Mi cuenta'** en la barra lateral para actualizar tu clave de acceso.
        """)