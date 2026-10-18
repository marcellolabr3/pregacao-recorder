"""Importador CSV/XLSX de programacao de pregacoes (S4).

Formato esperado (colunas obrigatorias):
  data, horario, pregador, igreja, texto_base, tema

Exemplo CSV:
  data,horario,pregador,igreja,texto_base,tema
  2026-10-25,19:00,Pr. Joao Silva,Igreja Central,Joao 3:16,"O Amor de Deus"
  2026-11-01,09:30,Pr. Maria Santos,Igreja Norte,Romanos 8:28,"Todas as Coisas Cooperam"

Regras:
- data: AAAA-MM-DD (valida formato)
- horario: HH:MM (valida formato 24h)
- pregador/igreja: nao vazios
- texto_base/tema: opcionais
- Duplicatas (mesma data+horario) sao detectadas e reportadas
- Nao grava nada ate confirmacao (previa -> confirmar -> gravar)
"""
from __future__ import annotations
import csv
import io
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import openpyxl
except ImportError:
    openpyxl = None  # so erro se tentar usar XLSX sem instalar


@dataclass
class PregacaoImportada:
    """Uma linha da planilha, ja validada."""
    data: str
    horario: str
    pregador: str
    igreja: str
    texto_base: str
    tema: str
    linha_origem: int  # para mensagens de erro

    def to_dict(self) -> Dict[str, Any]:
        return {
            "data": self.data,
            "horario": self.horario,
            "pregador": self.pregador,
            "igreja": self.igreja,
            "texto_base": self.texto_base,
            "tema": self.tema,
        }


@dataclass
class ResultadoImportacao:
    """Resultado da leitura/validacao (antes de gravar)."""
    validos: List[PregacaoImportada]
    erros: List[Dict[str, Any]]  # {linha, campo, mensagem, valor}
    duplicatas: List[Dict[str, Any]]  # {linha, data, horario, existente_id}


def _validar_data(valor: str) -> Tuple[bool, str]:
    valor = valor.strip()
    try:
        datetime.strptime(valor, "%Y-%m-%d")
        return True, ""
    except ValueError:
        return False, f"data invalida (use AAAA-MM-DD): {valor}"


def _validar_horario(valor: str) -> Tuple[bool, str]:
    valor = valor.strip()
    try:
        datetime.strptime(valor, "%H:%M")
        return True, ""
    except ValueError:
        return False, f"horario invalido (use HH:MM 24h): {valor}"


def _validar_campo_obrigatorio(valor: str, nome: str) -> Tuple[bool, str]:
    if not valor or not valor.strip():
        return False, f"{nome} obrigatorio"
    return True, ""


def _ler_csv(conteudo: str) -> List[Dict[str, str]]:
    """Le CSV com delimitador auto-detectado (virgula ou ponto-virgula)."""
    # tenta detectar delimitador
    amostra = conteudo[:1024]
    try:
        dialect = csv.Sniffer().sniff(amostra, delimiters=",;")
    except csv.Error:
        dialect = csv.excel
    leitor = csv.DictReader(io.StringIO(conteudo), dialect=dialect)
    # normaliza nomes de colunas (lower, strip)
    if leitor.fieldnames:
        leitor.fieldnames = [c.strip().lower() for c in leitor.fieldnames]
    return [dict((k.strip().lower(), v.strip()) for k, v in row.items()) for row in leitor]


def _ler_xlsx(caminho: Path) -> List[Dict[str, str]]:
    """Le XLSX (primeira aba). Requer openpyxl."""
    if openpyxl is None:
        raise RuntimeError("openpyxl nao instalado (pip install openpyxl)")
    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    linhas = list(ws.iter_rows(values_only=True))
    if not linhas:
        return []
    cabecalho = [str(c).strip().lower() if c else "" for c in linhas[0]]
    resultado = []
    for i, linha in enumerate(linhas[1:], start=2):
        row = {}
        for j, valor in enumerate(linha):
            if j < len(cabecalho) and cabecalho[j]:
                row[cabecalho[j]] = str(valor).strip() if valor is not None else ""
        resultado.append(row)
    return resultado


def _validar_linhas(
    linhas: List[Dict[str, str]], db_existente: callable
) -> ResultadoImportacao:
    """Valida cada linha e detecta duplicatas contra o banco."""
    validos = []
    erros = []
    duplicatas = []
    colunas_obrigatorias = ["data", "horario", "pregador", "igreja"]

    for idx, row in enumerate(linhas, start=2):  # linha 1 = cabecalho
        # ignora linhas completamente vazias
        if not any(v for v in row.values()):
            continue

        tem_erro = False
        # valida colunas obrigatorias
        for col in colunas_obrigatorias:
            valor = row.get(col, "")
            if col in ("data", "horario"):
                ok, msg = (_validar_data(valor) if col == "data" else _validar_horario(valor))
            else:
                ok, msg = _validar_campo_obrigatorio(valor, col)
            if not ok:
                erros.append({
                    "linha": idx,
                    "campo": col,
                    "mensagem": msg,
                    "valor": valor,
                })
                tem_erro = True

        if tem_erro:
            continue

        # duplicata contra banco?
        data = row.get("data", "").strip()
        horario = row.get("horario", "").strip()
        existente = db_existente(data, horario)
        if existente:
            duplicatas.append({
                "linha": idx,
                "data": data,
                "horario": horario,
                "existente_id": existente["id"],
                "existente_pregador": existente["pregador"],
            })
            continue

        validos.append(PregacaoImportada(
            data=data,
            horario=horario,
            pregador=row.get("pregador", "").strip(),
            igreja=row.get("igreja", "").strip(),
            texto_base=row.get("texto_base", "").strip(),
            tema=row.get("tema", "").strip(),
            linha_origem=idx,
        ))

    return ResultadoImportacao(validos=validos, erros=erros, duplicatas=duplicatas)


def importar_csv(conteudo: str, db_existente: callable) -> ResultadoImportacao:
    """Le e valida CSV. Nao grava no banco."""
    linhas = _ler_csv(conteudo)
    return _validar_linhas(linhas, db_existente)


def importar_xlsx(caminho: Path, db_existente: callable) -> ResultadoImportacao:
    """Le e valida XLSX. Nao grava no banco."""
    linhas = _ler_xlsx(caminho)
    return _validar_linhas(linhas, db_existente)


def gravar_pregacoes(db, pregacoes: List[PregacaoImportada]) -> List[int]:
    """Grava as pregacoes validadas no banco. Retorna lista de IDs inseridos."""
    ids = []
    for p in pregacoes:
        pid = db.create_pregacao(
            data=p.data,
            horario=p.horario,
            pregador=p.pregador,
            igreja=p.igreja,
            texto_base=p.texto_base,
            tema=p.tema,
        )
        ids.append(pid)
    return ids


def gerar_modelo_csv() -> str:
    """Gera um CSV modelo com cabecalho e duas linhas de exemplo."""
    return (
        "data,horario,pregador,igreja,texto_base,tema\n"
        "2026-10-25,19:00,Pr. Joao Silva,Igreja Central,\"Joao 3:16\",\"O Amor de Deus\"\n"
        "2026-11-01,09:30,Pr. Maria Santos,Igreja Norte,\"Romanos 8:28\",\"Todas as Coisas Cooperam\"\n"
    )