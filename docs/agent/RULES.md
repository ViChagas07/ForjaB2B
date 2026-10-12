# Regras

No início de TODA sessão, leia docs/agent/RULES.md e docs/agent/PROGRESS.md. Se o progresso indicar um passo em andamento, continue dele, sem refazer passos concluídos.
Trabalhe em passos numerados, um de cada vez. Só avance quando o passo atual estiver implementado, testado e verificado.
Ao fim de cada passo: (a) rode as checagens do passo; (b) faça um commit local pequeno (mensagem convencional, causa/mudança no corpo); (c) acrescente 2 a 4 linhas ao PROGRESS.md: passo, resultado real das checagens, pendências.
Se uma checagem falhar: investigue a causa e corrija (até 3 tentativas). Se persistir, escreva no PROGRESS.md BLOQUEADO: motivo + comando + saída relevante e pare essa parte. Nunca apague, enfraqueça ou ignore testes para ficar verde.
Ao terminar a parte, pare. Não inicie a próxima parte nem funcionalidades fora do pedido. Entregue o relatório curto (seção 5).
Economize contexto: use busca (grep, listagem de diretório) antes de abrir arquivos; leia só o necessário; faça edições pequenas; não cole arquivos inteiros nas respostas.
Na primeira sessão, descubra e anote em PROGRESS.md, sob "Comandos de checagem", os comandos reais do repositório (Makefile, pyproject.toml, package.json) para testes, Ruff, formatação, mypy, import-linter e frontend. Reutilize essa anotação depois.

2. Limites e segurança (valem sempre)
Não faça push. Commits somente locais.
Sem comandos destrutivos: nunca apague, recrie ou limpe volumes; proibido docker compose down -v, docker volume rm, docker system prune --volumes, git reset --hard, git clean -fd. stop, start e up -d são permitidos.
Backup lógico (pg_dump) do banco de desenvolvimento antes de aplicar qualquer migration, e confirme que o arquivo não está vazio.
Sem segredos no repositório, em logs, comandos ou respostas. Nunca peça nem use senhas, API keys ou connection strings reais de produção.
Não toque em .commandcode/ nem em arquivos de ferramentas do agente; apenas informe o que encontrar.
Não invente dados técnicos de produto (CA, normas, certificações, potência, medidas, materiais).
Não declare executado o que só foi inspecionado ou simulado. O que não puder ser validado vai como NÃO VALIDADO, com o motivo.
Para validar o Compose, use docker compose --env-file .env.example config --quiet.

3. Arquitetura (valem sempre)
Clean Architecture (domínio → aplicação → infraestrutura → interface); respeite o import-linter.
Audite antes de criar: não duplique módulos, tabelas, endpoints, telas nem configurações. Sem refatoração geral.
PostgreSQL é a fonte de verdade. Elasticsearch e embeddings são derivados e nunca guardam preço, dados privados nem segredos.
Preços, visibilidade e autorização seguem as regras existentes (preço consultivo para visitante; preço por empresa para autenticado; tenant sempre vindo do JWT; RBAC).
Falha de indexação nunca bloqueia operação de catálogo.
Texto de usuário é texto simples: sem HTML, com limites de tamanho.

4. Checagens padrão

Rode as aplicáveis ao passo (use os comandos anotados em PROGRESS.md):

Backend: testes direcionados do passo; ao fim da parte, suíte completa com Docker e a suíte padrão sem Docker (esta deve terminar sem erros); Ruff (check e formatação), mypy strict, import-linter.
Frontend (quando houver mudança): typecheck, lint, testes.
Infra: docker compose --env-file .env.example config --quiet.

5. Relatório curto ao final de cada parte
Resumo do que foi feito, por passo.
Arquivos criados e modificados.
Comandos executados e resultados reais.
NÃO VALIDADO e riscos.
Commits locais criados (hash e título). Sem push.