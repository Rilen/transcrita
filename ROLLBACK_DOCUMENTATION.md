# TRANSCRITA-025 — Rollback Documentado

## Último SHA Operacional Homologado
- **SHA:** `c40c0b30d2d0318cdf8b68d36d80974f93a7080e`
- **Branch:** `main` (HEAD detached at canonical main)
- **Commit message:** `Merge pull request #16 from Rilen/feat/transcrita-022-piper-tts`

## Como Executar Rollback

### Passo 1: Voltar o checkout ao SHA canônico
```bash
cd /opt/transcrita
git checkout c40c0b3
```
- Deixa o HEAD em estado detached na main canônica
- Código funcional restaurado à versão aprovada (113/113 testes)
- Service systemd apontando para a versão correta

### Passo 2: Reiniciar o Service
```bash
systemctl restart transcrita.service
```
- Novo processo PID será iniciado com a versão canônica
- Aguardar startup (aprox. 2-3 segundos)
- Verificar: `systemctl status transcrita.service`

### Passo 3: Verificar operação
```bash
# Health check
.venv/bin/python -c 'import sys; sys.path.insert(0, "/opt/transcrita"); from fastapi.testclient import TestClient; from transcrita import web; c = TestClient(web.app); r = c.get("/api/health"); print(r.status_code)'

# Deve retornar 200 OK
```

## Configurações Essenciais para Restauração

| Configuração | Valor | Onde está definido |
|---|---|---|
| `TRANSCRITA_ENABLE_TTS` | `true` | `/etc/systemd/system/transcrita.service` e env vars |
| `TRANSCRITA_PIPER_BIN` | `/opt/transcrita/.venv-piper/bin/piper` | `/etc/systemd/system/transcrita.service` |
| `TRANSCRITA_PIPER_MODELS_DIR` | `/var/lib/transcrita/models/piper/pt_BR/` | `/etc/systemd/system/transcrita.service` |
| `TRANSCRITA_HOST` | `10.0.1.1` | `/etc/systemd/system/transcrita.service` |
| `TRANSCRITA_PORT` | `18765` | `/etc/systemd/system/transcrita.service` |
| `TRANSCRITA_ROOT_PATH` | `/transcrita` | `/etc/systemd/system/transcrita.service` |
| Modelos ONNX | `/var/lib/transcrita/models/piper/pt_BR/` | Sistema de arquivos |
| Checksums SHA-256 | Confirmados em `MODEL_CHECKSUMS.md` | Este documento |

## Estado Preservado para Rollback

### No repositório git:
- **Reflog preserva:** `a43dd41` (merge main into feat/transcrita-022-piper-tts), `0d2c4c2` (TTS test fixes)
- **Branch `feat/transcrita-022-piper-tts`:** Mantida no remote `origin/feat/transcrita-022-piper-tts` para referência
- **Worktree `docs/transcrita-025-operational-consolidation`:** Todas as alterações documentais

### No sistema de arquivos:
- Modelos Piper em `/var/lib/transcrita/models/piper/pt_BR/` (com checksums válidos)
- Binário Piper em `/opt/transcrita/.venv-piper/bin/piper`
- Configurações systemd em `/etc/systemd/system/transcrita.service` e `.d/`
- Sem alterações em Nginx, Docker ou firewall

### O que NÃO foi alterado:
- Código funcional (nenhum `reset --hard`, `git clean`, force push ou reversão automática)
- Configurações operacionais (host, porta, root-path do systemd)
- Nginx, Docker, firewall ou outros projetos
- Segredos ou dados pessoais

## Cenários de Rollback

### Cenário 1: Problema após deploy canonical
```bash
# Se após o alinhamento à main surgir algum problema:
git checkout c40c0b3          # volta ao SHA canônico
systemctl restart transcrita.service  # reinicia service
```

### Cenário 2: Voltar à versão anterior do feature branch
```bash
# Se precisar voltar ao estado antes do merge à main:
git checkout feat/transcrita-022-piper-tts  # ou git log --oneline para histórico
```
- Estado: `a43dd41` (merge main into feat/transcrita-022-piper-tts)
- Contém alterações em `tests/test_tts.py` e `CHANGELOG.md`

### Cenário 3: Rollback completo para pré-022
```bash
# Se precisar de estado anterior à missão 022:
git log --oneline --all | tail -20
# Para versões antigas conforme necessidade
```

## Nota Importante
- **Não executar `git reset --hard`, `git clean -fdx` ou force push**
- **Não modificar Nginx, Docker, firewall**
- **As alterações documentais estão isoladas no worktree `docs/transcrita-025-operational-consolidation`**
- O checkout operacional `/opt/transcrita` permanecerá na main canônica `c40c0b3` após esta operação