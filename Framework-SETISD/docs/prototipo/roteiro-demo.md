# Roteiro da demonstração (27/11/2026)

## Antes de começar (5 minutos antes)

1. Apague `data/app.db` e reinicie o sistema (`./dev.sh`). Os registros de exemplo (contatos, sem contato, finalizados) são criados com horários relativos ao momento em que o sistema sobe. Se o banco foi criado na véspera, todo mundo em "Em contato" aparece com o prazo vencido e "Finalizados hoje" fica vazio.
2. Entre com `admin` / `admin` em http://localhost:5173 (ou http://localhost:8000 com o build).
3. Deixe a fila aberta em "Todas as unidades", aba "A chamar".

Tudo o que aparece é sintético: nomes, prontuários e números de solicitação são fictícios, com a mesma estrutura e distribuição do extrato enviado pela TI.

## Roteiro (cerca de 3 minutos)

1. **A fila substitui a planilha.** Cada linha é um paciente, com todos os exames pendentes dele e o motivo da posição (lista de prioridade, espera acima do limite, ordem de chegada). Mostre um "Pedido repetido": mesmo exame em duas solicitações (RF015). No extrato há 22 casos.
2. **Busca pelo ticket.** Digite um número de solicitação na busca. É o número que o paciente traz impresso, e hoje a Central o pesquisa no AGHU.
3. **Fila por exame e vagas.** Abra Ultrassonografia, filtre por "USG axila" e informe 5 vagas abertas. A linha de corte mostra quem chamar agora. Depois informe 0: aparece o aviso de agenda sem vagas (RN-05), e a fila continua visível.
4. **Contato com o paciente.** Abra um paciente, escolha "Em contato" com a data oferecida e mostre a mensagem pronta para colar no WhatsApp. Registre: o paciente vai para a aba "Em contato". Use "Desfazer" no aviso para mostrar que nada se perde.
5. **O bloco de notas das 24 horas.** Na aba "Em contato", os pacientes sem resposta há mais de 24 horas aparecem em vermelho com "ofereça a vaga ao próximo". É a regra que a Central descreveu na validação de 06/11, hoje controlada num bloco de notas.
6. **Agendado e preparo.** Em outro paciente, escolha "Agendado no AGHU" e uma data: a mensagem inclui o preparo do exame. Os preparos atuais são exemplo, por isso a mensagem mostra "[preparo a confirmar com a UDI]".
7. **Regras.** Crie uma regra própria para um exame (RN-03). Cole uma lista de prontuários da nefrologia com validade. Mostre o histórico de alterações no fim da página.
8. **Painel.** Compare a espera dos pacientes da lista de prioridade com a dos demais e mostre os contatos com prazo vencido. Exporte o resumo em CSV.

## Perguntas para a Central e a gestão

1. **Unidade ou exame?** A regra de prioridade é definida por exame (RN-03) ou por unidade? O protótipo aceita os dois: a regra da unidade vale por padrão e o exame pode ter a sua.
2. **Ordem de contato e prazo de 24 horas.** Depois de 24 horas sem resposta, a vaga vai para o próximo. E o paciente que não respondeu: volta para o fim da fila, mantém a posição ou é cancelado depois de N tentativas?
3. **O formulário do Google pode ser aposentado?** Com a fila lida do AGHU, o formulário serve hoje só para trazer retorno, município e telefone. Se a TI incluir esses campos no extrato (D5), ele deixa de ser necessário. Se não incluir, a importação do formulário (RF016) entra no escopo.
4. **Quem mantém a lista de prioridade?** É a área solicitante (por exemplo, a nefrologia), a chefia da Central ou a gestão? Qual a validade padrão de uma inclusão?
5. **Validar os exemplos.** Ordem dos critérios e limite de 60 dias, as seis combinações de exames e os textos de preparo. Tudo está marcado como exemplo na interface.

## Perguntas para a TI (hipóteses, esquema do AGHU não verificado)

O protótipo não altera a consulta enviada pela TI. Os nomes de colunas abaixo são hipóteses a confirmar.

1. **Filtro pela unidade executora.** A consulta filtra pelo nome da unidade com `LIKE`. Existe um código da unidade executora no item da solicitação (algo como `ise.ufe_unf_seq`) para filtrar a UDI sem depender do texto?
2. **Situação do item.** Dá para trazer só os itens ainda não agendados ou realizados no AGHU (algo como `ise.sit_codigo`)? Hoje um exame marcado no AGHU continua no extrato até alguém registrar o resultado no AgendaHC.
3. **`LIKE '%UDI%'`** também casa com "FONOAUDIOLOGIA". Os 72 itens de fonoaudiologia devem entrar na fila da Central?
4. **Precedência do `AND`.** Na consulta enviada, o filtro de 60 dias vale só para a segunda condição do `OR`. A versão do protótipo usa parênteses.
5. **Campos que faltam (D5).** Telefone, município e data de retorno ao médico. Com eles, o retorno e a distância entram como critérios (RF014) e a mensagem ao paciente pode ser gerada já com o telefone.
6. **Frequência de leitura (D6).** De quanto em quanto tempo o extrato pode ser atualizado?
