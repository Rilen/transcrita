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

## Piper TTS Performance (RTF - Rato de Transcrição Frente a Tempo Real)

| Cenário | RTF Observado | Comentário |
|---|---|---|
| Texto curto | ~0.314 | ~3x mais rápido que tempo real |
| Relatório técnico | ~0.132 | ~8x mais rápido |
| Acentos especiais | ~0.145 | ~7x mais rápido |
| Datas/valores monetários | ~0.117 | ~9x mais rápido |
| Siglas/abreviações | ~0.153 | ~7x mais rápido |
| Texto longo (1.200 chars) | ~0.049 | ~20x mais rápido |
| Voz Edresson | ~0.324 | ~3x mais rápido |

## Whisper Transcription Performance
- Variável dependendo do tamanho do áudio e do modelo `base`
- RTF calculado como `tempo_de_síntese / duração_do_audio`
- Registrado em log via `transcrita.core.logger.info("transcricao_concluida", ...)`

## Memória de Cache de Modelo
- `HF_HOME=/var/lib/transcrita/models`
- `XDG_CACHE_HOME=/var/lib/transcrita/models`
- Modelos carregados uma vez e reutilizados via cache em `transcrita.core.Transcriber.model` property
- Nenhum vazamento de memória detectado em 113 testes consecutivos