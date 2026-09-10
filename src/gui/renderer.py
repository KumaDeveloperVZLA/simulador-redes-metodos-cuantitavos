"""
Renderizador Gráfico de la Red para Pygame (Estética Cyberpunk / Dark Mode).
Dibuja el lienzo de topología, cuadrícula tecnológica, enlaces dinámicos con latencias,
nodos con anillos indicadores de saturación cromática y paquetes animados vía LERP.
"""

import math
from typing import Dict, List, Tuple, Any, Optional
import pygame

from ..config import (
    COLOR_BG,
    COLOR_CANVAS_GRID,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    COLOR_ACCENT_CYAN,
    COLOR_ACCENT_PURPLE,
    COLOR_LINK_ACTIVE,
    COLOR_LINK_DOWN,
    COLOR_LINK_CONGESTED,
    COLOR_PACKET,
    COLOR_PACKET_GLOW,
    COLOR_NODE_NORMAL,
    COLOR_NODE_WARNING,
    COLOR_NODE_DANGER
)
from ..models.link import NetworkLink


class NetworkRenderer:
    """
    Gestiona el dibujo en alta resolución de todos los elementos visuales de la red.
    """

    def __init__(self, surface: pygame.Surface, font_bold: pygame.font.Font, font_regular: pygame.font.Font, font_small: pygame.font.Font):
        self.surface: pygame.Surface = surface
        self.font_bold: pygame.font.Font = font_bold
        self.font_regular: pygame.font.Font = font_regular
        self.font_small: pygame.font.Font = font_small

        # Dimensiones del lienzo de topología
        self.width = surface.get_width()
        self.height = surface.get_height()

        # Nodos: radio visual
        self.node_radius = 34
        self.node_inner_radius = 26

    def draw_canvas_grid(self, width: int, height: int) -> None:
        """Dibuja un fondo tecnológico con cuadrícula sutil."""
        self.surface.fill(COLOR_BG)

        # Líneas verticales y horizontales espaciadas
        step = 50
        for x in range(0, width, step):
            pygame.draw.line(self.surface, COLOR_CANVAS_GRID, (x, 0), (x, height), 1)
        for y in range(0, height, step):
            pygame.draw.line(self.surface, COLOR_CANVAS_GRID, (0, y), (width, y), 1)

        # Destellos en intersecciones mayores
        for x in range(0, width, step * 2):
            for y in range(0, height, step * 2):
                pygame.draw.circle(self.surface, (30, 42, 65), (x, y), 2)

    def draw_links(self, links_state: List[Dict[str, Any]]) -> None:
        """
        Dibuja los enlaces dinámicos con grosores, colores por estado
        y etiquetas flotantes de latencia.
        """
        for lnk in links_state:
            p1 = lnk["src_pos"]
            p2 = lnk["tgt_pos"]
            is_active = lnk["is_active"]
            latency = lnk["current_latency"]
            in_transit = lnk["in_transit_count"]

            if is_active:
                color = COLOR_LINK_CONGESTED if in_transit > 4 else COLOR_LINK_ACTIVE
                width = 3 if in_transit > 2 else 2

                # Halo exterior sutil
                pygame.draw.line(self.surface, (0, 80, 110), p1, p2, width + 4)
                # Línea central brillante
                pygame.draw.line(self.surface, color, p1, p2, width)

                # Etiqueta de latencia en el centro del enlace
                mid_x = (p1[0] + p2[0]) / 2.0
                mid_y = (p1[1] + p2[1]) / 2.0
                label_text = f"{latency * 1000:.0f}ms"
                tag_surf = self.font_small.render(label_text, True, COLOR_TEXT_SECONDARY)
                tag_rect = tag_surf.get_rect(center=(mid_x, mid_y - 10))

                # Fondo de la etiqueta
                bg_rect = tag_rect.inflate(6, 4)
                pygame.draw.rect(self.surface, (14, 20, 32), bg_rect, border_radius=4)
                pygame.draw.rect(self.surface, (35, 48, 70), bg_rect, 1, border_radius=4)
                self.surface.blit(tag_surf, tag_rect)

            else:
                # Enlace caído (falla interactiva): línea roja discontinua/alerta
                pygame.draw.line(self.surface, COLOR_LINK_DOWN, p1, p2, 2)

                mid_x = (p1[0] + p2[0]) / 2.0
                mid_y = (p1[1] + p2[1]) / 2.0
                tag_surf = self.font_small.render("OFFLINE", True, (255, 255, 255))
                tag_rect = tag_surf.get_rect(center=(mid_x, mid_y))

                bg_rect = tag_rect.inflate(8, 6)
                pygame.draw.rect(self.surface, (180, 20, 40), bg_rect, border_radius=4)
                self.surface.blit(tag_surf, tag_rect)

    def draw_nodes(self, nodes_state: List[Dict[str, Any]]) -> None:
        """
        Dibuja los routers con:
        - Anillo exterior indicador de saturación cromática (<50% verde, 50-80% amarillo, >80% rojo).
        - Arco de progreso según nivel del buffer.
        - Identificador y conteo de ocupación / capacidad (ej. 12/50).
        - Etiqueta de control de flujo si está activa.
        """
        for node in nodes_state:
            x, y = node["pos"]
            occ = node["occupancy"]
            cap = node["capacity"]
            sat = node["saturation"]
            color_state = node["color"]
            name = node["name"]
            node_id = node["id"]
            flow_ctrl = node["flow_control"]

            # 1. Halo exterior brillante según el color de saturación
            halo_color = (color_state[0] // 4, color_state[1] // 4, color_state[2] // 4)
            pygame.draw.circle(self.surface, halo_color, (x, y), self.node_radius + 4)

            # 2. Círculo exterior base (anillo oscuro)
            pygame.draw.circle(self.surface, (25, 35, 55), (x, y), self.node_radius, 4)

            # 3. Arco indicador de capacidad ocupada (Buffer Fill Ring)
            if occ > 0:
                angle_span = 2 * math.pi * sat
                rect_box = pygame.Rect(
                    x - self.node_radius,
                    y - self.node_radius,
                    self.node_radius * 2,
                    self.node_radius * 2
                )
                start_ang = -math.pi / 2
                end_ang = start_ang + angle_span
                # pygame.draw.arc espera ángulos en radianes
                pygame.draw.arc(self.surface, color_state, rect_box, start_ang, end_ang, 4)

            # 4. Núcleo interior del nodo
            pygame.draw.circle(self.surface, (16, 22, 36), (x, y), self.node_inner_radius)
            pygame.draw.circle(self.surface, (45, 60, 90), (x, y), self.node_inner_radius, 1)

            # 5. Texto identificador central (ej. R1, Core)
            short_id = node_id.replace("R_", "").replace("IN_", "IN").replace("CORE_", "C").replace("OUT_", "OUT")
            id_surf = self.font_bold.render(short_id, True, COLOR_TEXT_PRIMARY)
            id_rect = id_surf.get_rect(center=(x, y - 4))
            self.surface.blit(id_surf, id_rect)

            # 6. Conteo de buffer (ej. 14/50)
            buf_text = f"{occ}/{cap}"
            buf_surf = self.font_small.render(buf_text, True, color_state)
            buf_rect = buf_surf.get_rect(center=(x, y + 11))
            self.surface.blit(buf_surf, buf_rect)

            # 7. Etiqueta inferior con el nombre descriptivo
            name_surf = self.font_small.render(name, True, COLOR_TEXT_SECONDARY)
            name_rect = name_surf.get_rect(center=(x, y + self.node_radius + 14))
            self.surface.blit(name_surf, name_rect)

            # 8. Indicador de señal de Control de Flujo (s, Q)
            if flow_ctrl:
                ctrl_surf = self.font_small.render("[REQ Q]", True, COLOR_ACCENT_CYAN)
                ctrl_rect = ctrl_surf.get_rect(center=(x, y - self.node_radius - 12))
                bg_c = ctrl_rect.inflate(6, 2)
                pygame.draw.rect(self.surface, (0, 40, 60), bg_c, border_radius=3)
                self.surface.blit(ctrl_surf, ctrl_rect)

    def draw_packets(self, packets_state: List[Dict[str, Any]]) -> None:
        """
        Dibuja los paquetes de datos animados en tránsito a lo largo de los enlaces.
        """
        for pkt in packets_state:
            x, y = pkt["pos"]
            ix = int(x)
            iy = int(y)

            # Destello exterior
            pygame.draw.circle(self.surface, (255, 200, 50), (ix, iy), 6)
            # Núcleo brillante
            pygame.draw.circle(self.surface, COLOR_PACKET, (ix, iy), 3)

    def find_clicked_link(
        self,
        mouse_pos: Tuple[int, int],
        links_state: List[Dict[str, Any]],
        hit_threshold: float = 12.0
    ) -> Optional[str]:
        """
        Detecta si el click del mouse ocurrió sobre algún enlace de la topología.
        Retorna el link_id del enlace más cercano dentro del umbral de tolerancia.
        """
        mx, my = mouse_pos
        closest_link_id = None
        min_dist = float("inf")

        for lnk in links_state:
            x1, y1 = lnk["src_pos"]
            x2, y2 = lnk["tgt_pos"]
            dist = NetworkLink.distance_point_to_segment(mx, my, x1, y1, x2, y2)
            if dist < hit_threshold and dist < min_dist:
                min_dist = dist
                closest_link_id = lnk["id"]

        return closest_link_id
