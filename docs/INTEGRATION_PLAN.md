# Plano de integração da cadeia multimotor (#2–#7)

## Cadeia atual
`main` → #2 (`exp/multi-asr-cpu-poc`) → #3 (`…validation-004`) → #4 (`…timestamps-005`)
→ #5 (`…integrity-006`) → #6 (`feat/transcrita-007-multiengine`) → #7 (`fix/transcrita-009-audit-remediation`).

Conteúdo por PR:
- **#2–#5**: experimentos (`experiments/multi_asr`), testes e relatórios; **sem** alteração de comportamento de produto.
- **#6**: integração multimotor no produto, protegida por `TRANSCRITA_ENABLE_PARAKEET=false`.
- **#7**: saneamento (CI de testes, upload chunked, sanitização, UI, temporários).

## Alternativas

### A — Merge sequencial (#2 → #7)
- Vantagens: rastreabilidade por missão, diffs pequenos, rollback por PR, evidências preservadas.
- Riscos: exige respeitar a ordem e manter as branches-base até o fim; mais operações de merge.
- Conflitos esperados: baixos (cadeia linear; #6 concentra o produto).

### B — Integração consolidada (um único conjunto)
- Vantagens: menos operações; conflito resolvido uma vez.
- Riscos: perde granularidade de evidências/rollback; diff grande; dificulta auditoria por missão.

## Recomendação: **Alternativa A**
1. Proteger `main` (revisão obrigatória + check `testes (Python 3.12, CPU)` obrigatório + sem force push).
2. Integrar na ordem #2→#7; após cada merge, aguardar CI e revalidar a base da PR seguinte.
3. Manter as branches experimentais até o merge de #7; depois removê-las (sem reescrever histórico).
4. Publicar em `main` com `[web]` apenas e flag desligada.
5. Piloto Parakeet separado (ver `docs/PARAKEET_PILOT.md`).

## Rollback
Reverter `main` para o merge anterior (revert do merge commit) ou para `95bdf68`; reaplicar
`pip install -e ".[web]"` e reiniciar o serviço. Flag desligada é rollback funcional imediato.
