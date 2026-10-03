from enum import Enum


class Role(str, Enum):
    ADMINISTRADOR = "ADMINISTRADOR"
    AGENTE = "AGENTE"
