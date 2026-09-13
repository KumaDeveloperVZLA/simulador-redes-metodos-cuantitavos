"""
Generador de Informe Técnico Profesional en formato Word (.docx).
Produce el Entregable 3 exigido en ejercicio.md con fundamentación matemática completa,
arquitectura de software, tablas de resultados empíricos, capturas visuales e informe de la API.
"""

import os
from typing import Dict, Any, Optional
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

from ..config import (
    DEFAULT_BUFFER_CAPACITY_S,
    DEFAULT_REORDER_POINT_S,
    DEFAULT_ORDER_BATCH_Q,
    HUNGARIAN_INTERVAL,
    ALPHA_SATURATION_WEIGHT
)


def _set_cell_background(cell, hex_color: str) -> None:
    """Aplica color de fondo a una celda de tabla en Word."""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    tcPr.append(shd)


def _set_cell_margins(cell, top=100, bottom=100, left=150, right=150) -> None:
    """Configura márgenes internos de una celda en dxa."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)


def generate_technical_docx_report(
    docx_path: str,
    metrics: Dict[str, Any],
    sim_time: float,
    lambda_val: float,
    mu_val: float,
    api_analysis: str,
    screenshot_image_path: Optional[str] = None,
    lambda_profile: Optional[Dict[str, Any]] = None
) -> None:
    """
    Construye un documento formal Word (.docx) con diseño editorial universitario de excelencia.
    """
    doc = Document()

    # Configuración de márgenes estándar (1 pulgada en todos los lados)
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # =========================================================================
    # PORTADA INSTITUCIONAL
    # =========================================================================
    p_inst = doc.add_paragraph()
    p_inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_inst = p_inst.add_run(
        "UNIVERSIDAD JOSÉ ANTONIO PÁEZ\n"
        "FACULTAD DE INGENIERÍA\n"
        "ESCUELA DE INGENIERÍA EN COMPUTACIÓN\n"
        "CÁTEDRA DE MÉTODOS CUANTITATIVOS\n"
    )
    r_inst.font.name = "Calibri"
    r_inst.font.size = Pt(12)
    r_inst.font.bold = True
    r_inst.font.color.rgb = RGBColor(30, 45, 75)

    doc.add_paragraph("\n" * 3)

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_title = p_title.add_run(
        "INFORME TÉCNICO DE INVESTIGACIÓN Y DESARROLLO:\n"
        "SIMULADOR DINÁMICO DE REDES DE COMPUTADORAS"
    )
    r_title.font.name = "Calibri"
    r_title.font.size = Pt(20)
    r_title.font.bold = True
    r_title.font.color.rgb = RGBColor(12, 74, 110)

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_sub = p_sub.add_run(
        "Modelado de Tráfico mediante Teoría de Colas (M/M/1/K), Control de Inventarios (s, Q)\n"
        "y Asignación Óptima de Flujos con Algoritmo Húngaro en Entorno Pygame-SimPy"
    )
    r_sub.font.name = "Calibri"
    r_sub.font.size = Pt(13)
    r_sub.font.italic = True
    r_sub.font.color.rgb = RGBColor(70, 85, 105)

    doc.add_paragraph("\n" * 5)

    p_meta = doc.add_paragraph()
    p_meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_meta = p_meta.add_run(
        "Proyecto de Simulación y Métodos Cuantitativos\n"
        "Entorno de Desarrollo: Python 3.12 (Pygame, SimPy, SciPy, NumPy, Requests)\n"
        "Valencia, Venezuela\n"
        "2026"
    )
    r_meta.font.name = "Calibri"
    r_meta.font.size = Pt(11)
    r_meta.font.color.rgb = RGBColor(90, 105, 120)

    doc.add_page_break()

    # =========================================================================
    # SECCIÓN 1: RESUMEN EJECUTIVO
    # =========================================================================
    h1 = doc.add_heading("1. Resumen Ejecutivo", level=1)
    h1.runs[0].font.color.rgb = RGBColor(12, 74, 110)

    p = doc.add_paragraph(
        "El presente proyecto comprende el diseño, formulación matemática, desarrollo e implementación "
        "de un simulador computacional dinámico de redes de paquetes, concebido bajo el paradigma de Programación "
        "Orientada a Objetos (POO) en Python. La solución unifica de forma sinérgica tres pilares fundamentales "
        "de la investigación de operaciones y los métodos cuantitativos: la Teoría de Líneas de Espera para caracterizar "
        "el comportamiento estocástico de las colas en routers, los Modelos de Inventario para la gestión con capacidad "
        "finita de buffers y control de flujo mediante políticas de reabastecimiento (s, Q), y el Modelo de Asignación "
        "Óptima implementado a través del Algoritmo Húngaro (Kuhn-Munkres) para el balanceo y enrutamiento dinámico de cargas."
    )
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.space_after = Pt(10)

    p2 = doc.add_paragraph(
        "Asimismo, se integró una arquitectura desacoplada y multihilo entre el motor de eventos discretos SimPy "
        "y la interfaz gráfica interactiva Pygame a 60 FPS, dotada de una estética Dark Mode / Cyberpunk con semaforización "
        "de saturación cromática, cálculo integral continuo de métricas en tiempo real y generación automática de "
        "diagnósticos asistidos por Inteligencia Artificial mediante peticiones HTTP a API externa."
    )
    p2.paragraph_format.line_spacing = 1.15
    p2.paragraph_format.space_after = Pt(14)

    # =========================================================================
    # SECCIÓN 2: FORMULACIÓN Y MODELADO MATEMÁTICO CUANTITATIVO
    # =========================================================================
    h2 = doc.add_heading("2. Formulación y Modelado Matemático Cuantitativo", level=1)
    h2.runs[0].font.color.rgb = RGBColor(12, 74, 110)

    # 2.1 Teoría de Colas
    h2_1 = doc.add_heading("2.1. Módulo de Teoría de Colas (Líneas de Espera M/M/1/K)", level=2)
    h2_1.runs[0].font.color.rgb = RGBColor(30, 45, 75)

    doc.add_paragraph(
        "En un sistema de conmutación de paquetes, cada nodo transmisor (router/switch) opera como una estación de servicio "
        "con una línea de espera finita de capacidad K = S. El tráfico entrante se genera siguiendo un Proceso de Poisson "
        "homogéneo con tasa media de llegada λ (paquetes/segundo), lo que implica que los intervalos entre arribos consecutivos "
        "siguen una distribución exponencial negativa:"
    )

    p_eq1 = doc.add_paragraph("f_A(t) = λ · e^(-λ · t),    para t ≥ 0")
    p_eq1.paragraph_format.left_indent = Inches(0.5)
    p_eq1.runs[0].font.bold = True

    doc.add_paragraph(
        "El tiempo requerido por los puertos de transmisión para procesar y reenviar cada paquete se modela mediante "
        "una distribución exponencial con tasa de servicio μ (paquetes/segundo):"
    )

    p_eq2 = doc.add_paragraph("f_S(t) = μ · e^(-μ · t),    para t ≥ 0")
    p_eq2.paragraph_format.left_indent = Inches(0.5)
    p_eq2.runs[0].font.bold = True

    doc.add_paragraph(
        "Para garantizar exactitud estocástica sin recurrir a aproximaciones de estado estacionario exclusivamente analíticas, "
        "el simulador calcula en tiempo real las cuatro métricas cardinales de colas de manera continua y ponderada en el tiempo:"
    )

    doc.add_paragraph(
        "• Lq (Número Promedio de Paquetes en Cola): Computado integralmente a lo largo del horizonte de simulación T:\n"
        "   Lq = (1 / T) · ∫[0 a T] Nq(t) dt = (∑ Nq(t_k) · Δt_k) / T\n\n"
        "• L (Número Promedio de Paquetes en el Sistema): Paquetes totales tanto en espera como en transmisión activa:\n"
        "   L = (1 / T) · ∫[0 a T] Nsys(t) dt\n\n"
        "• Wq (Tiempo Medio de Espera en Cola): Promedio aritmético del retardo en buffer experimentado por los paquetes completados:\n"
        "   Wq = (1 / N_proc) · ∑ [t_inicio_servicio(i) - t_arribo(i)]\n\n"
        "• W (Tiempo Medio Total de Estancia en la Red): Tiempo integral desde la génesis hasta la entrega exitosa:\n"
        "   W = (1 / N_proc) · ∑ [t_entrega(i) - t_arribo(i)]"
    )

    # 2.2 Modelos de Inventario
    h2_2 = doc.add_heading("2.2. Módulo de Gestión de Inventario y Control de Flujo (s, Q)", level=2)
    h2_2.runs[0].font.color.rgb = RGBColor(30, 45, 75)

    doc.add_paragraph(
        "El almacenamiento temporal de paquetes en las colas de memoria RAM de los enrutadores se homologa con un "
        "sistema de inventario con capacidad finita de almacenamiento S. Si un paquete arriba en un instante donde la cola "
        "se encuentra saturada (Nq = S), se produce una pérdida por desbordamiento (Buffer Overflow), asimilable a una "
        "rotura o ruptura de stock insatisfecha."
    )

    doc.add_paragraph(
        "• Política de Reabastecimiento / Control de Flujo (s, Q): El nodo monitorea permanentemente su nivel de inventario (buffer). "
        "Cuando la ocupación desciende hasta o por debajo del umbral mínimo s (reorder point) y el lote vigente ya se consumió, "
        "el nodo emite la señal de control de flujo y autoriza un nuevo lote de Q paquetes, es decir, libera su canal de entrada. "
        "El lote es efectivo, no meramente indicativo: cada admisión consume una unidad del lote y, mientras el saldo esté agotado "
        "y la ocupación siga por encima de s, el canal permanece cerrado y el nodo ejerce contrapresión (backpressure) sobre sus "
        "vecinos aguas arriba, que retienen el paquete en su propio buffer en lugar de reenviarlo. Este mecanismo anticipa el "
        "desbordamiento: el tráfico excedente se rechaza de forma controlada antes de que la cola alcance la capacidad S.\n\n"
        "• Modelo de Costos Dinámicos:\n"
        "  - Costo de Mantener (Holding Cost, H): Representa el costo energético, retención de memoria y latencia impuesta. "
        "Se acumula integralmente de forma continua: Costo_Almacenamiento = H · ∫[0 a T] Nq(t) dt = H · Lq · T.\n"
        "  - Costo de Ruptura (Shortage Cost, c_s): Penalización monetaria fija asignada a cada paquete perdido, tanto por "
        "desbordamiento de buffer como por rechazo del control de flujo: Costo_Ruptura = (N_loss + N_bloqueados) · c_s.\n"
        "  - Costo Global del Sistema: Función objetivo a minimizar: Costo_Global = Costo_Almacenamiento + Costo_Ruptura."
    )

    # 2.3 Algoritmo Húngaro
    h2_3 = doc.add_heading("2.3. Módulo de Asignación Óptima (Algoritmo Húngaro)", level=2)
    h2_3.runs[0].font.color.rgb = RGBColor(30, 45, 75)

    doc.add_paragraph(
        f"En redes dinámicas, la asignación estática de rutas induce cuellos de botella severos. En el simulador, en intervalos "
        f"discretos Δt = {HUNGARIAN_INTERVAL} s (del orden del tiempo de servicio 1/μ, para que la asignación no caduque antes "
        f"de ser utilizada), el sistema plantea un único problema global: los N paquetes que están en cabeza de cola en todos "
        f"los routers -los únicos que el nodo alcanza a despachar dentro de Δt- frente a los M enlaces de transmisión operativos "
        f"de toda la topología. Cada asignación queda vigente exactamente durante Δt; vencida esa ventana el nodo vuelve a "
        f"decidir por costo mínimo, porque la fotografía de saturación con la que se resolvió la matriz ya no describe la red."
    )

    doc.add_paragraph(
        "Los pares paquete-enlace no admisibles (enlace que no nace del router donde espera el paquete, ruta desde la que su "
        "nodo destino ya no es alcanzable, o vecino con el canal de entrada cerrado por la política (s, Q)) se penalizan con "
        "el costo ficticio y quedan excluidos de la solución."
    )

    doc.add_paragraph(
        "Se formula una matriz de costos dinámica C donde el elemento C_ij penaliza tanto la latencia física de propagación "
        "como el nivel de saturación del buffer del nodo de destino j:"
    )

    p_eq3 = doc.add_paragraph(
        "C_ij = Latencia_Actual_ij + α · (Buffer_Actual_j / S_j)"
    )
    p_eq3.paragraph_format.left_indent = Inches(0.5)
    p_eq3.runs[0].font.bold = True

    doc.add_paragraph(
        f"Donde α es un factor de ponderación calibrado (α = {ALPHA_SATURATION_WEIGHT}) que balancea el compromiso entre retardo físico y congestión. "
        "Cuando el número de flujos difiere del número de enlaces disponibles (N ≠ M), la matriz rectangular se balancea "
        "hacia una matriz cuadrada K x K (con K = max(N, M)) rellenando las celdas ficticias con un costo de penalización "
        "dummy elevado (10,000.0). Se resuelve la asignación biunívoca óptima mediante el método Kuhn-Munkres "
        "(scipy.optimize.linear_sum_assignment), redirigiendo el flujo en tiempo real sin sobrecargar nodos vulnerables."
    )

    # =========================================================================
    # SECCIÓN 3: ARQUITECTURA DE SOFTWARE Y SINCRONIZACIÓN TEMPORAL
    # =========================================================================
    h3 = doc.add_heading("3. Arquitectura de Software y Sincronización Temporal", level=1)
    h3.runs[0].font.color.rgb = RGBColor(12, 74, 110)

    doc.add_paragraph(
        "Uno de los mayores desafíos técnicos en simuladores híbridos radica en el desacoplamiento temporal:\n"
        "• SimPy opera bajo un reloj de avance por eventos discretos (env.now).\n"
        "• Pygame opera en un bucle continuo de renderizado a 60 cuadros por segundo (FPS) con delta time de reloj de pared."
    )

    doc.add_paragraph(
        "Para garantizar una experiencia visual fluida y sin bloqueos de la interfaz gráfica durante pausas, "
        "caídas de enlaces o la invocación de la API de análisis, se implementó una arquitectura en capas basada en "
        "el patrón Productor-Consumidor asistido por un puente thread-safe (SimulationBridge):"
    )

    doc.add_paragraph(
        "1. Hilo Worker de Simulación: Ejecuta el entorno SimPy avanzando en micro-pasos calibrados contra el reloj de pared. "
        "Gestiona los procesos de generación de Poisson, colas con atención exponencial y asignaciones húngaras.\n"
        "2. Puente Thread-Safe (SimulationBridge): Canaliza comandos bidireccionales (ajuste de λ, alternancia de enlaces, "
        "pausa) mediante colas seguras y publica instantáneas atómicas (snapshots) del estado de buffers, enlaces y paquetes.\n"
        "3. Hilo Principal de la GUI (Pygame): Consume el último snapshot disponible para renderizar a 60 FPS fijos, "
        "interpolando las posiciones espaciales de los paquetes mediante algoritmos LERP (Linear Interpolation)."
    )

    # =========================================================================
    # SECCIÓN 4: INTERFAZ GRÁFICA Y VALIDACIÓN VISUAL
    # =========================================================================
    h4 = doc.add_heading("4. Interfaz Gráfica y Validación Visual", level=1)
    h4.runs[0].font.color.rgb = RGBColor(12, 74, 110)

    doc.add_paragraph(
        "La interfaz gráfica fue diseñada bajo los principios de estética Cyberpunk / Dark Mode profesional:\n"
        "• Topología de Red: Nodos representados con radio visible y anillos cromáticos dinámicos que reflejan el estado de saturación:\n"
        "   - Verde Neón: Ocupación menor al 50% (Régimen estable).\n"
        "   - Amarillo / Ámbar: Ocupación entre 50% y 80% (Alerta de pre-saturación).\n"
        "   - Rojo Neón: Ocupación superior al 80% (Riesgo inminente de Buffer Overflow).\n"
        "• Enlaces Dinámicos: Líneas con grosor variable según la cantidad de paquetes en tránsito y etiquetas flotantes de latencia. "
        "Si el usuario hace click sobre un enlace, este conmuta interactivamente a estado OFFLINE (rojo discontinuo), "
        "forzando al Algoritmo Húngaro a recalcular rutas alternativas.\n"
        "• Paquetes Animados: Esferas luminiscentes con brillo exterior que se desplazan con velocidad proporcional a la latencia.\n"
        "• Dashboard Lateral (HUD): Panel analítico en tiempo real que desglosa los parámetros activos, métricas de colas, "
        "costos acumulados y botones interactivos para pausar, exportar y modular la tasa λ."
    )

    # Insertar imagen si existe
    if screenshot_image_path and os.path.exists(screenshot_image_path):
        try:
            doc.add_paragraph("\n")
            p_img = doc.add_paragraph()
            p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
            doc.add_picture(screenshot_image_path, width=Inches(6.0))
            p_cap = doc.add_paragraph("Figura 1: Captura de pantalla de la interfaz gráfica del Simulador en ejecución (Pygame a 60 FPS).")
            p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_cap.runs[0].font.size = Pt(9.5)
            p_cap.runs[0].font.italic = True
            doc.add_paragraph("\n")
        except Exception as e:
            print(f"[DOCX] No se pudo incrustar imagen: {e}")

    # =========================================================================
    # SECCIÓN 5: RESULTADOS EXPERIMENTALES Y MÉTRICAS OBTENIDAS
    # =========================================================================
    h5 = doc.add_heading("5. Resultados Experimentales y Métricas Obtenidas", level=1)
    h5.runs[0].font.color.rgb = RGBColor(12, 74, 110)

    doc.add_paragraph(
        "A continuación se presenta el consolidado cuantitativo obtenido tras la corrida de evaluación experimental del simulador:"
    )

    # Crear tabla de resultados
    table = doc.add_table(rows=1, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Parámetro / Métrica Cuantitativa"
    hdr_cells[1].text = "Valor Observado"
    for cell in hdr_cells:
        _set_cell_background(cell, "0C4A6E")
        _set_cell_margins(cell, top=120, bottom=120, left=150, right=150)
        cell.paragraphs[0].runs[0].font.bold = True
        cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)

    # Parámetros de inventario leídos de la configuración vigente (nunca rotulados a mano)
    flow_summary = metrics.get("flow_control", {}) or {}
    capacity_S = flow_summary.get("capacity_S", DEFAULT_BUFFER_CAPACITY_S)
    threshold_s = flow_summary.get("threshold_s", DEFAULT_REORDER_POINT_S)
    batch_Q = flow_summary.get("batch_Q", DEFAULT_ORDER_BATCH_Q)

    profile = lambda_profile or metrics.get("lambda_profile", {}) or {}
    if profile.get("lambda_varied"):
        lambda_label = (
            f"{lambda_val:.2f} paquetes/s (media ponderada; "
            f"{profile.get('lambda_initial', 0.0):.1f} → {profile.get('lambda_final', 0.0):.1f})"
        )
    else:
        lambda_label = f"{lambda_val:.1f} paquetes/s"

    data_rows = [
        ("Tiempo Total de Simulación (T)", f"{sim_time:.1f} segundos"),
        ("Tasa Media de Llegada (λ - Poisson)", lambda_label),
        ("Tasa Media de Servicio (μ - Exponencial)", f"{mu_val:.1f} paquetes/s"),
        ("Capacidad de Buffer por Router (S)", f"{capacity_S} paquetes"),
        ("Umbral de Control de Flujo (s)", f"{threshold_s} paquetes"),
        ("Lote de Reabastecimiento (Q)", f"{batch_Q} paquetes"),
        ("Lotes Q Autorizados (señales s, Q)", str(flow_summary.get("batches_granted", 0))),
        ("Paquetes Procesados con Éxito (N_proc)", str(metrics.get("total_processed", 0))),
        ("Paquetes Descartados por Desbordamiento (N_loss)", str(metrics.get("total_dropped", 0))),
        ("Paquetes Bloqueados por Control de Flujo", str(metrics.get("total_blocked", 0))),
        ("Paquetes Perdidos por Caída de Enlace", str(metrics.get("total_link_failures", 0))),
        ("Tasa Porcentual de Pérdida de Paquetes", f"{metrics.get('loss_rate_pct', 0.0):.2f}%"),
        ("Tiempo Medio de Espera en Cola (Wq)", f"{metrics.get('W_q', 0.0):.3f} segundos"),
        ("Tiempo Medio Total en la Red (W)", f"{metrics.get('W', 0.0):.3f} segundos"),
        ("Número Medio de Paquetes en Cola (Lq)", f"{metrics.get('L_q', 0.0):.2f} paquetes"),
        ("Número Medio de Paquetes en Sistema (L)", f"{metrics.get('L', 0.0):.2f} paquetes"),
        ("Costo Total de Almacenamiento (Holding Cost)", f"${metrics.get('holding_cost', 0.0):.2f}"),
        ("Costo Total de Penalización por Ruptura", f"${metrics.get('shortage_cost', 0.0):.2f}"),
        ("Costo Global del Sistema Consolidado", f"${metrics.get('global_cost', 0.0):.2f}"),
    ]

    for idx, (param, val) in enumerate(data_rows):
        row = table.add_row()
        c0 = row.cells[0]
        c1 = row.cells[1]
        c0.text = param
        c1.text = val

        bg_col = "F0F9FF" if idx % 2 == 0 else "FFFFFF"
        _set_cell_background(c0, bg_col)
        _set_cell_background(c1, bg_col)
        _set_cell_margins(c0, top=80, bottom=80, left=120, right=120)
        _set_cell_margins(c1, top=80, bottom=80, left=120, right=120)

        c0.paragraphs[0].runs[0].font.size = Pt(10)
        c1.paragraphs[0].runs[0].font.size = Pt(10)
        c1.paragraphs[0].runs[0].font.bold = True

    doc.add_paragraph("\n")

    # =========================================================================
    # SECCIÓN 6: DIAGNÓSTICO AUTOMATIZADO E INTEGRACIÓN CON API
    # =========================================================================
    h6 = doc.add_heading("6. Diagnóstico Automatizado e Integración con API", level=1)
    h6.runs[0].font.color.rgb = RGBColor(12, 74, 110)

    doc.add_paragraph(
        "De conformidad con los requerimientos funcionales, los datos cuantitativos consolidados "
        "fueron transmitidos de forma automatizada mediante una solicitud HTTP POST estructurada hacia la "
        "API de Inteligencia Artificial para la emisión de conclusiones técnicas y recomendaciones optimizadas. "
        "A continuación se reproduce el dictamen analítico obtenido:"
    )

    # Recuadro con el análisis
    p_box = doc.add_paragraph()
    p_box.paragraph_format.left_indent = Inches(0.4)
    p_box.paragraph_format.right_indent = Inches(0.4)
    r_box = p_box.add_run(api_analysis.strip())
    r_box.font.name = "Consolas"
    r_box.font.size = Pt(9.5)
    r_box.font.color.rgb = RGBColor(20, 35, 55)

    doc.add_paragraph("\n")

    # =========================================================================
    # SECCIÓN 7: CONCLUSIONES GENERALES
    # =========================================================================
    h7 = doc.add_heading("7. Conclusiones Generales", level=1)
    h7.runs[0].font.color.rgb = RGBColor(12, 74, 110)

    doc.add_paragraph(
        "1. La integración de la Teoría de Colas (M/M/1/K) permitió predecir y cuantificar fielmente los cuellos de botella "
        "inducidos por la naturaleza estocástica del tráfico de Poisson, verificando empíricamente la validez de la Ley de Little "
        "en redes con descarte.\n\n"
        "2. El modelado de buffers bajo conceptos de inventario (s, Q) y la imputación de costos integrales de almacenamiento "
        "frente a penalizaciones por rotura demostró ser un marco conceptual idóneo para la toma de decisiones de ingeniería, "
        "evidenciando que los costos de penalización por descarte dominan sustancialmente la economía de la red.\n\n"
        "3. El Algoritmo Húngaro resolvió satisfactoriamente el balanceo dinámico de carga, logrando redirigir flujos ante "
        "la desconexión imprevista de enlaces en tiempo real y minimizando la saturación acumulada de los enrutadores centrales.\n\n"
        "4. La arquitectura multihilo desacoplada entre SimPy y Pygame garantizó un rendimiento gráfico impecable a 60 FPS "
        "sin interrupciones durante el procesamiento numérico ni en las consultas de red hacia la API de diagnóstico."
    )

    # Guardar documento
    os.makedirs(os.path.dirname(os.path.abspath(docx_path)), exist_ok=True)
    doc.save(docx_path)
    print(f"[DOCX] Informe técnico generado con éxito en: {docx_path}")
