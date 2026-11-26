# TRANSCRITA-025 — Limites Efetivos de CPU e Memória

## Configuração systemd
```ini
[Service]
MemoryMax=8G
CPUQuota=400%
LimitNOFILE=65536
```

## Observados em Operação

| Métrica | Valor Observado | Comentário |
|---|---|---|
| **RSS do processo principal** | ~45-46 MB | Em operação estável (transcrita.service ativo) |
| **RSS máxima (homologation isolada)** | ~88 MB | Execução do `homologate_piper.py` em ambiente isolado |
| **CPU Quota** | 400% | Limite configurado no systemd |
| **CPU tempo usuário** | ~3.76s | Medido em `resource.getrusage(resource.RUSAGE_SELF)` durante homologation |
| **CPU tempo sistema** | ~0.10s | Medido em `resource.getrusage(resource.RUSAGE_SELF)` durante homologation |

## Intervalos de RTF Observados

| Cenário | RTF Observado | Comentário |
|---|---|---|
| Texto curto | ~0.314 | ~3x mais rápido que tempo real (1/0,314 ≈ 3,18x) |
| Relatório técnico | ~0.132 | ~8x mais rápido (1/0,132 ≈ 7,58x) |
| Acentos especiais | ~0.145 | ~7x mais rápido (1/0,145 ≈ 6,90x) |
| Datas/valores monetários | ~0.117 | ~9x mais rápido (1/0,117 ≈ 8,55x) |
| Siglas/abreviações | ~0.153 | ~7x mais rápido (1/0,153 ≈ 6,54x) |
| Texto longo (1.200 chars) | ~0.049 | ~20x mais rápido (1/0,049 ≈ 20,41x) |
| Voz Edresson | ~0.324 | ~3x mais rápido que tempo real (1/0,324 ≈ 3,09x) |

**Intervalo geral de RTF:** 0,049 a 0,328 → Aproximadamente 3 a 20 vezes mais rápido que tempo real.