"""criar base de endereços oficiais (CNEFE, bairros e distritos do IBGE)

Revision ID: 9a7d23fd35a3
Revises: b571b1984dfc
Create Date: 2026-11-20 11:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from geoalchemy2 import Geometry

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9a7d23fd35a3"
down_revision: Union[str, None] = "b571b1984dfc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    # O geoalchemy2 cria automaticamente os índices GiST das colunas
    # geométricas ("idx_<tabela>_<coluna>"; spatial_index=True é o padrão),
    # usados nas buscas por ponto (ST_Contains) e por vizinhos (<->).
    op.create_table(
        "divisoes_territoriais",
        sa.Column("codigo", sa.String(), nullable=False),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("nome", sa.String(), nullable=False),
        sa.Column("codigo_municipio", sa.String(), nullable=False),
        sa.Column("sede", sa.Boolean(), nullable=False),
        sa.Column("geom", Geometry("MULTIPOLYGON", srid=4326), nullable=False),
        sa.PrimaryKeyConstraint("codigo"),
    )
    op.create_index(
        op.f("ix_divisoes_territoriais_codigo_municipio"),
        "divisoes_territoriais",
        ["codigo_municipio"],
        unique=False,
    )

    op.create_table(
        "enderecos_referencia",
        sa.Column(
            "cod_unico_endereco", sa.BigInteger(), autoincrement=False, nullable=False
        ),
        sa.Column("codigo_municipio", sa.String(), nullable=False),
        sa.Column("codigo_distrito", sa.String(), nullable=False),
        sa.Column("logradouro", sa.String(), nullable=True),
        sa.Column("localidade", sa.String(), nullable=True),
        sa.Column("bairro_correios", sa.String(), nullable=True),
        sa.Column("bairro", sa.String(), nullable=True),
        sa.Column("cep", sa.String(), nullable=True),
        sa.Column("cidade", sa.String(), nullable=False),
        sa.Column("estado", sa.String(), nullable=False),
        sa.Column("location", Geometry("POINT", srid=4326), nullable=False),
        sa.PrimaryKeyConstraint("cod_unico_endereco"),
    )
    op.create_index(
        op.f("ix_enderecos_referencia_codigo_municipio"),
        "enderecos_referencia",
        ["codigo_municipio"],
        unique=False,
    )
    op.create_index(
        op.f("ix_enderecos_referencia_codigo_distrito"),
        "enderecos_referencia",
        ["codigo_distrito"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_enderecos_referencia_codigo_distrito"),
        table_name="enderecos_referencia",
    )
    op.drop_index(
        op.f("ix_enderecos_referencia_codigo_municipio"),
        table_name="enderecos_referencia",
    )
    op.drop_table("enderecos_referencia")
    op.drop_index(
        op.f("ix_divisoes_territoriais_codigo_municipio"),
        table_name="divisoes_territoriais",
    )
    op.drop_table("divisoes_territoriais")
