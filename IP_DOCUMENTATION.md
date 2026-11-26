# TRANSCRITA-025 — Documentação de Endereço e Divulgação de IP

## Endereço Interno do Serviço
- **Configuração systemd:** `Environment=TRANSCRITA_HOST=10.0.1.1`, `Environment=TRANSCRITA_PORT=18765`
- **Endereço efetivo de escuta:** `10.0.1.1:18765`
- **WorkingDirectory do service:** `/opt/transcrita`
- **User/Group:** `transcrita`

## Mapeamento Externo (Gateway/Reverse Proxy)
- **URL pública:** `http://10.0.0.88:3005/transcrita/`
- **Relação:** Acesso externo via infraestrutura de gateway/reverse proxy (nginx)
- **Observação:** Não foram realizadas modificações em Nginx, Docker ou firewall durante esta operação

## Divergência de IP (10.99.0.1 vs 10.0.1.1)
- O serviço foi visto escutando em `127.0.0.1:18799` em 18/11/2026 (processo anterior, sem inferências ativas)
- Configuração corrente em systemd: `10.0.1.1:18765`
- Não há alterações de rede ou de firewall registradas

## Última Configuração de Porta
- Porta `18765` ativa no service atual (reiniciado 26/11/2026 19:57 UTC)
- Porta `18799` vista em logs Nov 18 (processo em `/tmp/venv-pk018/`)