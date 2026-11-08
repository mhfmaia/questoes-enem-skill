# Formatos de saída

**Regra da skill:** toda vez que a skill gerar itens, entregue **sempre** um arquivo **Word (.docx)** e um **PDF**
no layout do caderno do ENEM, produzidos a partir de LaTeX. O caminho padrão é:

```
itens em JSON  ──►  scripts/gerar_prova.py  ──►  prova.tex  +  prova.pdf  +  prova.docx  (+ figuras/)
```

Também mostre os itens no chat, em texto, para revisão rápida, a menos que o professor peça só os arquivos.

## 1. Como gerar os arquivos

```bash
pip install python-docx matplotlib reportlab pymupdf      # uma vez (pymupdf é opcional)
python scripts/gerar_prova.py itens.json --saida saida --nome simulado-cn
# opções: --gabarito junto|separado|nenhum   --motor-pdf auto|latex|word|reportlab   --latex xelatex
```

- **PDF**: o script tenta, nesta ordem, **LaTeX** (tectonic, xelatex, lualatex, pdflatex), **LibreOffice**
  (Word→PDF) e **ReportLab**. Qualquer um gera o layout de duas colunas; com LaTeX o acabamento é o melhor.
- **Word**: sempre via python-docx, editável, com duas colunas, faixa de cabeçalho, figuras e gabarito.
- **.tex**: sempre salvo junto. O professor pode abrir no Overleaf e compilar com XeLaTeX (ou pdfLaTeX).
- Por padrão o gabarito comentado e a ficha técnica vão **no fim do mesmo arquivo**, em nova página.
  Use `--gabarito separado` para gerar `*_gabarito.pdf/.docx` (caderno do aluno sem respostas).
- Se faltar uma biblioteca, instale com `pip install …` e rode de novo. Se o ambiente não permitir executar
  código (ex.: chat sem execução), entregue o JSON e o `.tex` completos em blocos de código e explique ao professor
  como gerar os arquivos no computador (ver README do projeto).
- Ao terminar, **apresente os arquivos para download** e diga qual motor gerou o PDF.

## 2. Layout (igual ao caderno do ENEM)

- A4, **duas colunas** com fio separador, fonte sem serifa (Arial/Helvetica/TeX Gyre Heros) de 10 pt.
- **Faixa preta no topo** com a área em branco à esquerda e "DIA | CADERNO | COR | página" à direita.
- Título "**QUESTÃO 01**" em negrito; texto-base justificado; **referência pequena alinhada à direita**.
- Alternativas com a **letra dentro de um círculo**, recuo deslocado, sem parênteses.
- Figuras centralizadas na largura da coluna; tabelas com cabeçalho cinza.
- Cada item fica inteiro numa coluna sempre que couber.
- Rodapé discreto: "Material didático elaborado com a skill-enem. Não é material oficial do Inep."
  (não remova: evita que o simulado seja confundido com uma prova oficial; não use logotipos do Inep/MEC).

## 3. JSON da prova

```json
{
  "titulo": "Simulado ENEM — Ciências da Natureza",
  "subtitulo": "3ª série — 1º bimestre",
  "cabecalho": {"area": "CIÊNCIAS DA NATUREZA E SUAS TECNOLOGIAS", "dia": "2º DIA", "caderno": "CADERNO 1", "cor": "AZUL"},
  "numero_inicial": 91,
  "instrucoes": ["… (opcional; há instruções padrão)"],
  "itens": [
    {
      "area": "CN", "competencia": 2, "habilidade": "CN-H5", "eixo": "SP",
      "objeto": "Potência e consumo de energia em dispositivos elétricos",
      "dificuldade": "médio", "b_estimado": 600, "tempo_min": 3,
      "fonte_texto": "elaborado",
      "blocos": [
        {"tipo": "texto", "conteudo": "Parágrafo 1.\n\nParágrafo 2.", "referencia": "Texto elaborado para fins didáticos."},
        {"tipo": "figura", "grafico": { … }},
        {"tipo": "tabela", "cabecalho": ["Aparelho", "Potência (W)"], "linhas": [["Chuveiro", "5 500"]]},
        {"tipo": "referencia", "conteudo": "SOBRENOME, N. Título. Disponível em: www.site.org. Acesso em: 3 maio 2026 (adaptado)."}
      ],
      "enunciado": "Qual é o consumo mensal, em kWh, desse chuveiro?",
      "alternativas": {"A": "15", "B": "30", "C": "45", "D": "90", "E": "150"},
      "gabarito": "C",
      "justificativas": {"A": "…", "B": "…", "C": "…", "D": "…", "E": "…"},
      "comentario": "opcional: observação pedagógica"
    }
  ]
}
```

### Marcação de texto (em qualquer campo de texto)
- `**negrito**`, `*itálico*` (títulos de obras, estrangeirismos, nomes científicos).
- Fórmulas em LaTeX entre cifrões: `$v = \dfrac{\Delta s}{\Delta t}$`, `$\mathrm{H_2SO_4}$`, `$6\,600$`,
  `$1{,}5 \times 10^{3}$` (vírgula decimal entre chaves). No Word e no PDF sem LaTeX, as fórmulas viram texto
  Unicode automaticamente (frações como a/b, índices como H₂O).
- Moeda: escreva `R$ 12,50` normalmente (o script entende que não é fórmula). Para um cifrão literal use `\$`.
- Parágrafos separados por linha em branco (`\n\n`).
- **Não use emojis**: muitas fontes de impressão não os têm. Descreva-os em palavras se forem relevantes.

### Tipos de bloco
| tipo | campos | uso |
|---|---|---|
| `texto` | `conteudo`, `referencia` (opc.) | prosa do texto-base |
| `verso` | `conteudo` (quebras de linha preservadas), `referencia` | poemas, letras, falas |
| `rotulo` | `conteudo` | "TEXTO I", "TEXTO II" |
| `referencia` | `conteudo` | fonte alinhada à direita |
| `destaque` | `conteudo` | manchete, slogan, post, cartaz, texto em caixa |
| `tabela` | `cabecalho`, `linhas`, `titulo` (opc.) | quadros e tabelas |
| `figura` | ver tipos de figura abaixo; `largura` (0–1), `legenda`, `descricao` | gráficos, desenhos, imagens |

### Tipos de figura (todos aceitam `descricao`, usada quando a figura não puder ser desenhada)

**1. `grafico`** (matplotlib; funciona em qualquer ambiente, sem custo extra)
```json
{"tipo": "figura", "grafico": {
  "tipo_grafico": "barras | barras_horizontais | linhas | dispersao | pizza",
  "categorias": ["2019", "2020", "2021"],
  "series": [{"nome": "Produção", "valores": [12, 15, 11]}, {"nome": "Consumo", "valores": [10, 13, 14]}],
  "eixo_x": "Ano", "eixo_y": "Toneladas", "titulo": "opcional",
  "limites_y": [0, 20], "rotulos_valores": true, "grade": true, "tamanho": [3.4, 2.4]}}
```
Em `linhas`/`dispersao`, use `categorias` numéricas ou `"x": [...]` em cada série. Os tons são de cinza com
hachuras (como na prova impressa).

**2. `desenho`** (figuras geométricas e esquemas sem LaTeX; coordenadas em qualquer unidade)
```json
{"tipo": "figura", "desenho": {"tamanho": [3.3, 1.6], "elementos": [
  {"poligono": [[0,0],[7,0],[7,1.2]], "preenchimento": "#e6e6e6"},
  {"angulo_reto": [7,0], "tamanho": 0.3, "direcoes": [[-1,0],[0,1]]},
  {"cota": [[7.5,0],[7.5,1.2]], "texto": "0,6 m", "deslocamento": [0.6,0], "fundo": false},
  {"segmento": [[0,0],[3,2]], "estilo": "--"},
  {"seta": [[0,0],[1,1]]},
  {"circulo": {"centro": [2,2], "raio": 1}},
  {"retangulo": [[0,0],[2,1]], "hachura": "///"},
  {"arco": {"centro": [0,0], "raio": 1.3, "de": 0, "ate": 30, "texto": "α"}},
  {"ponto": [3,2], "rotulo": "A", "deslocamento": [0.15,0.15]},
  {"texto": "rampa", "pos": [3.3,0.95], "rotacao": 9.7, "italico": false}
]}}
```

**3. `tikz`** (melhor acabamento quando há LaTeX; use para geometria, circuitos, esquemas)
```json
{"tipo": "figura", "tikz": "\\begin{tikzpicture} … \\end{tikzpicture}", "ajustar_largura": true,
 "desenho": { … versão equivalente para quando não houver LaTeX … }, "descricao": "…"}
```
Bibliotecas TikZ carregadas: arrows.meta, calc, positioning, patterns, angles, quotes, shapes.geometric,
decorations.pathreplacing; também `pgfplots` (compat 1.18). **Sempre inclua uma versão `desenho`** ou uma
`descricao`, porque sem LaTeX o TikZ não é desenhado no Word.

**4. `imagem`** (arquivo PNG/JPG existente: foto, obra de arte, mapa, tirinha)
```json
{"tipo": "figura", "imagem": true, "arquivo": "figs/mapa.png", "descricao": "…", "legenda": "…"}
```
Caminho relativo ao JSON. Pode ser uma imagem enviada pelo professor, baixada de fonte com licença livre
(com referência) ou criada por um gerador de imagens da plataforma.

**5. `descricao`** (só a caixa com a descrição, para o professor inserir a imagem depois)
```json
{"tipo": "figura", "descricao": "Charge: um homem segura um guarda-chuva…"}
```

### Política de imagens (custo)
- **Gráficos, tabelas, desenhos geométricos e esquemas**: sempre em código (`grafico`, `desenho`, `tikz`, `tabela`).
  É exato, leve e **não gasta** créditos de geração de imagem.
- **Fotos, pinturas, charges, tirinhas e cartazes**: gerar imagem com IA **tem custo** (créditos, limites do plano,
  tempo) e pode falhar na grafia de textos dentro da imagem. Faça assim:
  1. se o professor enviou a imagem, use-a (`imagem`);
  2. se ele **pediu imagens geradas** e a plataforma tiver gerador, gere uma por item que realmente precisar e
     salve o arquivo; avise que isso consome créditos;
  3. caso contrário, use `descricao` (caixa com a descrição detalhada) e diga que o professor pode inserir a figura no Word.
- **Obras de arte e charges reais**: não imite o estilo de artistas vivos nem reproduza obras protegidas. Prefira
  descrever a obra e citar a referência, ou usar imagem em domínio público fornecida pelo professor.
- Imagens geradas por IA não podem ser apresentadas como documentos históricos ou fotos reais. Indique na legenda:
  "Imagem ilustrativa gerada por IA".

## 4. Formato no chat (resumo para revisão)

```
**QUESTÃO 01**

[texto-base]
                                         [referência]
[enunciado]

Ⓐ …
Ⓑ …
Ⓒ …
Ⓓ …
Ⓔ …
```
Depois: tabela-resumo `Questão | Gabarito | Habilidade | Dificuldade`, e os arquivos para download.

## 5. Outros formatos sob demanda

- **Tabela de especificação do simulado**: `Item | Área | Competência | Habilidade | Objeto | Dificuldade | b estimado | Gabarito`.
- **Folha de respostas**: grade com números e bolinhas A–E (peça ao script `--gabarito separado` e acrescente a grade no Word).
- **CSV/planilha** dos itens para importar em plataformas (colunas da ficha técnica + alternativas + gabarito).
- **Moodle/Google Forms**: ofereça o formato GIFT (Moodle) ou uma lista para colar no Forms, se pedirem.
