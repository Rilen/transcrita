# Recuperação e rollback — TRANSCRITA-026

Baseline recuperada reportada: `c40c0b30d2d0318cdf8b68d36d80974f93a7080e`. Restaurar esse SHA é recuperação da versão atual, não rollback para versão anterior.

A versão anterior reportada como operacional na missão 020 foi c8297a4 (ASR Whisper/Parakeet, sem Piper). Antes de qualquer rollback, verificar commit, dependências, configuração compatível e autorização. O merge local a43dd41 não é baseline homologada.

## Recuperação da baseline atual
Preservar checkout, modelos, caches e configurações. Verificar /opt/transcrita/.venv e .venv-piper, Python 3.12, dependências compatíveis, pip check, suíte completa e permissões do usuário de serviço. Bind 10.99.0.1:18765, root path /transcrita, limites 8G/400%, Parakeet e Piper habilitados conforme configuração recuperada. Não restaurar cegamente backups da configuração defeituosa.

O agente reportou backups datados 20261126-224401-transcrita-026 da unit e dos drop-ins firewall.conf e parakeet.conf. Sua integridade e conteúdo não foram inspecionados pelo coordenador.

Qualquer recuperação futura exige diagnóstico, preservação do estado, validação da unit, autorização e inicialização controlada somente do serviço Transcrita. Verificar HTTP pelo gateway, motores, vozes e transcrição com fala. TestClient não comprova disponibilidade publicada. Não alterar Nginx, Docker ou firewall sem autorização específica; não reiniciar em loop. Nenhum rollback foi executado nesta revisão.