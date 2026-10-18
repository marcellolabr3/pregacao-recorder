# Converte um Markdown em PDF (HTML intermediario + xhtml2pdf).
# Uso:  <python> scripts/md_para_pdf.py entrada.md saida.pdf
# Feito para os documentos do projeto (fontes sem acento, tabelas e
# blocos de fluxograma em monoespacada).
import sys
from pathlib import Path

import markdown
from xhtml2pdf import pisa

CSS = """
@page { size: a4; margin: 2cm 1.8cm; }
body { font-family: Helvetica, Arial, sans-serif; font-size: 10.5pt;
       line-height: 1.45; color: #1a1a1a; }
h1 { font-size: 19pt; color: #0b3d62; border-bottom: 2px solid #0b3d62;
     padding-bottom: 4px; }
h2 { font-size: 14pt; color: #0b3d62; margin-top: 16px; }
h3 { font-size: 12pt; color: #333; }
table { width: 100%; margin: 8px 0; }
th { background: #0b3d62; color: #fff; font-size: 9.5pt; padding: 4px 6px;
     text-align: left; }
td { border: 1px solid #bbb; font-size: 9.5pt; padding: 4px 6px;
     vertical-align: top; }
tr:nth-child(even) td { background: #f2f6fa; }
pre { background: #f4f4f4; border: 1px solid #ccc; padding: 8px;
      font-family: Courier, monospace; font-size: 8.5pt; }
code { font-family: Courier, monospace; font-size: 9.5pt; }
strong { color: #0b3d62; }
blockquote { border-left: 3px solid #0b3d62; margin-left: 0;
             padding-left: 10px; color: #333; }
"""


def main() -> int:
    if len(sys.argv) != 3:
        print("uso: md_para_pdf.py entrada.md saida.pdf")
        return 2
    entrada = Path(sys.argv[1])
    saida = Path(sys.argv[2])
    corpo = markdown.markdown(
        entrada.read_text(encoding="utf-8"),
        extensions=["tables", "fenced_code"],
    )
    html = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<style>{CSS}</style></head><body>{corpo}</body></html>"
    )
    saida.parent.mkdir(parents=True, exist_ok=True)
    with open(saida, "wb") as fh:
        erro = pisa.CreatePDF(html, dest=fh, encoding="utf-8")
    if erro.err:
        print(f"erro ao gerar {saida}")
        return 1
    tamanho = saida.stat().st_size
    print(f"ok: {saida} ({tamanho} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
