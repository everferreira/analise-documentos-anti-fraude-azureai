"""Anti-fraude de documentos — motor de regras, parser e score."""

from .models import CampoExtraido, Extracao, RelatorioAnalise, Verificacao, hash_arquivo
from .parser import parse_campos
from .rules import aplicar_regras, TIPOS_VALIDOS
from .score import gerar_relatorio

__all__ = [
    "CampoExtraido", "Extracao", "RelatorioAnalise", "Verificacao", "hash_arquivo",
    "parse_campos", "aplicar_regras", "gerar_relatorio", "TIPOS_VALIDOS",
]