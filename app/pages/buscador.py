# importar streamlit
import streamlit as st
import streamlit.components.v1 as components
# importamos la funcion obtener datos de nuestro api.py
from app.api import obtener_datos, actualizar_ofertas_manual
from datetime import datetime, date
from app.formato_excel import dar_formato
from st_keyup import st_keyup
import pandas as pd
import io
import json
import html
import textwrap


LOCAL_STORAGE_JS = """
export default function(component) {
    const { data, setStateValue } = component;

    const storageKey = "vs_compras_ofertadas";

    let guardadas = [];

    try {
        const valorGuardado = localStorage.getItem(storageKey);

        guardadas = valorGuardado
            ? JSON.parse(valorGuardado)
            : [];
    } catch (error) {
        guardadas = [];
    }

    const recibidas = Array.isArray(data)
        ? data
        : [];

    const combinadas = [
        ...new Set([
            ...guardadas,
            ...recibidas
        ])
    ];

    const guardadasOrdenadas = [...guardadas].sort();
    const combinadasOrdenadas = [...combinadas].sort();

    const cambioLocalStorage =
        JSON.stringify(guardadasOrdenadas) !==
        JSON.stringify(combinadasOrdenadas);

    if (cambioLocalStorage) {
        try {
            localStorage.setItem(
                storageKey,
                JSON.stringify(combinadas)
            );
        } catch (error) {
            console.error(
                "[V&S] No se pudo guardar localStorage:",
                error
            );
        }
    }

    const faltanComprasEnPython = guardadas.some(
        codigo => !recibidas.includes(codigo)
    );

    if (faltanComprasEnPython) {
        setStateValue(
            "compras",
            combinadas
        );
    }
}
"""

local_storage_compras = st.components.v2.component(
    "vs_local_storage_compras",
    js=LOCAL_STORAGE_JS
)


PANEL_BRIDGE_JS = """
export default function(component) {
    const { setTriggerValue } = component;

    function recibirAccionPanel(event) {
        if (
            event.data?.type !==
            "VS_PANEL_MARCAR_OFERTADA"
        ) {
            return;
        }

        const codigo = String(
            event.data.codigo || ""
        ).trim();

        if (!codigo) {
            return;
        }

        setTriggerValue(
            "ofertar",
            codigo
        );
    }

    window.top.addEventListener(
        "message",
        recibirAccionPanel
    );

    return () => {
        window.top.removeEventListener(
            "message",
            recibirAccionPanel
        );
    };
}
"""

panel_action_bridge = st.components.v2.component(
    "vs_panel_action_bridge",
    js=PANEL_BRIDGE_JS
)



# Fechas

filtrar_por_fecha = st.checkbox(
    "Filtrar por fecha de publicación"
)

if filtrar_por_fecha:
    fecha_inicio = st.date_input(
        "Desde",
        value=date.today(),
        max_value=date.today()
    )

    fecha_fin = st.date_input(
        "Hasta",
        value=date.today(),
        max_value=date.today()
    )

    if fecha_inicio > fecha_fin:
        st.error("La fecha inicial no puede ser mayor que la fecha final.")
        st.stop()

else:
    fecha_inicio = None
    fecha_fin = None

# equivalente a un h1 de html (cada vez que se abra la pagina se vera ese titulo)
st.title("Buscador de Compras Ágiles")

# Inicializar el Session State para guardar los datos entre clics
if "datos_busqueda" not in st.session_state:
    st.session_state.datos_busqueda = None

if "compras_ofertadas" not in st.session_state:
    st.session_state.compras_ofertadas = set()

if "actividad_reciente" not in st.session_state:
    st.session_state.actividad_reciente = []

resultado_storage = local_storage_compras(
    data=sorted(st.session_state.compras_ofertadas),
    key="vs_local_storage_compras",
    on_compras_change=lambda: None
)

compras_guardadas = getattr(
    resultado_storage,
    "compras",
    None
)

if compras_guardadas:
    st.session_state.compras_ofertadas.update(
        compras_guardadas
    )

#diccionario con regiones 
REGIONES = {
    "Arica y Parinacota": 15,
    "Tarapacá": 1,
    "Antofagasta": 2,
    "Atacama": 3,
    "Coquimbo": 4,
    "Valparaíso": 5,
    "Metropolitana": 13,
    "O'Higgins": 6,
    "Maule": 7,
    "Ñuble": 16,
    "Biobío": 8,
    "La Araucanía": 9,
    "Los Ríos": 14,
    "Los Lagos": 10,
    "Aysén": 11,
    "Magallanes": 12
}

LLAMADOS = {
    "Primer Llamado" : 1,
    "Segundo Llamado": 2
}

# creamos y mostramos el selectbox donde el texto seran las claves del diccionario (nombres)
region_nombre = st.selectbox(
    "Region",
    REGIONES.keys()
)

# aca obtenemso el numero. Si el usuario elige tarapaca , region valdra 1 (esto ya que region nombre almacena el nombre de la region)
region = REGIONES[region_nombre]

llamado_nombre = st.selectbox(
    "Llamado",
    LLAMADOS.keys()
)

llamado = LLAMADOS[llamado_nombre]


if st.button("Buscar"):

    with st.spinner("Buscando oportunidades..."):
        oportunidades = obtener_datos(
            region,
            llamado,
            fecha_inicio,
            fecha_fin,
            limite=9000
        )

    if not oportunidades:
        st.warning("No se encontraron oportunidades.")
        st.session_state.datos_busqueda = None
        st.stop()

    st.success(
        f"Se encontraron {len(oportunidades)} oportunidades"
    )

    datos = []

    for item in oportunidades:

        if llamado == 1:
            fecha_cierre = item["fecha_cierre_primer_llamado"]
        else:
            fecha_cierre = item["fecha_cierre_segundo_llamado"]

        datos.append(
            {
                "Codigo": item["codigo"],
                "Nombre": item["nombre"],
                "Organismo": item["organismo"],
                "Presupuesto": item["monto_disponible_clp"],
                "Fecha de cierre": fecha_cierre,
                "Ofertas": item.get("total_ofertas_reales"),
                "Fecha de actualización de ofertas": item.get("fecha_actualizacion_ofertas"),
                "Ficha": (
                    "https://buscador.mercadopublico.cl/"
                    f"ficha?code={item['codigo']}"
                )
            }
        )

    st.session_state.datos_busqueda = datos


def registrar_actividad(codigo, nombre, estado, fila):
    actividad = st.session_state.actividad_reciente

    actividad = [
        compra
        for compra in actividad
        if compra["codigo"] != codigo
    ]

    actividad.insert(
        0,
        {
            "codigo": codigo,
            "nombre": nombre,
            "estado": estado,
            "fila": fila
        }
    )

    st.session_state.actividad_reciente = actividad[:5]


def marcar_ofertada_desde_panel():
    resultado = st.session_state.get(
        "vs_panel_action_bridge"
    )

    codigo = getattr(
        resultado,
        "ofertar",
        None
    )

    if not codigo:
        return

    codigo = str(codigo).strip()

    st.session_state.compras_ofertadas.add(codigo)

    compra_panel = next(
        (
            compra
            for compra in st.session_state.actividad_reciente
            if compra["codigo"] == codigo
        ),
        None
    )

    if compra_panel:
        registrar_actividad(
            codigo=codigo,
            nombre=compra_panel["nombre"],
            estado="✅ Ofertada",
            fila=compra_panel.get("fila", 0)
        )

panel_action_bridge(
    on_ofertar_change=marcar_ofertada_desde_panel,
    key="vs_panel_action_bridge"
)


# Si ya existen datos guardados en la sesion , los mostramos y habilitamos la exportacion
if st.session_state.datos_busqueda:
    # Convertimos a DataFrame
    df = pd.DataFrame(st.session_state.datos_busqueda)

    df["Fecha de cierre"] = (
        pd.to_datetime(
            df["Fecha de cierre"],
            format="ISO8601",
            errors="coerce",
            utc=True
        )
        .dt.tz_convert("America/Santiago")
        .dt.tz_localize(None)
    )

    df["Fecha de actualización de ofertas"] = (
        pd.to_datetime(
            df["Fecha de actualización de ofertas"],
            format="ISO8601",
            errors="coerce",
            utc=True
        )
        .dt.tz_convert("America/Santiago")
        .dt.tz_localize(None)
    )

    # Filtro local
    palabra_busqueda = st_keyup(
        "Filtrar resultados por nombre",
        placeholder="Ej: silla, notebook, pintura...",
        debounce=300,
        key="filtro_nombre"
    )

    # Copia para no modificar resultados originales
    df_filtrado = df.copy()

    ordenar_por = st.selectbox(
        "Ordenar por",
        [
            "Sin orden adicional",
            "Fecha de cierre",
            "Presupuesto",
            "Nombre",
            "Código",
            "Ofertas"
        ],
        key="ordenar_por"
    )

    orden_descendente = st.toggle(
        "Orden descendente",
        value=False,
        key="orden_descendente"
    )

    if palabra_busqueda and palabra_busqueda.strip():
        df_filtrado = df_filtrado[
                df_filtrado["Nombre"]
                .fillna("")
                .str.contains(
                    palabra_busqueda.strip(),
                    case=False,
                    na=False,
                    regex=False
                )
        ]

    if ordenar_por != "Sin orden adicional":
        columnas_orden = {
            "Fecha de cierre": "Fecha de cierre",
            "Presupuesto": "Presupuesto",
            "Nombre": "Nombre",
            "Código": "Codigo",
            "Ofertas": "Ofertas"
        }

        columna_orden = columnas_orden[ordenar_por]

        df_filtrado = (
            df_filtrado
            .sort_values(
                by=columna_orden,
                ascending=not orden_descendente,
                na_position="last"
            )
            .reset_index(drop=True)
        )
    else:
        df_filtrado = df_filtrado.reset_index(
            drop=True
        )

    st.caption(
        f"Mostrando {len(df_filtrado)} de {len(df)} oportunidades"
    )


    def colorear_ofertas(valor):
        if pd.isna(valor):
            return (
                "background-color: #F1F3F5;"
                "color: #6C757D;"
                "font-weight: 600;"
                "text-align: center;"
            )

        if valor <= 4:
            return (
                "background-color: #D9F2E3;"
                "color: #14532D;"
                "font-weight: 700;"
                "text-align: center;"
            )

        if valor < 7:
            return (
                "background-color: #FFF1BF;"
                "color: #7A4E00;"
                "font-weight: 700;"
                "text-align: center;"
            )

        return (
            "background-color: #F8D7DA;"
            "color: #842029;"
            "font-weight: 700;"
            "text-align: center;"
        )

    columnas_a_ocultar = []

    df_filtrado.insert(
        0,
        "Ofertar",
        df_filtrado["Codigo"].apply(
            lambda codigo: (
                "✅ Ofertada"
                if codigo in st.session_state.compras_ofertadas
                else "Ofertar"
            )
        )
    )

    df_filtrado.insert(
        1,
        "Actualizar",
        "🔄"
    )

    df_mostrar = df_filtrado.drop(
        columns=columnas_a_ocultar,
        errors="ignore"
    )

    df_estilizado = (
        df_mostrar.style
        .map(
            colorear_ofertas,
            subset=["Ofertas"]
        )
        .format(
            {
                "Ofertas": lambda valor: (
                    ""
                    if pd.isna(valor)
                    else f"{int(valor)}"
                )
            }
        )
    )

    # Dejamos editable solamente la columna Actualizar
    columnas_bloqueadas = [
        columna
        for columna in df_mostrar.columns
        if columna not in ["Ofertar", "Actualizar"]
    ]


    def ofertar_compra():
        click = st.session_state.get("click_ofertar")

        if not click:
            return

        numero_fila = click["row"]

        codigo = str(
            df_filtrado.iloc[numero_fila]["Codigo"]
        ).strip()

        nombre = str(
            df_filtrado.iloc[numero_fila]["Nombre"]
        ).strip()

        st.session_state.compras_ofertadas.add(codigo)
        st.session_state["codigo_para_ofertar"] = codigo

        registrar_actividad(
            codigo=codigo,
            nombre=nombre,
            estado="✅ Ofertada",
            fila=numero_fila
        )


    def actualizar_ofertas_fila():
        click = st.session_state.get("click_actualizar_ofertas")

        if not click:
            return

        numero_fila = click["row"]

        codigo = str(
            df_filtrado.iloc[numero_fila]["Codigo"]
        ).strip()

        nombre = str(
            df_filtrado.iloc[numero_fila]["Nombre"]
        ).strip()

        resultado = actualizar_ofertas_manual(codigo)

        if resultado is None:
            st.session_state["error_actualizacion_ofertas"] = codigo
            return

        nuevo_total = resultado["total_ofertas_reales"]
        nueva_fecha = resultado.get(
            "fecha_actualizacion_ofertas"
        )

        for compra in st.session_state.datos_busqueda:
            if compra["Codigo"] == codigo:
                compra["Ofertas"] = nuevo_total

                if "Fecha de actualización de ofertas" in compra:
                    compra[
                        "Fecha de actualización de ofertas"
                    ] = nueva_fecha

                break

        if codigo in st.session_state.compras_ofertadas:
            estado_panel = "✅ Ofertada"
        else:
            cantidad = int(nuevo_total)

            estado_panel = (
                f"{cantidad} oferta"
                if cantidad == 1
                else f"{cantidad} ofertas"
            )

        registrar_actividad(
            codigo=codigo,
            nombre=nombre,
            estado=estado_panel,
            fila=numero_fila
        )

        st.session_state.pop(
            "tabla_compras",
            None
        )

        st.session_state["resultado_actualizacion_ofertas"] = {
            "codigo": codigo,
            "total": nuevo_total
        }


    df_editado = st.data_editor(
        df_estilizado,
        hide_index=True,
        width="stretch",
        disabled=columnas_bloqueadas,
        key="tabla_compras",
        column_config={
            "Ofertas": st.column_config.NumberColumn(
                "Ofertas",
                format="%d"
            ),
            "Ficha": st.column_config.LinkColumn(
                "Ficha",
                display_text="🔗 Revisar"
            ),
            "Presupuesto": st.column_config.NumberColumn(
                "Presupuesto",
                format="$%d"
            ),
            "Fecha de cierre": st.column_config.DatetimeColumn(
                "Fecha de cierre",
                format="DD-MM-YYYY HH:mm"
            ),
            "Fecha de actualización de ofertas": st.column_config.DatetimeColumn(
                "Fecha de actualización de ofertas",
                format="DD-MM-YYYY HH:mm"
            ),
            "Actualizar": st.column_config.ButtonColumn(
                "",
                help="Actualizar total de ofertas",
                width="small",
                alignment="center",
                pinned=True,
                type="tertiary",
                on_click=actualizar_ofertas_fila,
                key="click_actualizar_ofertas"
            ),
            "Ofertar": st.column_config.ButtonColumn(
                "",
                help="Abrir esta compra para ofertar",
                width="small",
                alignment="center",
                pinned=True,
                type="secondary",
                on_click=ofertar_compra,
                key="click_ofertar"
            )
        }
    )

    if "resultado_actualizacion_ofertas" in st.session_state:
        dato = st.session_state.pop(
            "resultado_actualizacion_ofertas"
        )

        st.toast(
            f'{dato["codigo"]}: {dato["total"]} ofertas',
            icon="🔄"
        )

    if "error_actualizacion_ofertas" in st.session_state:
        codigo_error = st.session_state.pop(
            "error_actualizacion_ofertas"
        )

        st.error(
            f"No fue posible actualizar {codigo_error}."
        )


    actividad = st.session_state.actividad_reciente

    if actividad:
        tarjetas = ""

        for compra in actividad:
            codigo_seguro = html.escape(
                str(compra["codigo"])
            )

            nombre_seguro = html.escape(
                str(compra["nombre"])
            )

            estado_seguro = html.escape(
                str(compra["estado"])
            )

            fila_segura = int(
                compra.get("fila", 0)
            )

            tarjetas += textwrap.dedent(
                f"""
                <div class="vs-actividad-item">
                    <div class="vs-actividad-codigo">
                        {codigo_seguro}
                    </div>

                    <div class="vs-actividad-nombre">
                        {nombre_seguro}
                    </div>

                    <div class="vs-actividad-estado">
                        {estado_seguro}
                    </div>

                    <button
                        type="button"
                        class="vs-ir-fila"
                        data-codigo="{codigo_seguro}"
                        data-fila="{fila_segura}"
                    >
                        ↩ Ir a la fila
                    </button>

                    <button
                        type="button"
                        class="vs-abrir-compra"
                        data-codigo="{codigo_seguro}"
                    >
                        🚀 Abrir compra
                    </button>
                </div>
                """
            ).strip()

        st.html(
            textwrap.dedent(
                f"""
                <style>
                    .vs-actividad-panel {{
                        position: fixed;
                        right: 18px;
                        bottom: 18px;
                        width: 330px;
                        max-height: 280px;
                        overflow-y: auto;
                        z-index: 999999;
                        padding: 14px;
                        border: 1px solid rgba(128, 128, 128, 0.30);
                        border-radius: 12px;
                        background: white;
                        color: #1f2937;
                        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
                    }}

                    .vs-actividad-titulo {{
                        margin-bottom: 10px;
                        font-size: 15px;
                        font-weight: 700;
                    }}

                    .vs-actividad-item {{
                        margin-bottom: 9px;
                        padding: 10px;
                        border: 1px solid rgba(128, 128, 128, 0.22);
                        border-radius: 9px;
                        background: #f8f9fa;
                    }}

                    .vs-actividad-item:last-child {{
                        margin-bottom: 0;
                    }}

                    .vs-actividad-codigo {{
                        font-size: 13px;
                        font-weight: 700;
                    }}

                    .vs-actividad-nombre {{
                        margin-top: 3px;
                        font-size: 12px;
                        line-height: 1.25;
                        opacity: 0.78;
                    }}

                    .vs-actividad-estado {{
                        margin-top: 7px;
                        font-size: 13px;
                        font-weight: 700;
                    }}

                    .vs-ir-fila {{
                        width: 100%;
                        margin-top: 9px;
                        padding: 7px 10px;
                        border: 1px solid #2563eb;
                        border-radius: 7px;
                        background: transparent;
                        color: #2563eb;
                        font-size: 12px;
                        font-weight: 700;
                        cursor: pointer;
                    }}

                    .vs-ir-fila:hover {{
                        background: #2563eb;
                        color: white;
                    }}

                    .vs-abrir-compra {{
                        width: 100%;
                        margin-top: 7px;
                        padding: 7px 10px;
                        border: 1px solid #16a34a;
                        border-radius: 7px;
                        background: #16a34a;
                        color: white;
                        font-size: 12px;
                        font-weight: 700;
                        cursor: pointer;
                    }}

                    .vs-abrir-compra:hover {{
                        background: #15803d;
                        border-color: #15803d;
                    }}
                </style>

                <div class="vs-actividad-panel">
                    <div class="vs-actividad-titulo">
                        Últimas compras revisadas
                    </div>

                    {tarjetas}
                </div>

                <script>
                (() => {{
                    function encontrarCodigo(
                        contenedor,
                        codigo
                    ) {{
                        const walker =
                            document.createTreeWalker(
                                contenedor,
                                NodeFilter.SHOW_TEXT
                            );

                        let nodo;

                        while (
                            (nodo = walker.nextNode())
                        ) {{
                            if (
                                nodo.nodeValue?.trim() ===
                                codigo
                            ) {{
                                return nodo.parentElement;
                            }}
                        }}

                        return null;
                    }}

                    function obtenerTabla() {{
                        return (
                            document.querySelector(
                                '[data-testid="stDataFrame"]'
                            ) ||
                            document.querySelector(
                                '[data-testid="stDataEditor"]'
                            )
                        );
                    }}

                    function obtenerContenedorScrollable(
                        tabla
                    ) {{
                        const candidatos = [
                            tabla,
                            ...tabla.querySelectorAll("*")
                        ].filter((elemento) => {{
                            const estilo =
                                window.getComputedStyle(
                                    elemento
                                );

                            const permiteScroll =
                                estilo.overflowY === "auto" ||
                                estilo.overflowY === "scroll";

                            return (
                                permiteScroll &&
                                elemento.scrollHeight >
                                elemento.clientHeight + 10
                            );
                        }});

                        candidatos.sort(
                            (a, b) =>
                                (
                                    b.scrollHeight -
                                    b.clientHeight
                                ) -
                                (
                                    a.scrollHeight -
                                    a.clientHeight
                                )
                        );

                        return candidatos[0] || null;
                    }}

                    function destacar(elemento) {{
                        if (!elemento) {{
                            return;
                        }}

                        const fondoAnterior =
                            elemento.style.backgroundColor;

                        elemento.style.backgroundColor =
                            "rgba(37, 99, 235, 0.30)";

                        setTimeout(() => {{
                            elemento.style.backgroundColor =
                                fondoAnterior;
                        }}, 1600);
                    }}

                    async function irAFila(
                        codigo,
                        fila
                    ) {{
                        const tabla = obtenerTabla();

                        if (!tabla) {{
                            console.error(
                                "[V&S] No se encontró la tabla"
                            );
                            return;
                        }}

                        let elementoCodigo =
                            encontrarCodigo(
                                tabla,
                                codigo
                            );

                        if (elementoCodigo) {{
                            elementoCodigo.scrollIntoView({{
                                behavior: "smooth",
                                block: "center",
                                inline: "nearest"
                            }});

                            destacar(elementoCodigo);
                            return;
                        }}

                        const contenedor =
                            obtenerContenedorScrollable(
                                tabla
                            );

                        if (!contenedor) {{
                            console.error(
                                "[V&S] No se encontró el scroll interno"
                            );
                            return;
                        }}

                        const alturaFila = 35;

                        contenedor.scrollTo({{
                            top: Math.max(
                                0,
                                fila * alturaFila
                            ),
                            behavior: "smooth"
                        }});

                        await new Promise(
                            resolver =>
                                setTimeout(
                                    resolver,
                                    500
                                )
                        );

                        elementoCodigo =
                            encontrarCodigo(
                                tabla,
                                codigo
                            );

                        if (elementoCodigo) {{
                            elementoCodigo.scrollIntoView({{
                                behavior: "smooth",
                                block: "center",
                                inline: "nearest"
                            }});

                            destacar(elementoCodigo);
                        }}
                    }}

                    document
                        .querySelectorAll(".vs-ir-fila")
                        .forEach((boton) => {{
                            boton.addEventListener(
                                "click",
                                () => {{
                                    irAFila(
                                        boton.dataset.codigo,
                                        Number(
                                            boton.dataset.fila
                                        )
                                    );
                                }}
                            );
                        }});

                    document
                        .querySelectorAll(
                            ".vs-abrir-compra"
                        )
                        .forEach((boton) => {{
                            boton.addEventListener(
                                "click",
                                () => {{
                                    const codigo =
                                        boton.dataset.codigo;

                                    window.top.postMessage(
                                        {{
                                            type:
                                                "VS_ABRIR_COMPRA",
                                            codigo: codigo
                                        }},
                                        "*"
                                    );

                                    window.top.postMessage(
                                        {{
                                            type:
                                                "VS_PANEL_MARCAR_OFERTADA",
                                            codigo: codigo
                                        }},
                                        "*"
                                    );
                                }}
                            );
                        }});
                }})();
                </script>
                """
            ).strip(),
            unsafe_allow_javascript=True
        )


    codigo_para_ofertar = st.session_state.pop(
        "codigo_para_ofertar",
        None
    )

    if codigo_para_ofertar:
        codigo_js = json.dumps(codigo_para_ofertar)

        components.html(
            f"""
            <script>
                window.top.postMessage(
                    {{
                        type: "VS_ABRIR_COMPRA",
                        codigo: {codigo_js}
                    }},
                    "*"
                );

                window.top.postMessage(
                    {{
                        type: "VS_PANEL_MARCAR_OFERTADA",
                        codigo: {codigo_js}
                    }},
                    "*"
                );
            </script>
            """,
            height=0
        )

        st.success(
            f"Abriendo compra para ofertar: "
            f"{codigo_para_ofertar}"
        )
    

    # Crear buffer para almacenar el Excel en memoria
    buffer = io.BytesIO()

    # Escribe el Excel dentro del buffer
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_filtrado.drop(
            columns=["Ofertar", "Actualizar"],
            errors="ignore"
        ).to_excel(writer, index=False, sheet_name="Informe")
        ws = writer.sheets["Informe"]
        dar_formato(ws)

    nombre_archivo = f"reporte_{datetime.now():%Y%m%d_%H%M%S}.xlsx"

    st.download_button(
        label="Descargar Excel",
        data=buffer.getvalue(),
        file_name=nombre_archivo,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )