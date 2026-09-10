"""
Modelos de dominio de la red: Paquetes, Nodos (Routers) y Enlaces (Links).
"""

from .packet import Packet, PacketStatus
from .node import RouterNode
from .link import NetworkLink

__all__ = ["Packet", "PacketStatus", "RouterNode", "NetworkLink"]
