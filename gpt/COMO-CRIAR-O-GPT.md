# Como usar a skill-enem no ChatGPT

O ChatGPT não instala arquivos `SKILL.md` do mesmo jeito que o Claude. O caminho mais estável é criar um
**GPT personalizado**. Ele é gratuito para usar; para **criar** um GPT é preciso um plano que permita isso.

## Opção A — GPT personalizado (recomendada)

1. Baixe `skill-enem-chatgpt.zip` na página **Releases** do repositório e descompacte.
2. No ChatGPT, abra **Explorar GPTs → Criar** (ou acesse chatgpt.com/gpts/editor) e vá para a aba **Configurar**.
3. **Nome:** `skill-enem — Questões no padrão ENEM`.
   **Descrição:** `Cria questões inéditas no padrão ENEM/INEP com Word e PDF no layout do caderno.`
4. **Instruções:** cole todo o conteúdo de `LEIA-instrucoes-para-colar-no-GPT.md`.
5. **Conhecimento:** envie **todos** os arquivos da pasta `conhecimento/` (os .md e os .py).
6. **Capacidades:** marque **Interpretador de código e análise de dados** (obrigatório para gerar Word e PDF).
   Marque **Pesquisa na web** se quiser textos-base de fontes reais. Marque **Geração de imagem** só se for usar
   imagens geradas por IA (consome mais limite do plano).
7. **Iniciadores de conversa** (sugestões):
   - `/skill-enem 5 questões de Biologia sobre vacinas, nível médio`
   - `/skill-enem simulado de Matemática com 10 questões e gráficos`
   - `/skill-enem revise esta questão: …`
8. Clique em **Criar** e escolha quem pode usar: só você, quem tiver o link ou a loja de GPTs.

## Opção B — Projeto do ChatGPT

Crie um **Projeto**, cole o conteúdo de `LEIA-instrucoes-para-colar-no-GPT.md` em *Instruções do projeto* e
envie os arquivos de `conhecimento/` em *Arquivos do projeto*. Converse dentro do projeto usando `/skill-enem …`.

## Opção C — Skills no ChatGPT ou no Codex

- **Codex CLI** (terminal da OpenAI): rode o instalador com `--codex` (veja o README). A skill fica em `~/.codex/skills/skill-enem`.
- Se a sua conta do ChatGPT já mostrar a opção de **Skills**, envie o mesmo `skill-enem.zip` usado no Claude.

## Observações
- No ChatGPT o PDF é gerado sem LaTeX (pelo ReportLab), com o mesmo layout de duas colunas. O `.tex` também é
  entregue: para o acabamento LaTeX, abra-o no Overleaf (gratuito) e compile com XeLaTeX.
- Se o GPT responder só com texto, peça: "gere agora o Word e o PDF com o gerar_prova.py".
