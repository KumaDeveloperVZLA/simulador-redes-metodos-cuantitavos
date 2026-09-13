"""
Generador del Reporte Estructurado de Simulación de Red (reporte_simulacion.txt).
Respeta estrictamente el formato exigido en INSTRUCCIONES.md y ejercicio.md.
"""

import os
from typing import Dict, Any, Optional, List


def _build_supplementary_block(
    metrics: Dict[str, Any],
    capacity_S: int,
    threshold_s: int,
    batch_Q: Optional[int],
    lambda_profile: Optional[Dict[str, Any]]
) -> List[str]:
    """
    Bloque complementario (fuera de la plantilla exigida) con la trazabilidad de la
    corrida: recorrido de lambda, política (s, Q) y métricas de cola adicionales.
    """
    lines: List[str] = [
        "-" * 50,
        "DETALLE COMPLEMENTARIO DE LA CORRIDA:",
    ]

    if lambda_profile and lambda_profile.get("lambda_varied"):
        lines.append(
            "Lambda fue ajustada en caliente durante la sesión: "
            f"inicial {lambda_profile.get('lambda_initial', 0.0):.1f} -> "
            f"final {lambda_profile.get('lambda_final', 0.0):.1f} paquetes/s "
            f"(rango [{lambda_profile.get('lambda_min', 0.0):.1f}, "
            f"{lambda_profile.get('lambda_max', 0.0):.1f}])."
        )
        lines.append(
            "El valor reportado arriba es la media ponderada en el tiempo, que es la "
            "tasa de llegada que efectivamente rigió la simulación."
        )
    elif lambda_profile:
        lines.append("Lambda se mantuvo constante durante toda la corrida.")

    if lambda_profile and lambda_profile.get("mu_varied"):
        lines.append(
            "Mu fue ajustada durante la sesión: "
            f"inicial {lambda_profile.get('mu_initial', 0.0):.1f} -> "
            f"final {lambda_profile.get('mu_final', 0.0):.1f} paquetes/s."
        )

    if batch_Q is not None:
        lines.append(f"Lote de Reabastecimiento (Q): {batch_Q} paquetes")

    flow = metrics.get("flow_control", {}) or {}
    if flow:
        lines.append(
            f"Señales de Control de Flujo (s, Q) emitidas: {flow.get('flow_control_signals', 0)}"
        )
    lines.append(
        f"Paquetes Bloqueados por Control de Flujo: {metrics.get('total_blocked', 0)}"
    )
    lines.append(
        f"Paquetes Generados (tráfico ofrecido): {metrics.get('total_generated', 0)}"
    )
    lines.append(
        f"Promedio Paquetes en Cola (Lq): {metrics.get('L_q', 0.0):.2f}"
    )
    lines.append(
        f"Tiempo Medio Total en Red (W): {metrics.get('W', 0.0):.3f} s"
    )
    lines.append(
        f"Paquetes Perdidos en Tránsito por Caída de Enlace: {metrics.get('total_link_failures', 0)}"
    )
    lines.append(
        "Entregas en egress alterno (balanceo bajo falla): "
        f"{metrics.get('total_misrouted', 0)}"
    )

    # Lectura cuantitativa de la política de inventario: la ocupación de un nodo no
    # puede superar s + Q, porque un lote nuevo solo se autoriza al bajar hasta s.
    if batch_Q is not None:
        max_occupancy = threshold_s + batch_Q
        if max_occupancy < capacity_S:
            lines.append(
                f"Nota: con S = {capacity_S}, s = {threshold_s} y Q = {batch_Q}, la ocupación máxima "
                f"alcanzable de un buffer es s + Q = {max_occupancy} < S, de modo que el control de "
                "flujo evita por construcción el desbordamiento: la pérdida se materializa como "
                "rechazo controlado en la admisión y no como Buffer Overflow."
            )
    lines.append(
        "Los paquetes bloqueados se contabilizan como tráfico perdido (el modelo no "
        "reintenta el envío) y penalizan el costo de ruptura igual que un desbordamiento."
    )

    errors = metrics.get("engine_errors", 0)
    if errors:
        lines.append(
            f"ADVERTENCIA: el motor registró {errors} fallo(s) durante la corrida "
            f"({metrics.get('last_engine_error', 'sin detalle')})."
        )

    lines.append("=" * 50)
    return lines


def format_simulation_report(
    sim_time: float,
    lambda_val: float,
    mu_val: float,
    capacity_S: int,
    threshold_s: int,
    metrics: Dict[str, Any],
    batch_Q: Optional[int] = None,
    lambda_profile: Optional[Dict[str, Any]] = None
) -> str:
    """
    Construye la cadena de texto con el formato exacto requerido:
    ==================================================
               REPORTE DE SIMULACIÓN DE RED           
    ==================================================
    Tiempo Total de Simulación: [T] s
    Tasa de Llegada (lambda): [λ] paquetes/s
    Tasa de Servicio (mu): [μ] paquetes/s
    Capacidad de Buffer (S): [S] paquetes
    Umbral Reabastecimiento (s): [s] paquetes
    --------------------------------------------------
    METRICAS OBTENIDAS:
    Paquetes Procesados: [N_proc]
    Paquetes Perdidos (Overflow): [N_loss]
    Tasa de Pérdida: [X.XX]%
    Tiempo Medio en Cola (Wq): [X.XX] s
    Promedio Paquetes en Sistema (L): [X.XX]
    Costo Total de Almacenamiento: $[X.XX]
    Costo Total de Penalización (Ruptura): $[X.XX]
    --------------------------------------------------
    Costo Global del Sistema: $[X.XX]
    ==================================================

    `lambda_val` debe ser la tasa de llegada que rigió la corrida (media ponderada
    en el tiempo cuando el usuario la ajustó desde la GUI), nunca el último valor
    tecleado: de lo contrario el reporte queda internamente contradictorio.
    """
    n_proc = metrics.get("total_processed", 0)
    n_loss = metrics.get("total_dropped", 0)
    loss_pct = metrics.get("loss_rate_pct", 0.0)
    wq = metrics.get("W_q", 0.0)
    l_val = metrics.get("L", 0.0)
    c_hold = metrics.get("holding_cost", 0.0)
    c_short = metrics.get("shortage_cost", 0.0)
    c_global = metrics.get("global_cost", 0.0)

    report_lines = [
        "=" * 50,
        "           REPORTE DE SIMULACIÓN DE RED           ",
        "=" * 50,
        f"Tiempo Total de Simulación: {sim_time:.1f} s",
        f"Tasa de Llegada (lambda): {lambda_val:.1f} paquetes/s",
        f"Tasa de Servicio (mu): {mu_val:.1f} paquetes/s",
        f"Capacidad de Buffer (S): {capacity_S} paquetes",
        f"Umbral Reabastecimiento (s): {threshold_s} paquetes",
        "-" * 50,
        "METRICAS OBTENIDAS:",
        f"Paquetes Procesados: {n_proc}",
        f"Paquetes Perdidos (Overflow): {n_loss}",
        f"Tasa de Pérdida: {loss_pct:.2f}%",
        f"Tiempo Medio en Cola (Wq): {wq:.2f} s",
        f"Promedio Paquetes en Sistema (L): {l_val:.2f}",
        f"Costo Total de Almacenamiento: ${c_hold:.2f}",
        f"Costo Total de Penalización (Ruptura): ${c_short:.2f}",
        "-" * 50,
        f"Costo Global del Sistema: ${c_global:.2f}",
        "=" * 50,
    ]

    report_lines.extend(
        _build_supplementary_block(metrics, capacity_S, threshold_s, batch_Q, lambda_profile)
    )

    return "\n".join(report_lines) + "\n"


def export_simulation_report(
    filepath: str,
    sim_time: float,
    lambda_val: float,
    mu_val: float,
    capacity_S: int,
    threshold_s: int,
    metrics: Dict[str, Any],
    batch_Q: Optional[int] = None,
    lambda_profile: Optional[Dict[str, Any]] = None
) -> str:
    """
    Escribe el reporte en disco en la ruta especificada y retorna el texto generado.
    """
    content = format_simulation_report(
        sim_time=sim_time,
        lambda_val=lambda_val,
        mu_val=mu_val,
        capacity_S=capacity_S,
        threshold_s=threshold_s,
        metrics=metrics,
        batch_Q=batch_Q,
        lambda_profile=lambda_profile
    )

    # Asegurar directorio
    dirname = os.path.dirname(filepath)
    if dirname:
        os.makedirs(dirname, exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return content
