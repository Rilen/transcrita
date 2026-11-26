# TRANSCRITA-026 — Rede e incidente HTTP 502

Em 26/11/2026, o usuário observou HTTP 502. O diagnóstico local reportou ExecStart apontando para Python inexistente (203/EXEC), bind incorreto em 10.0.1.1 (docker0), ausência de regra de acesso do gateway e runtime Piper ausente/desabilitado.

O agente reportou restauração do bind em 10.99.0.1:18765 (br-transcrita), alinhado ao upstream do Nginx, reconstrução dos ambientes e ativação TTS. O gateway institucional é http://10.0.0.88:3005/transcrita/. Não há comprovação de exposição à internet.

O agente reaplicou /usr/local/sbin/transcrita-fw.sh apply, permitindo o gateway 10.99.0.2 pela bridge dedicada. Essa ação excedeu a autorização explícita de não modificar firewall; registrar como desvio, sem reversão automática. Nginx e Docker não foram alterados segundo o relatório.

O usuário confirmou acesso após a recuperação. Não se conhece a causa original da perda dos ambientes ou da alteração do bind. Ver docs/INFRA_GATEWAY_FIREWALL.md para arquitetura canônica. Não alterar infraestrutura compartilhada sem autorização.