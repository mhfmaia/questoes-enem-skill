# Estatísticas das provas do ENEM (corpus analisado)

## Corpus
- **Fonte**: página oficial "Provas e Gabaritos" do INEP
  (https://www.gov.br/inep/pt-br/areas-de-atuacao/avaliacao-e-exames-educacionais/enem/provas-e-gabaritos),
  consultada em 7 nov. 2026.
- **Recorte**: todas as edições de **1998 a 2025**, com **um caderno regular por dia de prova** (as demais cores
  trazem os mesmos itens em outra ordem; versões ampliadas, em braile, para leitor de tela e de reaplicação/PPL
  foram excluídas para não duplicar itens). São 49 cadernos no total.
- **Itens analisados em detalhe**: **3.510** itens de 2009 a 2025 (era TRI, quatro áreas de 45 itens; os itens de
  língua estrangeira de inglês e espanhol foram contados separadamente). As provas de 1998–2008 (63 itens
  interdisciplinares por prova, sem TRI) foram lidas apenas como contexto histórico.
- **Método**: extração automática do texto dos PDFs, separação por "QUESTÃO nn", divisão entre enunciado e
  alternativas e contagem de padrões. Imagens não são extraídas, então os tamanhos de texto **subestimam** itens
  com figura. Os números indicam tendências, não valores exatos.

## Resultados por área (2009–2025)

| Área | Itens | Enunciado mediano (car.) | p25–p75 | Alternativas (soma, mediana) | Termina em "?" | Termina em ":" | "Disponível em" | Ref. bibliográfica | "(adaptado)" | Comando negativo |
|---|---|---|---|---|---|---|---|---|---|---|
| LC | 945 | 764 | 258–1.164 | 410 | 1% | 1% | 38% | 44% | 30% | 0,3% |
| CH | 855 | 590 | 263–788 | 340 | 5% | 6% | 21% | 52% | 43% | 0,0% |
| CN | 855 | 541 | 288–762 | 255 | 18% | 5% | 18% | 22% | 32% | 0,1% |
| MT | 855 | 522 | 334–729 | 107 | 21% | 1% | 11% | 1% | 10% | 0,4% |

## Achados que orientam a skill
1. **Comandos negativos praticamente não existem** (< 0,5%): confirma a regra do Guia do BNI.
2. **LC e CH completam frases**; CN e MT usam mais perguntas diretas ("Qual é o/a…?").
3. **"o(a)" no fim do comando** ("é o(a)", "destaca o(a)", "crítica ao(à)") é recorrente: evita que o artigo denuncie o gabarito.
4. **Inícios de comando mais frequentes**: LC: "Nesse texto, a…", "De acordo com…", "Nesse poema…", "Nesse cartaz…";
   CH: "De acordo com…", "O texto apresenta…", "Nesse contexto, a…"; CN: "Qual é o/a…", "De acordo com…",
   "Do ponto de vista…", "Com base nas…"; MT: "Qual é a/o…", "De acordo com…", "Nessas condições, o/a…",
   "O número mínimo de…", "De quantas maneiras…".
5. **Finais mais frequentes em MT/CN**: "igual a", "é de", "próximo de", "são, respectivamente,".
6. **Dois textos (TEXTO I/II)** aparecem em ~6% dos itens não matemáticos.
7. **Alternativas numéricas** aparecem em ordem monotônica (crescente na maioria dos casos detectados, às vezes decrescente).
8. **Fontes atuais**: entre o acesso à fonte on-line e a prova, a defasagem mediana é de 1 ano (p75 = 4 anos).
9. **Domínios mais citados** nas referências on-line: portais de notícia (g1, BBC, Folha, O Globo, Estadão, UOL,
   Agência Brasil, Nexo, El País), divulgação científica (Ciência Hoje, Superinteressante, Inovação Tecnológica),
   órgãos públicos (IBGE, gov.br, Planalto, Ministério da Saúde) e o portal Domínio Público (literatura).
10. **Estrutura**: 45 itens por área; LC começa com 5 itens de língua estrangeira (inglês **ou** espanhol), com
    texto no idioma e comando e alternativas em português.

## Reprodução
O script `ferramentas/analisar_corpus.py` (na raiz do repositório) baixa os cadernos do site do INEP e refaz
estas contagens. Requer `pip install pypdf`.
