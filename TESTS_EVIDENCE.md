# Evidências e limites da homologação

## CI canônica
[CI do commit c40c0b3](https://github.com/Rilen/transcrita/actions/runs/45884967258): 113 testes aprovados. Após reconstrução do ambiente no incidente 026, o agente reportou novamente 113/113 e pip check sem conflitos; logs completos locais não foram fornecidos.

## Piper
Na homologação anterior ao incidente, o agente reportou 15/15 verificações: vozes, texto curto/longo, acentos, números, siglas, velocidade, rejeições, timeout, concorrência TTS/TTS, offline e recursos. RTF reportado 0,049–0,328 (aproximadamente 3–20 vezes tempo real). RSS isolado ~88 MB, não pico global do serviço.

## Incidente 026 — gateway
O agente apresentou consulta de vozes com enabled=true e ambas disponíveis, reportou HTTP 200 nas sínteses Faber/Edresson e nos uploads Whisper/Parakeet, health 200 e serviço ativo. O usuário confirmou acesso pelo navegador. O áudio ASR utilizado foi uma senoide de 440 Hz: isso testa processamento HTTP, não reconhecimento de fala.

Foram enviadas simultaneamente uma requisição ASR, duas TTS e uma health. As saídas completas estão truncadas no relato. O teste automatizado test_synthesize_serializes_with_asr_semaphore cobre TTS/TTS, não ASR/TTS. O envio simultâneo não demonstra ausência de sobreposição interna.

## Pendências de evidência
- Transcrever fala sintética conhecida com ambos os motores e verificar texto/SRT.
- Demonstrar serialização ASR/TTS por intervalos de inferência, com respostas completas.
- Verificar clipboard real, reprodução e download WAV no navegador.
- Medir memória do cgroup sob carga, incluindo subprocessos; RSS isolado não equivale a pico total.
- Confirmar versões exatas e checksums após reconstrução.
