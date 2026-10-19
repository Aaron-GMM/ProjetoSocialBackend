from enum import Enum


class CodigoContran(str, Enum):
    """Códigos oficiais de sinalização vertical do CONTRAN."""

    # Regulamentação (Série R)
    R_1 = "R-1"
    R_2 = "R-2"
    R_3 = "R-3"
    R_4A = "R-4a"
    R_4B = "R-4b"
    R_5A = "R-5a"
    R_5B = "R-5b"
    R_6A = "R-6a"
    R_6B = "R-6b"
    R_6C = "R-6c"
    R_7 = "R-7"
    R_8A = "R-8a"
    R_8B = "R-8b"
    R_9 = "R-9"
    R_10 = "R-10"
    R_11 = "R-11"
    R_12 = "R-12"
    R_13 = "R-13"
    R_14 = "R-14"
    R_15 = "R-15"
    R_16 = "R-16"
    R_17 = "R-17"
    R_18 = "R-18"
    R_19 = "R-19"
    R_20 = "R-20"
    R_21 = "R-21"
    R_22 = "R-22"
    R_23 = "R-23"
    R_24A = "R-24a"
    R_24B = "R-24b"
    R_25A = "R-25a"
    R_25B = "R-25b"
    R_25C = "R-25c"
    R_25D = "R-25d"
    R_26 = "R-26"
    R_27 = "R-27"
    R_28 = "R-28"
    R_29 = "R-29"
    R_30 = "R-30"
    R_31 = "R-31"
    R_32 = "R-32"
    R_33 = "R-33"
    R_34 = "R-34"
    R_35A = "R-35a"
    R_35B = "R-35b"
    R_36A = "R-36a"
    R_36B = "R-36b"
    R_37 = "R-37"
    R_38 = "R-38"
    R_39 = "R-39"
    R_40 = "R-40"

    # Advertência (Principais da Série A)
    A_1A = "A-1a"
    A_1B = "A-1b"
    A_2A = "A-2a"
    A_2B = "A-2b"
    A_14 = "A-14"
    A_18 = "A-18"
    A_24 = "A-24"
    A_32A = "A-32a"
    A_32B = "A-32b"
    A_33A = "A-33a"
    A_33B = "A-33b"

    OUTRO = "OUTRO"


class TipoPelicula(str, Enum):
    """Tipos de película retrorrefletiva segundo ABNT NBR 14644."""

    TIPO_I = "TIPO_I"
    TIPO_II = "TIPO_II"
    TIPO_III = "TIPO_III"
    TIPO_IV = "TIPO_IV"
    TIPO_X = "TIPO_X"
    NAO_REFLETIVA = "NAO_REFLETIVA"
    OUTRO = "OUTRO"


class TipoSubstrato(str, Enum):
    """Materiais do substrato da placa."""

    ACO = "ACO"
    ALUMINIO = "ALUMINIO"
    MADEIRA = "MADEIRA"
    FIBRA = "FIBRA"
    PLASTICO = "PLASTICO"
    OUTRO = "OUTRO"


class TipoSuporte(str, Enum):
    """Tipos de suporte de fixação da placa."""

    POSTE_ACO = "POSTE_ACO"
    POSTE_MADEIRA = "POSTE_MADEIRA"
    POSTE_CONCRETO = "POSTE_CONCRETO"
    PORTICO = "PORTICO"
    COLUNA_SEMAFORICA = "COLUNA_SEMAFORICA"
    PAREDE_MURO = "PAREDE_MURO"
    OUTRO = "OUTRO"


class TipoEvento(str, Enum):
    """Tipos de evento no ciclo de vida Append-Only da placa."""

    CRIACAO = "CRIACAO"
    VISTORIA = "VISTORIA"
    DELECAO = "DELECAO"


class EstadoConservacao(str, Enum):
    """Estados de conservação geral e dos componentes da placa."""

    BOM = "BOM"
    REGULAR = "REGULAR"
    RUIM = "RUIM"
