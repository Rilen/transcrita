# Infraestrutura operacional — gateway, rede dedicada e firewall

Documento de referência da arquitetura implantada nas missões TRANSCRITA-016C a 016F.
Não contém segredos nem configurações de outros projetos.

## Topologia

```
Clientes (LAN 10.0.0.0/24 + institucionais 192.168.x via upstream)
   │ HTTP :3005 publicado em 0.0.0.0 pelo container nginx-3005
   ▼
nginx-3005 (nginx:alpine, restart=unless-stopped, container manual)
   │ eth3 — rede dedicada transcrita-net (10.99.0.0/24)
   │ origem efetiva: 10.99.0.2
   │ proxy_pass http://10.99.0.1:18765  (location ^~ /transcrita/)
   ▼
HOST — transcrita.service (systemd, user transcrita)
   bind 10.99.0.1:18765   ← IP do host na bridge br-transcrita
```

- O backend executa **no host** via systemd, fora de containers.
- O gateway `nginx-3005` é **compartilhado** com outros projetos; somente o
  `location ^~ /transcrita/` foi alterado. Demais rotas não fazem parte deste
  documento e não devem ser modificadas por missões do Transcrita.

## Endereços e interfaces

| Item | Valor |
|---|---|
| Rede Docker dedicada | `transcrita-net` → bridge `br-transcrita`, subnet `10.99.0.0/24` |
| Endpoint do host | `10.99.0.1` |
| Endpoint do nginx | `10.99.0.2` (atribuído via `docker network connect --ip`) |
| Bind do serviço | `10.99.0.1:18765` (`TRANSCRITA_HOST` no unit) |
| Root path | `/transcrita` (`TRANSCRITA_ROOT_PATH`) |

## Fonte persistente do gateway

- Diretório-fonte: `/opt/nginx-3005-gateway-config/` (compartilhado; contém
  também rotas de outros projetos — **não versionar o arquivo inteiro**).
- Bloco do Transcrita: `location ^~ /transcrita/` em
  `conf.d/default.conf` → `proxy_pass http://10.99.0.1:18765`.
- Aplicação ao container: `/opt/nginx-3005-gateway-config/apply.sh`
  (`docker cp` de todos os arquivos + `nginx -t` + reload).
- O container não possui volumes; a configuração efetiva vive no filesystem do
  container e é **reidratada a partir de `/opt/nginx-3005-gateway-config/`**
  por `apply.sh` ou por recriação manual. Manter os dois lados sincronizados
  é obrigatório — divergência faz o `apply.sh` reverter o `proxy_pass`.

## Firewall

- Script idempotente: `/usr/local/sbin/transcrita-fw.sh` (`apply|remove|status`).
- Unit: `transcrita-firewall.service` (oneshot, `RemainAfterExit=yes`,
  `Before=transcrita.service docker.service`, `WantedBy=multi-user.target`).
- Cadeia `TRANSCRITA_ACCESS` (filter/INPUT, somente `--dport 18765`):
  1. `RETURN` se `iif=br-transcrita` e `src=10.99.0.2`;
  2. `RETURN` se `iif=lo`;
  3. `REJECT --reject-with tcp-reset` para todo o resto.
- Match por **interface de ingresso** (anti-spoof): pacote forjado de outro
  container chega por `docker0`, não por `br-transcrita`.
- Não altera `nat`, `FORWARD`, `DOCKER-USER` ou outras portas.

## Dependências systemd

- `transcrita-firewall.service` — `DefaultDependencies=no`,
  `After=local-fs.target`, `Before=transcrita.service docker.service`.
- `transcrita.service` — `After=network-online.target`, `Restart=always`,
  limites `MemoryMax=8G`/`CPUQuota=400%`.
- Drop-in `/etc/systemd/system/transcrita.service.d/firewall.conf`
  (TRANSCRITA-016F): `Requires=transcrita-firewall.service` +
  `After=transcrita-firewall.service` — o backend **não inicia** se a
  política de firewall falhar (fail-closed).

## Recuperação após recriação do nginx-3005

`docker network connect` **não é persistente**: recriar o container perde o
endpoint em `transcrita-net`, o IP `10.99.0.2` e a configuração interna do
nginx. Procedimento de recuperação (executar somente com autorização):

```bash
# 1. Reconectar à rede dedicada com IP fixo
docker network connect --ip 10.99.0.2 transcrita-net nginx-3005

# 2. Reidratar a configuração persistente (inclui proxy_pass correto)
/opt/nginx-3005-gateway-config/apply.sh nginx-3005

# 3. Validar
docker exec nginx-3005 nginx -t
curl -fsS http://127.0.0.1:3005/transcrita/api/health
```

O endpoint `transcrita-net` e o IP `10.99.0.2` **não** são recriados
automaticamente — este é o principal risco residual (ver abaixo).

## Rollback

- Rollback completo da migração 016E: `/root/transcrita-016e-rollback.sh`
  (fora do repositório; restaura unit, conf do nginx e firewall IP-based).
  Backups relacionados em `/root/*.bak-016e` e `/root/iptables-pre-016e.rules`.
- Rollback do drop-in de firewall:
  `rm /etc/systemd/system/transcrita.service.d/firewall.conf && systemctl daemon-reload`.
- Rollback da sincronização do `proxy_pass`: restaurar
  `/root/nginx-default.conf.bak-016f` sobre
  `/opt/nginx-3005-gateway-config/conf.d/default.conf` (somente se o backend
  voltar a escutar em `10.0.1.1`).

## Riscos residuais

- **R1:** recriação manual do `nginx-3005` perde o endpoint `transcrita-net`
  e o IP `10.99.0.2` — requer o procedimento de recuperação acima. Não há
  unit de autocura hoje (candidato: `transcrita-net-ensure.service`).
- **R2:** se `transcrita-firewall.service` falhar no boot, `transcrita.service`
  não sobe (fail-closed por `Requires=`); a porta fica inacessível até correção
  — comportamento intencional.
- **R3:** borda `:3005` permanece aberta a qualquer origem que roteie até o
  host; autenticação/TLS/rate limiting estão fora do escopo atual.
- **R4:** `fake0` (dummy, `1.2.3.4/24`) é inócuo mas deve ser removido em
  missão de higiene de rede.
- **R5:** backups operacionais residem em `/root/` — fora de qualquer
  mecanismo de backup gerenciado; a fonte de verdade versionável é este
  repositório (somente para artefatos do Transcrita).
