from uuid import UUID, uuid4

from src.domain.models.municipio import Municipio


def test_criar_municipio_com_sucesso_gerando_id_automatico():
    """
    CENÁRIO: Criação básica de um Município sem fornecer um ID explícito.
    ESPERADO: O SQLModel deve gerar um UUID4 automaticamente para o campo 'id'.
    """
    mun = Municipio(nome="Quixadá", codigo_ibge="2311306")

    assert isinstance(mun.id, UUID), (
        "O ID deve ser gerado automaticamente como um UUID."
    )
    assert mun.nome == "Quixadá"
    assert mun.codigo_ibge == "2311306"
    assert mun.poligono is None, (
        "Sem conexão com o banco, o polígono deve iniciar nulo."
    )


def test_criar_municipio_fornecendo_id_explicito():
    """
    CENÁRIO: Criação de um Município com ID customizado (ex: via seed).
    ESPERADO: O sistema deve respeitar o ID passado e não gerar um novo.
    """
    id_customizado = uuid4()
    mun = Municipio(id=id_customizado, nome="Fortaleza", codigo_ibge="2304400")

    assert mun.id == id_customizado


def test_municipio_aceita_qualquer_valor_para_poligono_em_memoria():
    """
    CENÁRIO: Passar um valor arbitrário para o campo poligono (como uma string WKT).
    ESPERADO: O Pydantic não deve quebrar graças à tipagem 'Any', permitindo
              que a responsabilidade de conversão geométrica fique para o SQLAlchemy.
    """
    mun = Municipio(
        nome="Sobral", codigo_ibge="2312908", poligono="POLYGON((0 0, 1 1))"
    )

    # Valida se o 'Any' no modelo evitou quebras de Type Checking
    assert mun.poligono == "POLYGON((0 0, 1 1))"
