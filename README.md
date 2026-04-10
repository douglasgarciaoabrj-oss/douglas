# Monitoramento de Processos Parados (LinkLei)

## 1) Arquitetura da solução

### Objetivo
Identificar automaticamente processos sem movimentação recente (30/60/90 dias), priorizar por criticidade e disparar alertas acionáveis.

### Arquitetura proposta (simples e escalável)

```text
[LinkLei API | Exportação CSV/XLSX | Scraping controlado]
                 |
                 v
          [Coletor de Dados]
                 |
                 v
        [Banco SQLite/PostgreSQL]
                 |
                 v
 [Motor de Regras de Inatividade + Prioridade]
                 |
      +----------+-----------+
      |                      |
      v                      v
[Alertas e Notificações]   [Dashboard/Relatórios]
      |                      |
      v                      v
 Email / Teams / Slack    Streamlit / BI / CSV
```

### Componentes
1. **Coletor de dados**
   - Fonte preferencial: API do LinkLei (quando disponível).
   - Fallback: importação de exportações CSV/XLSX.
   - Último recurso: scraping com autenticação e controle de taxa.
2. **Persistência**
   - **MVP**: SQLite (baixo custo operacional).
   - Escala: PostgreSQL.
3. **Motor de regras**
   - Calcula dias sem movimentação por processo.
   - Classifica em faixas (30/60/90+).
   - Aplica pesos por prioridade e tipo.
4. **Alertas**
   - E-mail diário/resumo por responsável.
   - Opcional: webhook para Teams/Slack.
5. **Visualização**
   - Dashboard com filtros (responsável, tipo, prioridade, faixa de atraso).
   - Relatório CSV para auditoria e ação.
6. **Ações sugeridas**
   - Geração de “próxima ação” por regra de negócio.

---

## 2) Tecnologias recomendadas

### Stack sugerida (MVP robusto)
- **Python 3.11+**: excelente ecossistema para ETL e automação.
- **pandas**: leitura e transformação de planilhas.
- **sqlite3** (nativo) + opção PostgreSQL futura.
- **APScheduler / cron**: agendamento diário.
- **smtplib** (nativo) para e-mail (ou SendGrid futuramente).
- **Streamlit** para dashboard rápido.

### Justificativa técnica
- Minimiza dependências externas complexas.
- Curva de aprendizado baixa para manutenção.
- Fácil evolução para arquitetura com filas/serviços quando volume crescer.

---

## 3) Fluxo de funcionamento (passo a passo)

1. **Ingestão**
   - Job diário busca API ou lê `data/processos.csv`.
2. **Normalização**
   - Padroniza campos: `id`, `numero`, `tipo`, `prioridade`, `ultima_movimentacao`, `responsavel`.
3. **Enriquecimento**
   - Calcula `dias_sem_movimentacao`.
4. **Classificação**
   - Regras:
     - >30 dias: alerta baixo
     - >60 dias: alerta médio
     - >90 dias: alerta alto
   - Ajuste por prioridade:
     - Alta prioridade aumenta severidade.
5. **Ações sugeridas**
   - Exemplo:
     - 30–59 dias: revisar autos
     - 60–89 dias: cobrar andamento/contato com cartório
     - 90+ dias: peticionar impulso processual
6. **Saída**
   - Gera `output/processos_parados.csv`.
   - Envia resumo por e-mail.
   - Exibe dashboard com filtros.

---

## 4) Exemplo de código inicial funcional

Arquivo: `scripts/monitor_processos.py`

### Como executar
```bash
python scripts/monitor_processos.py --input data/processos.csv --output output/processos_parados.csv
```

### Formato esperado do CSV de entrada
Colunas mínimas:
- `id_processo`
- `numero_processo`
- `tipo_processo`
- `prioridade` (baixa, media, alta)
- `ultima_movimentacao` (YYYY-MM-DD)
- `responsavel`

### Exemplo rápido de CSV
```csv
id_processo,numero_processo,tipo_processo,prioridade,ultima_movimentacao,responsavel
1,0001234-56.2024.8.26.0100,Cível,alta,2025-12-01,Ana
2,0009988-11.2023.8.26.0100,Trabalhista,media,2026-02-01,Carlos
```

---

## 5) Melhorias futuras

1. **Integração oficial com API LinkLei**
   - Token OAuth, paginação e retries.
2. **Mecanismo de deduplicação e histórico**
   - Snapshot diário para medir envelhecimento.
3. **Score de risco**
   - Combinar valor da causa, fase processual e SLA interno.
4. **Recomendação assistida por IA**
   - Sugestão de minuta ou checklist por classe processual.
5. **Observabilidade**
   - Logs estruturados + métricas de execução (tempo, falhas, volume).

---

## 6) Limitações e riscos

1. **Dependência da qualidade dos dados**
   - Datas inválidas ou campos vazios comprometem ranking.
2. **Scraping é frágil**
   - Mudanças de layout quebram coletores.
3. **E-mail pode ter falso negativo**
   - Entrega bloqueada/spam sem monitoramento de bounce.
4. **Regras fixas podem gerar ruído**
   - Necessário calibrar thresholds por área jurídica.
5. **Conformidade LGPD**
   - Criptografia em repouso e controle de acesso são mandatórios.

---

## Abordagens alternativas (comparativo breve)

### A) Python + CSV + SQLite (recomendada para começar)
- **Prós**: simples, barato, rápido para colocar em produção.
- **Contras**: menos colaborativo em grande escala.

### B) Node.js + PostgreSQL + Dashboard web customizado
- **Prós**: ótima integração web e APIs em tempo real.
- **Contras**: maior esforço inicial.

### C) BI-first (Power BI/Metabase) + ETL mínimo
- **Prós**: visualização forte com pouco código.
- **Contras**: lógica de ação automática e alertas tende a ficar limitada.

**Recomendação prática:** iniciar com A e evoluir modularmente para B conforme volume/processos/responsáveis aumentarem.
