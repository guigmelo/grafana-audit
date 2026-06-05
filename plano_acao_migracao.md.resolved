# Plano de Ação — Migração de Permissões Nominais → Teams (ServiceNow)

## Visão Geral do Fluxo

```mermaid
graph TD
    A["1. Auditoria<br/>audit_permissions.py"] --> B["2. De-Para Manual<br/>CSV + ServiceNow"]
    B --> C["3. Criar/Mapear Teams<br/>no Grafana"]
    C --> D["4. Aplicar Permissões<br/>por Team"]
    D --> E["5. Remover Permissões<br/>Nominais"]

    style A fill:#4CAF50,color:#fff
    style B fill:#FF9800,color:#fff
    style C fill:#2196F3,color:#fff
    style D fill:#9C27B0,color:#fff
    style E fill:#F44336,color:#fff
```

---

## Fase 1 — Auditoria ✅ (Já feita)

O script `audit_permissions.py` já gerou o `inventario_grafana.csv` com 6 não conformidades.

---

## Fase 2 — De-Para Manual (ServiceNow → Team Grafana)

### O que fazer

1. Pegar o CSV gerado (`inventario_grafana.csv`)
2. Para cada **e-mail de usuário** no CSV, consultar no **ServiceNow** qual é o **Grupo de Atribuição** desse usuário
3. Adicionar uma coluna `Grupo SNOW` ao CSV manualmente (ou via export do SNOW)
4. Definir qual **Team do Grafana** corresponde a cada Grupo do SNOW

### Formato sugerido para o arquivo de-para

Criar um arquivo `depara_snow_teams.csv` com o mapeamento:

```
E-mail do Usuário;Grupo SNOW;Team Grafana;Nível de Permissão
user01@teste.local;Infra-Linux;Team-Infra;Editor
user02@teste.local;App-Java;Team-Aplicacoes;Editor
```

> [!IMPORTANT]
> **Este é o passo manual mais crítico.** Você precisa:
> - Exportar do ServiceNow a lista de usuários e seus grupos de atribuição
> - Cruzar com os e-mails do `inventario_grafana.csv`
> - Decidir o nome do Team Grafana para cada grupo SNOW
> - Usuários do **mesmo grupo SNOW** devem ir para o **mesmo Team Grafana**

### Dica: Agrupar por similaridade

Olhando o CSV atual, podemos agrupar:

| E-mail | Pastas/Dashs com acesso | Grupo SNOW (preencher) | Team Grafana (definir) |
|---|---|---|---|
| user01@teste.local | Folder2, Pasta-Teste-A, Dashboard-Teste-B, New dashboard | ? | ? |
| user02@teste.local | Folder2, Dashboard-Teste-B | ? | ? |

Se ambos pertencem ao mesmo grupo no SNOW → mesmo Team no Grafana.

---

## Fase 3 — Criar/Mapear Teams no Grafana

Depois de definir o de-para, precisamos:

1. **Verificar quais Teams já existem** no Grafana
2. **Criar os Teams que faltam**
3. **Adicionar os usuários** aos Teams correspondentes

> [!NOTE]
> Posso criar um script `create_teams.py` que lê o `depara_snow_teams.csv` e automatiza essas 3 ações via API:
> - `GET /api/teams/search` — listar teams existentes
> - `POST /api/teams` — criar team
> - `POST /api/teams/{teamId}/members` — adicionar membro ao team

---

## Fase 4 — Aplicar Permissões por Team

Para cada recurso (Pasta ou Dashboard) no inventário:

1. Consultar as permissões atuais
2. Adicionar a permissão do **Team** com o mesmo nível (Editor/Viewer/Admin)
3. Manter as permissões de roles organizacionais intactas

> [!NOTE]
> Posso criar um script `apply_team_permissions.py` que lê o de-para e aplica as permissões automaticamente via:
> - `POST /api/folders/{uid}/permissions` 
> - `POST /api/dashboards/uid/{uid}/permissions`

---

## Fase 5 — Remover Permissões Nominais

**Somente após validar** que os Teams têm acesso correto:

1. Para cada recurso no inventário, remover as entradas com `userId > 0`
2. Manter apenas permissões de Teams e Roles

> [!WARNING]
> **Execute esta fase com cautela!** Recomendo:
> - Fazer um backup das permissões atuais antes (o próprio `inventario_grafana.csv` serve)
> - Remover um recurso por vez e validar
> - Ter o script de rollback pronto (re-aplicar permissões nominais do CSV)

> [!NOTE]
> Posso criar um script `remove_nominal_permissions.py` que faz isso automaticamente, preservando permissões de Teams e Roles.

---

## Resumo dos Scripts Necessários

| # | Script | Status | Descrição |
|---|---|---|---|
| 1 | `audit_permissions.py` | ✅ Pronto | Gera inventário CSV |
| 2 | `depara_snow_teams.csv` | 📝 Manual | De-para preenchido por você |
| 3 | `create_teams.py` | 🔧 A criar | Cria Teams e adiciona membros |
| 4 | `apply_team_permissions.py` | 🔧 A criar | Aplica permissões por Team |
| 5 | `remove_nominal_permissions.py` | 🔧 A criar | Remove permissões nominais |

---

## Ordem de Execução Recomendada

```
1. python audit_permissions.py           # Gerar inventário (✅ feito)
2. [MANUAL] Preencher depara_snow_teams.csv  # Cruzar com ServiceNow
3. python create_teams.py                # Criar Teams + adicionar membros
4. python apply_team_permissions.py      # Dar permissões aos Teams
5. [VALIDAR] Conferir no Grafana UI      # Verificar se Teams têm acesso
6. python remove_nominal_permissions.py  # Remover permissões nominais
7. python audit_permissions.py           # Re-auditar — deve retornar 0 não conformidades
```

## Próximos Passos

> [!IMPORTANT]
> **O que preciso de você:**
> 1. Preencher o `depara_snow_teams.csv` com os dados do ServiceNow
> 2. Me dizer quais scripts (3, 4, 5) quer que eu crie
> 3. Confirmar se os Teams já existem no Grafana ou se precisam ser criados
