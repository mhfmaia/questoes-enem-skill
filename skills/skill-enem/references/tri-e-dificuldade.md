# TRI, dificuldade e montagem de simulados

Fontes: INEP. *Entenda a sua nota no Enem: guia do participante* (2021); INEP. *Exame Nacional do Ensino Médio —
Enem: procedimentos de análise* (2021); INEP. *Guia de Elaboração e Revisão de Itens* (2010).

## 1. O que a TRI faz no ENEM (explicação para professores)

- Desde 2009 o ENEM calcula as notas das provas objetivas pela **Teoria de Resposta ao Item (TRI)**, com o
  **modelo logístico de três parâmetros** (Birnbaum, 1968):

  P(acerto | θ) = c + (1 − c) · 1 / (1 + e^(−D·a·(θ − b)))

  - **a — discriminação**: quanto o item separa quem domina de quem não domina a habilidade (inclinação da curva).
  - **b — dificuldade**: posição do item na mesma régua da proficiência; quanto maior, mais difícil.
  - **c — acerto casual**: chance de acerto de quem não domina a habilidade ("chute"); fica tipicamente perto de 0,2 com 5 alternativas, e cai quando os distratores são muito atrativos.
  - **θ — proficiência** do participante. D é uma constante de escala (convencionalmente 1,7).
- Os parâmetros vêm de **pré-testes** com amostras parecidas com o público do ENEM, e o banco de itens (BNI)
  guarda itens já calibrados. A prova real é montada com itens de dificuldades variadas.
- A escala de cada área tem **média 500 e desvio-padrão 100**, referidos aos concluintes regulares de escola
  pública de 2009. Transformação: θ(500,100) = 100·θ(0,1) + 500; b(500,100) = 100·b(0,1) + 500; a(500,100) = a(0,1)/100; c não muda.
- **Não há mínimo nem máximo fixos** (não é 0 a 1000): dependem dos itens de cada prova. Ex.: em 2020, quem acertou
  as 45 de Ciências Humanas teria 862,6; o máximo de outra prova foi 859,8.
- A nota é estimada pelo método **EAP** (*Expected a Posteriori*), com 40 pontos de quadratura e distribuição a priori normal.
- **Coerência pedagógica**: quem acerta itens difíceis e erra fáceis tem os acertos difíceis tratados como mais
  prováveis de serem casuais, e eles somam menos. Duas pessoas com o mesmo número de acertos podem ter notas
  diferentes. Ainda assim, mais acertos levam, em geral, a nota maior, e **chutar nunca diminui a nota** (item em
  branco conta como erro).
- Os parâmetros **não são pesos**: não existe "a questão X vale mais". O INEP divulga os parâmetros só 5 anos depois da prova.
- Cada item é posicionado na régua onde a **probabilidade de acerto é ≈ 0,65**, geralmente um pouco acima de b.
- Antes da TRI, o INEP faz a análise clássica (TCT): % de acerto, % de escolha de cada alternativa, índice de
  discriminação (grupos superior e inferior de 27%) e **bisserial** por alternativa. O bisserial do gabarito deve
  ser positivo e o dos distratores negativo; distrator com bisserial positivo indica possível erro de gabarito ou
  dupla resposta. → `scripts/analisar_respostas.py` faz exatamente isso com os dados de uma turma.
- Pressupostos: **unidimensionalidade** (um traço dominante por área) e **independência local** (a resposta de um
  item não depende de outro). Consequência prática para quem elabora: **um item não pode dar a dica de outro**, e
  itens do mesmo texto-base devem ser independentes entre si.

### O que a skill pode e não pode prometer
- **Pode**: estimar a dificuldade de um item com critérios pedagógicos, escrever itens que tendem a ter boa
  discriminação, montar simulados com gradação e analisar as respostas da turma (TCT).
- **Não pode**: dar os parâmetros reais de um item novo nem a "nota TRI oficial" de um aluno. Parâmetros só existem
  depois de aplicar o item a muitos estudantes. `simular_tri.py` usa **parâmetros estimados** e serve para ensinar a
  lógica da TRI, não para prever a nota do ENEM. Diga isso ao professor sempre que falar em "nota TRI".

## 2. Como estimar a dificuldade de um item (ficha técnica)

Use três níveis do Guia do BNI (**fácil, médio, difícil**) e uma faixa estimada de **b na escala 500/100**:

| Nível | b estimado | Perfil |
|---|---|---|
| Fácil | < 500 | 1 passo; informação explícita no texto; conceito básico; distratores claramente distinguíveis por quem domina o básico. |
| Médio | 500–650 | 2–3 passos; inferência local; conversão entre representações (gráfico → valor); distratores ligados a erros frequentes. |
| Difícil | > 650 | vários passos ou modelagem; inferência global ou relação entre textos; conceito menos trabalhado; distratores muito atrativos que exigem domínio fino. |

Na prova real, a maioria dos itens tem b acima de 500 (a média de referência é a de 2009). Muitos concluintes erram
itens "médios". Ao estimar, pense em **quem é o concluinte médio de escola pública**, não nos melhores alunos.

### Alavancas de dificuldade (use para criar versões fácil/média/difícil da mesma habilidade)

| Alavanca | Mais fácil | Mais difícil |
|---|---|---|
| Passos de raciocínio | 1 operação ou relação | encadear 3+ etapas |
| Localização da informação | explícita, no comando | dispersa, em texto + tabela + gráfico |
| Inferência | literal/local | global, implícita, entre dois textos |
| Representação | uma só | conversão (texto ↔ gráfico ↔ equação) |
| Conceito | básico, muito ensinado | menos trabalhado ou contraintuitivo |
| Distratores | erros pouco frequentes | erros muito comuns (senso comum, passo intermediário) |
| Dados | números redondos | decimais, unidades a converter, dado irrelevante plausível |
| Comando | pergunta direta | completar avaliando proposta/argumento |

**Cuidado:** dificuldade deve vir da **habilidade**, não de obstáculos ilegítimos (texto longo sem necessidade,
vocabulário raro, ambiguidade, pegadinha). Obstáculos ilegítimos derrubam a **discriminação (a)**: alunos bons
também erram e o item mede menos.

### Como escrever itens com boa discriminação
- Um único construto: o acerto precisa depender da habilidade-alvo, não de leitura cansativa ou cálculo braçal.
- Distratores que correspondem a erros de **quem não domina** (e que quem domina descarta com segurança).
- Nenhuma alternativa "quase certa" que um aluno forte possa defender (isso gera bisserial positivo em distrator).
- Gabarito que não se destaca por forma (extensão, termos técnicos, repetição do texto).

## 3. Montagem de simulado

1. **Quantidade e tempo**: 45 itens por área. No ENEM, o 1º dia tem 5h30 (LC + CH + redação) e o 2º dia tem 5h
   (CN + MT), o que dá cerca de 3 minutos por item. Um simulado de uma área cabe em ~2h15.
2. **Cobertura da matriz**: distribua os itens pelas competências da área; não repita habilidade mais de 2–3 vezes
   em 45 itens, salvo pedido. Varie os objetos de conhecimento e os contextos (regiões do Brasil, campo/cidade, gêneros, gráficos).
3. **Distribuição de dificuldade sugerida** (45 itens): ~12 fáceis, ~20 médios, ~13 difíceis. Para turmas
   iniciantes, inverta o peso para mais itens fáceis.
4. **Ordem**: o ENEM **não ordena por dificuldade**. Misture os níveis, mas evite começar com uma sequência de difíceis.
   Em LC, os itens 1–5 são de língua estrangeira (ofereça versão inglês **e** espanhol se a turma escolher).
5. **Gabarito equilibrado**: cerca de 9 de cada letra em 45 itens, sem mais de 3 iguais seguidos e sem padrão visível (ABCDE…).
6. **Independência**: nenhum item pode entregar a resposta de outro; no máximo 3 itens por texto-base, com habilidades diferentes.
7. **Entrega**: caderno do aluno (sem respostas) + gabarito + gabarito comentado + tabela de especificação
   (item × habilidade × dificuldade). Ver `formatos-de-saida.md`.
8. **Depois da aplicação**: ofereça `analisar_respostas.py` para identificar itens problemáticos e habilidades a retomar.

## 4. Perguntas frequentes de professores e alunos

- **"Quanto vale cada questão?"** Nenhum valor fixo; a TRI não usa pesos.
- **"Dá para calcular a nota TRI do meu simulado?"** Só de forma aproximada e didática, com parâmetros estimados
  (`simular_tri.py`). A nota oficial depende de parâmetros calibrados com milhões de respostas.
- **"Por que acertei mais e tirei menos?"** A prova pode ter itens mais fáceis, ou o padrão de respostas pode ter sido
  menos coerente (erros em itens fáceis).
- **"Chutar prejudica?"** Não. Um acerto nunca diminui a nota; acertos incoerentes apenas somam menos.
- **"Dá para comparar a nota de Matemática com a de Humanas?"** Não diretamente: cada área tem sua própria escala.
