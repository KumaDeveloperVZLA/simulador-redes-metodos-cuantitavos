"""
Configuración global del Simulador Dinámico de Redes de Computadoras.
Define constantes de simulación, topología de red, parámetros matemáticos y paleta visual.
"""

from dataclasses import dataclass
from typing import Dict, Tuple, List

# ==========================================
# DIMENSIONES DE PANTALLA Y RENDERIZADO
# ==========================================
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 768
FPS = 60

# Ancho del panel lateral derecho (HUD)
SIDEBAR_WIDTH = 380
CANVAS_WIDTH = SCREEN_WIDTH - SIDEBAR_WIDTH

# ==========================================
# PARÁMETROS MATEMÁTICOS DE SIMULACIÓN
# ==========================================
DEFAULT_LAMBDA = 15.0      # Tasa de llegada de Poisson (paquetes/s)
DEFAULT_MU = 18.0          # Tasa de servicio exponencial por servidor (paquetes/s)
DEFAULT_BUFFER_CAPACITY_S = 50  # Capacidad máxima del buffer (S)
DEFAULT_REORDER_POINT_S = 10    # Umbral de reabastecimiento / control de flujo (s)
DEFAULT_ORDER_BATCH_Q = 15      # Tamaño de lote de reabastecimiento (Q)

# Costos del modelo de inventario
HOLDING_COST_RATE_H = 0.05      # Costo de almacenamiento por paquete por segundo ($/pkt·s)
SHORTAGE_PENALTY_COST = 10.0    # Penalización monetaria fija por paquete descartado ($/pkt)

# Algoritmo Húngaro (Asignación Óptima)
HUNGARIAN_INTERVAL = 0.5        # Intervalo Delta t para ejecución del algoritmo (segundos)
ALPHA_SATURATION_WEIGHT = 5.0   # Factor de ponderación alpha para saturación de buffer
DUMMY_PENALTY_COST = 10000.0    # Penalización para balancear matriz rectangular N != M

# ==========================================
# PALETA DE COLORES CYBERPUNK / DARK MODE
# ==========================================
COLOR_BG = (11, 15, 25)                # Fondo principal azul muy oscuro
COLOR_CANVAS_GRID = (20, 28, 45)       # Líneas de cuadrícula sutiles
COLOR_PANEL_BG = (16, 22, 36)          # Fondo de paneles laterales
COLOR_PANEL_BORDER = (32, 44, 68)      # Borde de paneles
COLOR_PANEL_HEADER = (23, 33, 54)      # Fondo de cabeceras en paneles

# Textos
COLOR_TEXT_PRIMARY = (235, 243, 255)   # Blanco brillante / azul hielo
COLOR_TEXT_SECONDARY = (138, 155, 184) # Gris azulado tenue
COLOR_TEXT_MUTED = (85, 102, 128)      # Gris oscuro
COLOR_ACCENT_CYAN = (0, 240, 255)      # Neón cian
COLOR_ACCENT_PURPLE = (168, 85, 247)   # Neón púrpura

# Estados de Nodos (Saturación de Buffer)
COLOR_NODE_NORMAL = (0, 230, 130)      # Verde Neón (< 50%)
COLOR_NODE_WARNING = (255, 195, 0)     # Amarillo / Ámbar (50% - 80%)
COLOR_NODE_DANGER = (255, 45, 85)      # Rojo Neón (> 80%)

# Enlaces
COLOR_LINK_ACTIVE = (0, 185, 235)      # Enlace activo brillante
COLOR_LINK_CONGESTED = (255, 140, 0)   # Enlace con latencia / tráfico alto
COLOR_LINK_DOWN = (255, 50, 75)        # Enlace caído (falla simulada)
COLOR_LINK_GLOW = (0, 240, 255, 40)    # Halo de enlace activo

# Paquetes de datos
COLOR_PACKET = (255, 240, 90)          # Amarillo orbe brillante
COLOR_PACKET_GLOW = (255, 200, 50)     # Brillo exterior del paquete
COLOR_PACKET_DROPPED = (255, 40, 70)   # Destello de paquete descartado

# Botones
COLOR_BTN_BG = (28, 38, 60)
COLOR_BTN_HOVER = (42, 58, 90)
COLOR_BTN_BORDER = (0, 200, 240)
COLOR_BTN_TEXT = (240, 245, 255)

# ==========================================
# DEFINICIÓN DE TOPOLOGÍA DE RED
# ==========================================
# Coordenadas y roles de los routers en el lienzo (Canvas)
TOPOLOGY_NODES = [
    {
        "id": "R_IN_1",
        "name": "Ingress Alpha",
        "pos": (120, 220),
        "is_ingress": True,
        "is_egress": False,
        "capacity": DEFAULT_BUFFER_CAPACITY_S,
        "threshold": DEFAULT_REORDER_POINT_S,
        "batch": DEFAULT_ORDER_BATCH_Q
    },
    {
        "id": "R_IN_2",
        "name": "Ingress Beta",
        "pos": (120, 500),
        "is_ingress": True,
        "is_egress": False,
        "capacity": DEFAULT_BUFFER_CAPACITY_S,
        "threshold": DEFAULT_REORDER_POINT_S,
        "batch": DEFAULT_ORDER_BATCH_Q
    },
    {
        "id": "R_CORE_1",
        "name": "Core Norte",
        "pos": (440, 160),
        "is_ingress": False,
        "is_egress": False,
        "capacity": DEFAULT_BUFFER_CAPACITY_S,
        "threshold": DEFAULT_REORDER_POINT_S,
        "batch": DEFAULT_ORDER_BATCH_Q
    },
    {
        "id": "R_CORE_2",
        "name": "Core Centro",
        "pos": (440, 360),
        "is_ingress": False,
        "is_egress": False,
        "capacity": DEFAULT_BUFFER_CAPACITY_S,
        "threshold": DEFAULT_REORDER_POINT_S,
        "batch": DEFAULT_ORDER_BATCH_Q
    },
    {
        "id": "R_CORE_3",
        "name": "Core Sur",
        "pos": (440, 560),
        "is_ingress": False,
        "is_egress": False,
        "capacity": DEFAULT_BUFFER_CAPACITY_S,
        "threshold": DEFAULT_REORDER_POINT_S,
        "batch": DEFAULT_ORDER_BATCH_Q
    },
    {
        "id": "R_OUT_1",
        "name": "Egress Gateway 1",
        "pos": (760, 260),
        "is_ingress": False,
        "is_egress": True,
        "capacity": DEFAULT_BUFFER_CAPACITY_S,
        "threshold": DEFAULT_REORDER_POINT_S,
        "batch": DEFAULT_ORDER_BATCH_Q
    },
    {
        "id": "R_OUT_2",
        "name": "Egress Gateway 2",
        "pos": (760, 480),
        "is_ingress": False,
        "is_egress": True,
        "capacity": DEFAULT_BUFFER_CAPACITY_S,
        "threshold": DEFAULT_REORDER_POINT_S,
        "batch": DEFAULT_ORDER_BATCH_Q
    },
]

# Enlaces interconectados con latencias base
TOPOLOGY_LINKS = [
    {"id": "L1", "source": "R_IN_1", "target": "R_CORE_1", "base_latency": 0.08},
    {"id": "L2", "source": "R_IN_1", "target": "R_CORE_2", "base_latency": 0.05},
    {"id": "L3", "source": "R_IN_2", "target": "R_CORE_2", "base_latency": 0.05},
    {"id": "L4", "source": "R_IN_2", "target": "R_CORE_3", "base_latency": 0.09},
    {"id": "L5", "source": "R_CORE_1", "target": "R_OUT_1", "base_latency": 0.06},
    {"id": "L6", "source": "R_CORE_2", "target": "R_OUT_1", "base_latency": 0.07},
    {"id": "L7", "source": "R_CORE_2", "target": "R_OUT_2", "base_latency": 0.07},
    {"id": "L8", "source": "R_CORE_3", "target": "R_OUT_2", "base_latency": 0.06},
    # Enlace entre núcleos para tolerancia a fallos
    {"id": "L9", "source": "R_CORE_1", "target": "R_CORE_2", "base_latency": 0.03},
    {"id": "L10", "source": "R_CORE_2", "target": "R_CORE_3", "base_latency": 0.03},
]
