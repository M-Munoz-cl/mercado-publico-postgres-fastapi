import io

import streamlit as st
# componente que permite pegar imagenes
from streamlit_paste_button import paste_image_button as pbutton
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas



# Estado inicial
if "pdf_generado" not in st.session_state:
    st.session_state.pdf_generado = None

if "contador_imagen" not in st.session_state:
    st.session_state.contador_imagen = 0

if "contador_pegado" not in st.session_state:
    st.session_state.contador_pegado = 0


def limpiar_formulario():
    # Limpiar campos de texto
    st.session_state.titulo = ""
    st.session_state.descripcion = ""

    # Cambiar las keys hace que Streamlit cree widgets nuevos y vacíos
    st.session_state.contador_imagen += 1
    st.session_state.contador_pegado += 1

    # Quitar el PDF anterior
    st.session_state.pdf_generado = None



def generar_pdf(titulo, imagen, descripcion):
    # Crear espacio en memoria que streamlit usara despues para descargar el pdf
    buffer = io.BytesIO()
    # Crear el documento PDF (lugar donde se almacena , tamaño de la hoja)
    pdf = canvas.Canvas(buffer, pagesize=A4)

    ancho_pagina, alto_pagina = A4

    # Margenes
    margen_izquierdo = 50
    margen_derecho = 50
    ancho_disponible = ancho_pagina - margen_izquierdo - margen_derecho

    # Título
    tamano_titulo = 20
    pdf.setFont("Helvetica-Bold", tamano_titulo)

    palabras_titulo = titulo.split()
    lineas_titulo = []
    linea_actual = ""

    for palabra in palabras_titulo:
        linea_prueba = f"{linea_actual} {palabra}".strip()

        ancho_linea = pdf.stringWidth(
            linea_prueba,
            "Helvetica-Bold",
            tamano_titulo
        )

        if ancho_linea <= ancho_disponible:
            linea_actual = linea_prueba
        else:
            lineas_titulo.append(linea_actual)
            linea_actual = palabra

    if linea_actual:
        lineas_titulo.append(linea_actual)

    posicion_titulo_y = alto_pagina - 60

    for linea_titulo in lineas_titulo:
        pdf.drawCentredString(
            ancho_pagina / 2,
            posicion_titulo_y,
            linea_titulo
        )

        posicion_titulo_y -= 24

    # Imagen
    # Primero convertir imagen a formato compatible
    imagen_pil = Image.open(imagen) if hasattr(imagen, "read") else imagen

    if imagen_pil.mode in ("RGBA", "P"):
        imagen_pil = imagen_pil.convert("RGB")
    
    imagen_buffer = io.BytesIO()
    imagen_pil.save(imagen_buffer, format="JPEG")
    imagen_buffer.seek(0)

    # Ajustar tamaño manteniendo
    ancho_original, alto_original = imagen_pil.size

    ancho_maximo = 350
    alto_maximo = 280

    proporcion = min(
        ancho_maximo / ancho_original,
        alto_maximo / alto_original
    )

    ancho_imagen = ancho_original * proporcion
    alto_imagen = alto_original * proporcion

    posicion_x = (ancho_pagina - ancho_imagen) / 2
    posicion_y = posicion_titulo_y - 30 - alto_imagen

    pdf.drawImage(
        ImageReader(imagen_buffer),
        posicion_x,
        posicion_y,
        width=ancho_imagen,
        height=alto_imagen
    )

    # Descripcion

    posicion_texto_y = posicion_y - 40

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(
        margen_izquierdo,
        posicion_texto_y,
        "Descripción"
    )

    posicion_texto_y -= 25
    pdf.setFont("Helvetica", 11)

    # Respetar los saltos de línea escritos por el usuario
    parrafos = descripcion.splitlines()

    for parrafo in parrafos:

        # Línea vacía: dejar espacio entre párrafos
        if not parrafo.strip():
            posicion_texto_y -= 16
            continue

        palabras = parrafo.split()
        linea = ""

        for palabra in palabras:
            linea_prueba = f"{linea} {palabra}".strip()

            ancho_linea = pdf.stringWidth(
                linea_prueba,
                "Helvetica",
                11
            )

            if ancho_linea <= ancho_disponible:
                linea = linea_prueba
            else:
                pdf.drawString(
                    margen_izquierdo,
                    posicion_texto_y,
                    linea
                )

                posicion_texto_y -= 16
                linea = palabra

                if posicion_texto_y < 50:
                    pdf.showPage()
                    pdf.setFont("Helvetica", 11)
                    posicion_texto_y = alto_pagina - 50

        if linea:
            pdf.drawString(
                margen_izquierdo,
                posicion_texto_y,
                linea
            )

            posicion_texto_y -= 16

        # Espacio después de cada párrafo
        posicion_texto_y -= 8

        if posicion_texto_y < 50:
            pdf.showPage()
            pdf.setFont("Helvetica", 11)
            posicion_texto_y = alto_pagina - 50

    pdf.save()

    buffer.seek(0)
    return buffer

col1, col2 = st.columns(2)

with col1:
    st.title("Creador de Ficha Técnica")

    titulo = st.text_input("Ingrese el título", placeholder="Ej: Extractor de aire mural", key="titulo")

    imagen_pegada = pbutton("Pegar imagen", key=f"imagen_pegada_{st.session_state.contador_pegado}")

    imagen_subida = st.file_uploader("O cargar imagen", type=["png", "jpg", "jpeg"], key=f"imagen_{st.session_state.contador_imagen}")

    if imagen_pegada.image_data is not None:
        imagen = imagen_pegada.image_data
    else:
        imagen = imagen_subida

    descripcion = st.text_area("Ingrese la descripción", placeholder="Ingrese la descripción del producto...", height=150, key="descripcion")

    st.divider()

    boton = st.button("Generar PDF")

    # Validacion de formulario
    if boton:
        if not titulo:
            st.warning("Debe tener un titulo")
        elif imagen is None:
            st.warning("Debe tener una imagen")
        elif not descripcion:
            st.warning("Debe tener una descripcion")
        else:
            pdf_generado = generar_pdf(
                titulo,
                imagen,
                descripcion
            )
            
            st.session_state.pdf_generado = pdf_generado.getvalue()

    if st.session_state.pdf_generado is not None:
        st.success("Datos completos, PDF generado")

        st.download_button(
            label="Descargar PDF",
            data=st.session_state.pdf_generado,
            file_name=titulo.strip().replace(" ", "_") + ".pdf",
            mime="application/pdf",
            use_container_width=True,
            on_click=limpiar_formulario
        )

        st.button(
            "Nueva ficha",
            on_click=limpiar_formulario,
            use_container_width=True
        )

with col2:
    st.title("Vista previa")

    if titulo:
        st.header(titulo)

    if imagen is not None:
        st.image(imagen, width=450)
    
    if descripcion:
        st.write(descripcion)


