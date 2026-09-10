"""
Módulo de Exportación y Análisis:
Generación de reporte TXT, integración HTTP con API externa y redacción del Informe Técnico (.docx).
"""

from .exporter import export_simulation_report
from .api_client import request_ai_analysis
from .doc_generator import generate_technical_docx_report

__all__ = [
    "export_simulation_report",
    "request_ai_analysis",
    "generate_technical_docx_report"
]
