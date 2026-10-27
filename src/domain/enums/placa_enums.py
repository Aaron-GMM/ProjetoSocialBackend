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


CONTRAN_DESCRICOES: dict[str, str] = {
    "R-1": "Parada Obrigatória (PARE)",
    "R-2": "Dê a Preferência",
    "R-3": "Sentido Proibido",
    "R-4a": "Proibido Virar à Esquerda",
    "R-4b": "Proibido Virar à Direita",
    "R-5a": "Proibido Retornar à Esquerda",
    "R-5b": "Proibido Retornar à Direita",
    "R-6a": "Proibido Estacionar",
    "R-6b": "Estacionamento Regulamentado",
    "R-6c": "Proibido Parar e Estacionar",
    "R-7": "Proibido Ultrapassar",
    "R-8a": "Proibido Mudar de Faixa da Esquerda para Direita",
    "R-8b": "Proibido Mudar de Faixa da Direita para Esquerda",
    "R-9": "Proibido Trânsito de Caminhões",
    "R-10": "Proibido Trânsito de Veículos Automotores",
    "R-11": "Proibido Trânsito de Veículos de Tração Animal",
    "R-12": "Proibido Trânsito de Bicicletas",
    "R-13": "Proibido Trânsito de Tratores e Máquinas de Obras",
    "R-14": "Peso Bruto Total Máximo Permitido",
    "R-15": "Altura Máxima Permitida",
    "R-16": "Largura Máxima Permitida",
    "R-17": "Peso Máximo Permitido por Eixo",
    "R-18": "Comprimento Máximo Permitido",
    "R-19": "Velocidade Máxima Permitida",
    "R-20": "Proibido Acionar Buzina ou Sinal Sonoro",
    "R-21": "Alfândega",
    "R-22": "Uso Obrigatório de Corrente",
    "R-23": "Conserve-se à Direita",
    "R-24a": "Sentido de Circulação da Via/Pista",
    "R-24b": "Passagem Obrigatória",
    "R-25a": "Vire à Esquerda",
    "R-25b": "Vire à Direita",
    "R-25c": "Siga em Frente ou à Esquerda",
    "R-25d": "Siga em Frente ou à Direita",
    "R-26": "Siga em Frente",
    "R-27": "Ônibus, Caminhões e Veículos de Grande Porte Mantenham-se à Direita",
    "R-28": "Duplo Sentido de Circulação",
    "R-29": "Proibido Trânsito de Pedestres",
    "R-30": "Pedestre, Ande pela Esquerda",
    "R-31": "Pedestre, Ande pela Direita",
    "R-32": "Circulação Exclusiva de Ônibus",
    "R-33": "Sentido de Circulação na Rotatória",
    "R-34": "Circulação Exclusiva de Bicicletas",
    "R-35a": "Ciclista, Transite à Esquerda",
    "R-35b": "Ciclista, Transite à Direita",
    "R-36a": "Ciclistas à Esquerda, Pedestres à Direita",
    "R-36b": "Pedestres à Esquerda, Ciclistas à Direita",
    "R-37": "Proibido Trânsito de Motocicletas, Motonetas e Ciclomotores",
    "R-38": "Proibido Trânsito de Ônibus",
    "R-39": "Circulação Exclusiva de Caminhão",
    "R-40": "Trânsito Proibido a Carros de Mão",
    "A-1a": "Curva Acentuada à Esquerda",
    "A-1b": "Curva Acentuada à Direita",
    "A-2a": "Curva à Esquerda",
    "A-2b": "Curva à Direita",
    "A-14": "Semáforo à Frente",
    "A-18": "Saliência ou Lombada",
    "A-24": "Obras",
    "A-32a": "Trânsito de Pedestres",
    "A-32b": "Passagem Sinalizada de Pedestres",
    "A-33a": "Área Escolar",
    "A-33b": "Passagem Sinalizada de Escolares",
    "OUTRO": "Outro",
}


def resolve_codigo_contran_filter(termo: str) -> list[str]:
    """Mapeia termos, aliases ou descrições para os códigos CONTRAN correspondentes."""
    import unicodedata

    termo_limpo = termo.strip().upper()
    if not termo_limpo:
        return []

    # 1. Checagem direta pelo valor do Enum (ex: 'R-1', 'A-18')
    for code in CodigoContran:
        if code.value.upper() == termo_limpo:
            return [code.value]

    # 2. Checagem ignorando hífen (ex: 'R1' -> 'R-1', 'A18' -> 'A-18')
    termo_sem_hifen = termo_limpo.replace("-", "")
    for code in CodigoContran:
        if code.value.upper().replace("-", "") == termo_sem_hifen:
            return [code.value]

    # 3. Busca textual sem acentos na descrição ou no código
    def strip_accents(text: str) -> str:
        return "".join(
            c
            for c in unicodedata.normalize("NFD", text)
            if unicodedata.category(c) != "Mn"
        ).upper()

    termo_norm = strip_accents(termo_limpo)
    matched: list[str] = []
    for code_val, desc in CONTRAN_DESCRICOES.items():
        desc_norm = strip_accents(desc)
        if termo_norm in desc_norm or termo_norm in strip_accents(code_val):
            matched.append(code_val)

    if matched:
        return matched

    return [termo.strip()]


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
