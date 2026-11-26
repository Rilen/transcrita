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

## TRANSCRITA-027 — homologação complementar reportada

Piper Faber: HTTP 200, 4,16 s, WAV PCM 16-bit mono 22050 Hz, 197676 bytes. Frase: “O sistema Transcrita realiza transcrição e síntese de voz em português.” Whisper tiny: HTTP 200, 1,32 s, “O sistema transcrita realiza a transcrição e sintese de voz em português.” SRT 0–6 s. Parakeet pt-br-int8: HTTP 200, 18 s, “O sistema transcrita realiza transcrição e síntese de voz em português.” SRT 0,006–4,470 s. O término Whisper excede a duração aproximada de 4,48 s inferida do tamanho/formato WAV; não afirmar precisão temporal. Não extrapolar desempenho a outros áudios.

ASR, duas TTS e health concorrentes: HTTP 200 reportado; sem intervalos internos para comprovar serialização. PID 3643558, NRestarts=0, bind 10.99.0.1:18765. MemoryCurrent=1421074432, MemoryPeak=1767849984, MemoryMax=8589934592 bytes, CPUQuota=400%. Pico observado ~20,6% do limite. Arquivo temporário removido segundo agente.

Versões reportadas ASR: faster-whisper 1.2.1, fastapi 0.165.0, uvicorn 0.54.0, onnx-asr 0.12.0, soundfile 0.14.0, cffi 2.1.1, python-multipart 0.0.34, av 19.0.2, ctranslate2 4.9.1, onnxruntime 1.32.0, tokenizers 0.23.3, huggingface-hub 2.5.0. Piper: piper-tts 1.8.0, onnxruntime 1.32.0, numpy 2.5.5. Inventário não é lockfile reproduzível. Quatro arquivos Piper presentes segundo agente, sem novos hashes apresentados. Nenhuma mudança de configuração ou reinício reportado. Homologação funcional aceita com ressalvas; verificação de hashes, precisão SRT e instrumentação de serialização ficam como melhorias futuras.
