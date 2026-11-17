# Checklist de publicação protegida (Whisper + multimotor com flag off)

## Pré-publicação
- [ ] CI de testes aprovada no SHA a publicar (GitHub Actions).
- [ ] GitGuardian aprovado; nenhum segredo no diff.
- [ ] `TRANSCRITA_ENABLE_PARAKEET=false` confirmado (default; ausente no systemd).
- [ ] Instalação apenas com `[web]` (sem `[parakeet]`).
- [ ] Snapshot/backup do checkout e do unit systemd; SHA atual registrado.
- [ ] `pip freeze` registrado; espaço em disco e limites conferidos.
- [ ] Rollback ensaiado (reverter SHA + reinstall + restart).

## Publicação
1. `git fetch && git switch main && git merge --ff-only origin/main` (SHA aprovado).
2. `pip install -e ".[web]"`.
3. `systemctl restart transcrita.service` (somente Transcrita).
4. Verificar `systemctl status` e journal (sem tracebacks).

## Pós-publicação
- [ ] Health direto (`10.0.1.1:18765`) e via gateway (`:3005/transcrita/`).
- [ ] Frontend 200 e seletor de motor exibindo Whisper; Parakeet indisponível.
- [ ] Upload e transcrição Whisper (áudio sintético/autorizado) + SSE + cancelamento.
- [ ] TXT/SRT gerados e válidos.
- [ ] `/api/engines` retorna disponibilidade coerente.
- [ ] CPU/RAM do serviço e logs.
- [ ] Regressão: gateway, FROC Portal/Mapa, Consulta360.

## Rollback
- Funcional: manter/forçar `TRANSCRITA_ENABLE_PARAKEET=false` + restart.
- Código: `git checkout <sha_anterior>` + `pip install -e ".[web]"` + restart.
- Nginx/systemd: restaurar backups previamente registrados.
