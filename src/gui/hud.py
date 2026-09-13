"""
Dashboard / HUD Lateral para Pygame.
Muestra cronómetro, parámetros activos (lambda, mu, S, s, Q), métricas en vivo (L, Lq, W, Wq),
desglose de costos (Almacenamiento, Ruptura, Costo Global) y botones interactivos.
"""

from typing import Dict, Any, Tuple, Optional
import pygame

from ..config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    SIDEBAR_WIDTH,
    CANVAS_WIDTH,
    DEFAULT_BUFFER_CAPACITY_S,
    DEFAULT_REORDER_POINT_S,
    DEFAULT_ORDER_BATCH_Q,
    COLOR_PANEL_BG,
    COLOR_PANEL_BORDER,
    COLOR_PANEL_HEADER,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    COLOR_ACCENT_CYAN,
    COLOR_ACCENT_PURPLE,
    COLOR_NODE_NORMAL,
    COLOR_NODE_WARNING,
    COLOR_NODE_DANGER,
    COLOR_BTN_BG,
    COLOR_BTN_HOVER,
    COLOR_BTN_BORDER,
    COLOR_BTN_TEXT
)


# Valores de respaldo solo para el primer frame, antes del primer snapshot del motor
DEFAULT_LAMBDA_FALLBACK = 15.0
DEFAULT_MU_FALLBACK = 18.0


class SimulationHUD:
    """
    Panel lateral que despliega la instrumentación analítica y controles interactivos.
    """

    def __init__(
        self,
        surface: pygame.Surface,
        font_title: pygame.font.Font,
        font_bold: pygame.font.Font,
        font_regular: pygame.font.Font,
        font_small: pygame.font.Font
    ):
        self.surface: pygame.Surface = surface
        self.font_title: pygame.font.Font = font_title
        self.font_bold: pygame.font.Font = font_bold
        self.font_regular: pygame.font.Font = font_regular
        self.font_small: pygame.font.Font = font_small

        self.sidebar_x = CANVAS_WIDTH
        self.sidebar_width = SIDEBAR_WIDTH
        self.sidebar_height = SCREEN_HEIGHT

        # Botones interactivos (Rectángulos)
        self.buttons: Dict[str, pygame.Rect] = {}

    def draw(self, snapshot: Dict[str, Any], mouse_pos: Tuple[int, int]) -> None:
        """Dibuja el panel lateral completo a partir del último snapshot."""
        # Fondo del sidebar
        sidebar_rect = pygame.Rect(self.sidebar_x, 0, self.sidebar_width, self.sidebar_height)
        pygame.draw.rect(self.surface, COLOR_PANEL_BG, sidebar_rect)
        pygame.draw.line(self.surface, COLOR_PANEL_BORDER, (self.sidebar_x, 0), (self.sidebar_x, self.sidebar_height), 2)

        metrics = snapshot.get("metrics", {})
        sim_time = snapshot.get("sim_time", 0.0)
        is_paused = snapshot.get("is_paused", False)
        current_lambda = snapshot.get("lambda", DEFAULT_LAMBDA_FALLBACK)
        current_mu = snapshot.get("mu", DEFAULT_MU_FALLBACK)

        # Parámetros reales de la corrida: nunca se rotulan a mano, se leen del
        # snapshot (y en su defecto de config) para que el panel no mienta si cambian.
        params = snapshot.get("params", {})
        capacity_S = params.get("capacity_S", DEFAULT_BUFFER_CAPACITY_S)
        threshold_s = params.get("threshold_s", DEFAULT_REORDER_POINT_S)
        batch_Q = params.get("batch_Q", DEFAULT_ORDER_BATCH_Q)
        flow_ctrl = snapshot.get("flow_control", {})
        lambda_profile = snapshot.get("lambda_profile", {})

        cur_y = 16

        # ----------------------------------------------------
        # 1. Cabecera Institucional y Título
        # ----------------------------------------------------
        title_surf = self.font_bold.render("SIMULADOR DE REDES", True, COLOR_ACCENT_CYAN)
        self.surface.blit(title_surf, (self.sidebar_x + 18, cur_y))
        cur_y += 24

        sub_surf = self.font_small.render("UJAP - MÉTODOS CUANTITATIVOS", True, COLOR_TEXT_MUTED)
        self.surface.blit(sub_surf, (self.sidebar_x + 18, cur_y))
        cur_y += 26

        # Estado operativo (Badge RUNNING / PAUSED)
        badge_text = "PAUSADO" if is_paused else "EN EJECUCIÓN"
        badge_color = COLOR_NODE_WARNING if is_paused else COLOR_NODE_NORMAL
        badge_surf = self.font_bold.render(f"● {badge_text}", True, badge_color)
        badge_rect = badge_surf.get_rect(topleft=(self.sidebar_x + 18, cur_y))
        bg_badge = badge_rect.inflate(14, 6)
        pygame.draw.rect(self.surface, (20, 28, 44), bg_badge, border_radius=4)
        pygame.draw.rect(self.surface, badge_color, bg_badge, 1, border_radius=4)
        self.surface.blit(badge_surf, badge_rect)

        # Cronómetro
        mins = int(sim_time) // 60
        secs = int(sim_time) % 60
        time_str = f"T: {sim_time:05.1f}s ({mins:02d}:{secs:02d})"
        time_surf = self.font_bold.render(time_str, True, COLOR_TEXT_PRIMARY)
        self.surface.blit(time_surf, (self.sidebar_x + 195, cur_y + 2))
        cur_y += 38

        # ----------------------------------------------------
        # 2. Card: Parámetros del Sistema (lambda, mu, S, s, Q)
        # ----------------------------------------------------
        cur_y = self._draw_card_header(cur_y, "PARÁMETROS ACTIVOS")

        # Fila Lambda con botones +/-
        lam_label = self.font_regular.render(f"Tasa Llegada (λ): {current_lambda:.1f} pkt/s", True, COLOR_TEXT_PRIMARY)
        self.surface.blit(lam_label, (self.sidebar_x + 22, cur_y + 2))

        # Botón [-]
        btn_minus = pygame.Rect(self.sidebar_x + 295, cur_y, 28, 22)
        self.buttons["lambda_minus"] = btn_minus
        self._draw_mini_btn(btn_minus, "-", mouse_pos)

        # Botón [+]
        btn_plus = pygame.Rect(self.sidebar_x + 330, cur_y, 28, 22)
        self.buttons["lambda_plus"] = btn_plus
        self._draw_mini_btn(btn_plus, "+", mouse_pos)
        cur_y += 26

        lam_mean = lambda_profile.get("lambda_mean", current_lambda)
        if lambda_profile.get("lambda_varied"):
            self._draw_key_value("λ medio ponderado:", f"{lam_mean:.2f} pkt/s", cur_y)
            cur_y += 20

        self._draw_key_value("Tasa Servicio (μ):", f"{current_mu:.1f} pkt/s", cur_y)
        cur_y += 20
        self._draw_key_value("Capacidad Buffer (S):", f"{capacity_S} paquetes", cur_y)
        cur_y += 20
        self._draw_key_value("Umbral Reabast. (s):", f"{threshold_s} paquetes", cur_y)
        cur_y += 20
        self._draw_key_value("Lote de Control (Q):", f"{batch_Q} paquetes", cur_y)
        cur_y += 20
        self._draw_key_value(
            "Lotes Q autorizados:",
            f"{flow_ctrl.get('batches_granted', 0)}",
            cur_y
        )
        cur_y += 28

        # ----------------------------------------------------
        # 3. Card: Métricas de Teoría de Colas (L, Lq, W, Wq)
        # ----------------------------------------------------
        cur_y = self._draw_card_header(cur_y, "TEORÍA DE COLAS (LÍNEAS DE ESPERA)")

        l_val = metrics.get("L", 0.0)
        lq_val = metrics.get("L_q", 0.0)
        w_val = metrics.get("W", 0.0)
        wq_val = metrics.get("W_q", 0.0)
        n_proc = metrics.get("total_processed", 0)
        n_loss = metrics.get("total_dropped", 0)
        loss_pct = metrics.get("loss_rate_pct", 0.0)

        self._draw_metric_row("Promedio en Sistema (L):", f"{l_val:.2f}", COLOR_TEXT_PRIMARY, cur_y)
        cur_y += 20
        self._draw_metric_row("Promedio en Cola (Lq):", f"{lq_val:.2f}", COLOR_TEXT_PRIMARY, cur_y)
        cur_y += 20
        self._draw_metric_row("Tiempo Medio Total (W):", f"{w_val:.3f} s", COLOR_ACCENT_CYAN, cur_y)
        cur_y += 20
        self._draw_metric_row("Tiempo Medio en Cola (Wq):", f"{wq_val:.3f} s", COLOR_ACCENT_CYAN, cur_y)
        cur_y += 20
        self._draw_metric_row("Paquetes Procesados:", f"{n_proc}", COLOR_TEXT_PRIMARY, cur_y)
        cur_y += 20

        loss_color = COLOR_NODE_DANGER if loss_pct > 5.0 else COLOR_TEXT_PRIMARY
        self._draw_metric_row(
            "Perdidos (Overflow):",
            f"{n_loss} ({loss_pct:.2f}% total)",
            loss_color,
            cur_y
        )
        cur_y += 20

        n_blocked = metrics.get("total_blocked", 0)
        self._draw_metric_row(
            "Bloqueados (Control s,Q):",
            f"{n_blocked}",
            COLOR_NODE_WARNING if n_blocked else COLOR_TEXT_PRIMARY,
            cur_y
        )
        cur_y += 28

        # ----------------------------------------------------
        # 4. Card: Modelo de Costos de Inventario
        # ----------------------------------------------------
        cur_y = self._draw_card_header(cur_y, "MODELO DE COSTOS (INVENTARIO)")

        c_hold = metrics.get("holding_cost", 0.0)
        c_short = metrics.get("shortage_cost", 0.0)
        c_global = metrics.get("global_cost", 0.0)

        self._draw_metric_row("Costo Almacenamiento (H):", f"${c_hold:.2f}", COLOR_TEXT_PRIMARY, cur_y)
        cur_y += 20
        self._draw_metric_row("Costo Penalización (Ruptura):", f"${c_short:.2f}", COLOR_NODE_WARNING, cur_y)
        cur_y += 24

        # Caja destacada de Costo Global
        global_box = pygame.Rect(self.sidebar_x + 18, cur_y, self.sidebar_width - 36, 42)
        pygame.draw.rect(self.surface, (20, 32, 50), global_box, border_radius=6)
        pygame.draw.rect(self.surface, COLOR_ACCENT_CYAN, global_box, 1, border_radius=6)

        g_lbl = self.font_regular.render("COSTO GLOBAL DEL SISTEMA", True, COLOR_TEXT_SECONDARY)
        self.surface.blit(g_lbl, (global_box.x + 12, global_box.y + 6))

        g_val = self.font_bold.render(f"${c_global:.2f}", True, COLOR_ACCENT_CYAN)
        g_val_rect = g_val.get_rect(topright=(global_box.right - 12, global_box.y + 8))
        self.surface.blit(g_val, g_val_rect)
        cur_y += 56

        # ----------------------------------------------------
        # 5. Botones de Control de la Simulación
        # ----------------------------------------------------
        btn_width = (self.sidebar_width - 46) // 2

        # Botón Pausar / Reanudar
        pause_rect = pygame.Rect(self.sidebar_x + 18, cur_y, btn_width, 36)
        self.buttons["toggle_pause"] = pause_rect
        p_label = "REANUDAR" if is_paused else "PAUSAR"
        self._draw_action_btn(pause_rect, p_label, mouse_pos, COLOR_ACCENT_CYAN)

        # Botón Detener y Reportar
        stop_rect = pygame.Rect(self.sidebar_x + 28 + btn_width, cur_y, btn_width, 36)
        self.buttons["stop_export"] = stop_rect
        self._draw_action_btn(stop_rect, "EXPORTAR [E]", mouse_pos, COLOR_NODE_DANGER)
        cur_y += 46

        # Indicaciones de atajos de teclado
        hints = [
            "Atajos: [ESPACIO] Pausa | [+/-] Ajustar λ",
            "Click en enlace: Alternar Fallo / Operativo",
            "[E / ESC]: Detener, Reporte TXT y Análisis API"
        ]
        for hint in hints:
            h_surf = self.font_small.render(hint, True, COLOR_TEXT_MUTED)
            self.surface.blit(h_surf, (self.sidebar_x + 18, cur_y))
            cur_y += 16

    def _draw_card_header(self, y: int, title: str) -> int:
        """Dibuja un encabezado estilizado de sección."""
        hdr_rect = pygame.Rect(self.sidebar_x + 18, y, self.sidebar_width - 36, 22)
        pygame.draw.rect(self.surface, COLOR_PANEL_HEADER, hdr_rect, border_radius=4)
        lbl = self.font_small.render(title, True, COLOR_ACCENT_CYAN)
        self.surface.blit(lbl, (hdr_rect.x + 8, hdr_rect.y + 4))
        return y + 28

    def _draw_key_value(self, key: str, val: str, y: int) -> None:
        k_surf = self.font_regular.render(key, True, COLOR_TEXT_SECONDARY)
        v_surf = self.font_regular.render(val, True, COLOR_TEXT_PRIMARY)
        self.surface.blit(k_surf, (self.sidebar_x + 22, y))
        v_rect = v_surf.get_rect(topright=(self.sidebar_x + self.sidebar_width - 24, y))
        self.surface.blit(v_surf, v_rect)

    def _draw_metric_row(self, label: str, value: str, val_color: Tuple[int, int, int], y: int) -> None:
        l_surf = self.font_regular.render(label, True, COLOR_TEXT_SECONDARY)
        v_surf = self.font_bold.render(value, True, val_color)
        self.surface.blit(l_surf, (self.sidebar_x + 22, y))
        v_rect = v_surf.get_rect(topright=(self.sidebar_x + self.sidebar_width - 24, y))
        self.surface.blit(v_surf, v_rect)

    def _draw_mini_btn(self, rect: pygame.Rect, text: str, mouse_pos: Tuple[int, int]) -> None:
        hover = rect.collidepoint(mouse_pos)
        bg_col = COLOR_BTN_HOVER if hover else COLOR_BTN_BG
        pygame.draw.rect(self.surface, bg_col, rect, border_radius=3)
        pygame.draw.rect(self.surface, COLOR_BTN_BORDER, rect, 1, border_radius=3)
        t_surf = self.font_bold.render(text, True, COLOR_TEXT_PRIMARY)
        t_rect = t_surf.get_rect(center=rect.center)
        self.surface.blit(t_surf, t_rect)

    def _draw_action_btn(self, rect: pygame.Rect, text: str, mouse_pos: Tuple[int, int], border_color: Tuple[int, int, int]) -> None:
        hover = rect.collidepoint(mouse_pos)
        bg_col = COLOR_BTN_HOVER if hover else COLOR_BTN_BG
        pygame.draw.rect(self.surface, bg_col, rect, border_radius=6)
        pygame.draw.rect(self.surface, border_color, rect, 1, border_radius=6)
        t_surf = self.font_bold.render(text, True, COLOR_TEXT_PRIMARY)
        t_rect = t_surf.get_rect(center=rect.center)
        self.surface.blit(t_surf, t_rect)

    def handle_click(self, mouse_pos: Tuple[int, int]) -> Optional[str]:
        """Identifica si se hizo click sobre algún botón del HUD."""
        for action, rect in self.buttons.items():
            if rect.collidepoint(mouse_pos):
                return action
        return None
