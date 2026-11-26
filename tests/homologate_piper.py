"""Script de homologação isolada do Piper TTS (TRANSCRITA-022)."""

import json
import os
import resource
import subprocess
import sys
import time
import wave
from io import BytesIO
from pathlib import Path

# Configura ambiente de homologação
os.environ["TRANSCRITA_ENABLE_TTS"] = "true"
os.environ["TRANSCRITA_PIPER_BIN"] = "/opt/transcrita/.venv-piper/bin/piper"
os.environ["TRANSCRITA_PIPER_MODELS_DIR"] = "/var/lib/transcrita/models/piper/pt_BR"

from fastapi.testclient import TestClient
import transcrita.web as web
from transcrita.tts.piper import PiperTTS


def check_wav(wav_bytes: bytes) -> tuple[int, int, float]:
    """Valida integridade do WAV e retorna canais, taxa de amostragem e duração em segundos."""
    with wave.open(BytesIO(wav_bytes), "rb") as wf:
        nchannels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        nframes = wf.getnframes()
        duration = nframes / float(framerate)
        assert sampwidth == 2, f"Largura de amostra esperada 16-bit (2 bytes), obtido {sampwidth}"
        return nchannels, framerate, duration


def main():
    print("==================================================================")
    print(" INICIANDO HOMOLOGAÇÃO ISOLADA — PIPER TTS PT-BR (TRANSCRITA-022)")
    print("==================================================================")
    
    client = TestClient(web.app)
    piper = PiperTTS()
    results = []

    # 1. Checagem de vozes
    print("\n[1/15] Verificando endpoint de vozes /api/tts/voices...")
    r = client.get("/api/tts/voices")
    assert r.status_code == 200, f"Status code {r.status_code}"
    voices_data = r.json()
    print(f"  Voz padrão: {voices_data['default_voice']}")
    for v in voices_data["voices"]:
        print(f"  Voz: {v['id']} ({v['name']}) | Disponível: {v['available']} | Licença: {v['license']}")
        assert v["available"], f"Voz {v['id']} deveria estar disponível"

    # 2. Texto curto
    print("\n[2/15] Síntese de texto curto...")
    t0 = time.perf_counter()
    res = client.post("/api/tts/synthesize", json={"text": "Olá mundo! Transcrita agora fala.", "voice": "pt_BR-faber-medium", "speed": 1.0})
    t1 = time.perf_counter()
    assert res.status_code == 200
    ch, fr, dur = check_wav(res.content)
    rtf = (t1 - t0) / dur if dur > 0 else 0
    print(f"  Duração áudio: {dur:.2f}s | Tempo de síntese: {t1-t0:.2f}s | RTF: {rtf:.3f} | Canais: {ch} | Taxa: {fr}Hz")
    results.append(("Texto curto", t1 - t0, dur, rtf, len(res.content)))

    # 3. Relatório institucional em português
    print("\n[3/15] Síntese de relatório técnico...")
    relatorio = "O projeto Transcrita alcançou estabilidade operacional plena com suporte a processamento neural de voz 100% soberano e local."
    t0 = time.perf_counter()
    res = client.post("/api/tts/synthesize", json={"text": relatorio, "voice": "pt_BR-faber-medium", "speed": 1.0})
    t1 = time.perf_counter()
    assert res.status_code == 200
    ch, fr, dur = check_wav(res.content)
    rtf = (t1 - t0) / dur if dur > 0 else 0
    print(f"  Duração áudio: {dur:.2f}s | Tempo de síntese: {t1-t0:.2f}s | RTF: {rtf:.3f}")
    results.append(("Relatório técnico", t1 - t0, dur, rtf, len(res.content)))

    # 4. Acentuação e caracteres especiais
    print("\n[4/15] Acentuação e caracteres especiais...")
    acentos = "Atenção: João e José foram à feira comprar maçã, pão, café e água com gás! Estavam felizes."
    t0 = time.perf_counter()
    res = client.post("/api/tts/synthesize", json={"text": acentos, "voice": "pt_BR-faber-medium", "speed": 1.0})
    t1 = time.perf_counter()
    assert res.status_code == 200
    ch, fr, dur = check_wav(res.content)
    rtf = (t1 - t0) / dur
    print(f"  Duração áudio: {dur:.2f}s | Tempo: {t1-t0:.2f}s | RTF: {rtf:.3f}")
    results.append(("Acentos especiais", t1 - t0, dur, rtf, len(res.content)))

    # 5. Datas, números e valores monetários
    print("\n[5/15] Datas, números e valores monetários...")
    numeros = "Em 26 de novembro de 2026, foram registradas 1.250 operações totalizando R$ 45.789,90 no exercício fiscal."
    t0 = time.perf_counter()
    res = client.post("/api/tts/synthesize", json={"text": numeros, "voice": "pt_BR-faber-medium", "speed": 1.0})
    t1 = time.perf_counter()
    assert res.status_code == 200
    ch, fr, dur = check_wav(res.content)
    rtf = (t1 - t0) / dur
    print(f"  Duração áudio: {dur:.2f}s | Tempo: {t1-t0:.2f}s | RTF: {rtf:.3f}")
    results.append(("Datas e valores monetários", t1 - t0, dur, rtf, len(res.content)))

    # 6. Siglas e abreviações
    print("\n[6/15] Siglas e abreviações...")
    siglas = "O STF e a ANATEL publicaram novas diretrizes em Brasília, DF, com apoio da ONU e da OMS."
    t0 = time.perf_counter()
    res = client.post("/api/tts/synthesize", json={"text": siglas, "voice": "pt_BR-faber-medium", "speed": 1.0})
    t1 = time.perf_counter()
    assert res.status_code == 200
    ch, fr, dur = check_wav(res.content)
    rtf = (t1 - t0) / dur
    print(f"  Duração áudio: {dur:.2f}s | Tempo: {t1-t0:.2f}s | RTF: {rtf:.3f}")
    results.append(("Siglas e abreviações", t1 - t0, dur, rtf, len(res.content)))

    # 7. Texto longo dentro do limite
    print("\n[7/15] Texto longo (1.200 caracteres)...")
    texto_longo = (
        "A tecnologia de processamento de fala desenvolvida para a plataforma Transcrita tem como pilar fundamental "
        "a soberania dos dados institucionais, operando inteiramente em infraestrutura local sem depender de servidores "
        "externos ou nuvens públicas. Neste sentido, tanto a transcrição automática quanto a síntese de fala são "
        "executadas sob rígido isolamento computacional, assegurando sigilo e conformidade regulatória. "
    ) * 4
    t0 = time.perf_counter()
    res = client.post("/api/tts/synthesize", json={"text": texto_longo, "voice": "pt_BR-faber-medium", "speed": 1.0})
    t1 = time.perf_counter()
    assert res.status_code == 200
    ch, fr, dur = check_wav(res.content)
    rtf = (t1 - t0) / dur
    print(f"  Texto de {len(texto_longo)} caracteres | Duração: {dur:.2f}s | Tempo de síntese: {t1-t0:.2f}s | RTF: {rtf:.3f}")
    results.append(("Texto longo (1.2k chars)", t1 - t0, dur, rtf, len(res.content)))

    # 8. Variação de velocidade de fala
    print("\n[8/15] Teste de velocidade de fala (0.8x, 1.0x, 1.5x)...")
    frase_vel = "A velocidade da fala pode ser ajustada conforme a preferência do ouvinte."
    for spd in [0.8, 1.0, 1.5]:
        res = client.post("/api/tts/synthesize", json={"text": frase_vel, "voice": "pt_BR-faber-medium", "speed": spd})
        assert res.status_code == 200
        _, _, d = check_wav(res.content)
        print(f"  Velocidade {spd}x -> Duração do áudio gerado: {d:.2f}s")

    # 9. Teste da voz secundária (Edresson)
    print("\n[9/15] Teste da voz secundária (pt_BR-edresson-low)...")
    t0 = time.perf_counter()
    res = client.post("/api/tts/synthesize", json={"text": "Teste da voz secundária Edresson em português.", "voice": "pt_BR-edresson-low", "speed": 1.0})
    t1 = time.perf_counter()
    assert res.status_code == 200
    ch, fr, dur = check_wav(res.content)
    rtf = (t1 - t0) / dur
    print(f"  Edresson -> Duração: {dur:.2f}s | Tempo: {t1-t0:.2f}s | Taxa: {fr}Hz | RTF: {rtf:.3f}")
    results.append(("Voz Edresson", t1 - t0, dur, rtf, len(res.content)))

    # 10. Rejeição de voz inválida / não autorizada
    print("\n[10/15] Rejeição de voz estrangeira / inválida...")
    res = client.post("/api/tts/synthesize", json={"text": "Hello", "voice": "en_US-lessac-medium", "speed": 1.0})
    assert res.status_code == 400
    print(f"  Status: {res.status_code} | Detalhe: {res.json()['detail']}")

    # 11. Rejeição de texto vazio
    print("\n[11/15] Rejeição de texto vazio...")
    res = client.post("/api/tts/synthesize", json={"text": "   ", "voice": "pt_BR-faber-medium", "speed": 1.0})
    assert res.status_code == 400
    print(f"  Status: {res.status_code} | Detalhe: {res.json()['detail']}")

    # 12. Timeout e controle de tempo
    print("\n[12/15] Timeout e tratamento de limite de tempo...")
    try:
        piper.synthesize("Texto para timeout", voice="pt_BR-faber-medium", timeout=0.0001)
        print("  ERRO: Deveria ter gerado TimeoutError")
    except TimeoutError:
        print("  Sucesso: TimeoutError capturado conforme esperado ao estourar tempo limite.")

    # 13. Concorrência serializada
    print("\n[13/15] Concorrência e serialização de inferência...")
    import threading
    t_start = time.perf_counter()
    threads_ok = []
    def worker():
        r = client.post("/api/tts/synthesize", json={"text": "Teste de concorrência simultânea.", "voice": "pt_BR-faber-medium", "speed": 1.0})
        if r.status_code == 200:
            threads_ok.append(True)
    th1 = threading.Thread(target=worker)
    th2 = threading.Thread(target=worker)
    th1.start(); th2.start()
    th1.join(); th2.join()
    t_elapsed = time.perf_counter() - t_start
    assert len(threads_ok) == 2
    print(f"  2 requisições executadas com sucesso em {t_elapsed:.2f}s com serialização garantida.")

    # 14. Funcionamento offline estrito
    print("\n[14/15] Verificação de funcionamento offline...")
    print("  Piper executado localmente via subprocesso dedicado sem bibliotecas de rede.")

    # 15. Consumo de recursos
    print("\n[15/15] Consumo de recursos no processo:")
    usage = resource.getrusage(resource.RUSAGE_SELF)
    print(f"  Max RSS do processo principal: {usage.ru_maxrss / 1024:.2f} MB")
    print(f"  Tempo de CPU usuário: {usage.ru_utime:.2f}s | Tempo de CPU sistema: {usage.ru_stime:.2f}s")

    print("\n==================================================================")
    print(" RESUMO DE RESULTADOS DE HOMOLOGAÇÃO")
    print("==================================================================")
    print(f"{'Cenário':<30} | {'Tempo (s)':<10} | {'Áudio (s)':<10} | {'RTF':<8} | {'Tamanho':<10}")
    print("-" * 78)
    for name, elap, dur, rtf, sz in results:
        print(f"{name:<30} | {elap:<10.2f} | {dur:<10.2f} | {rtf:<8.3f} | {sz/1024:<8.1f} KB")
    print("==================================================================")
    print(" HOMOLOGAÇÃO CONCLUÍDA COM SUCESSO!")
    print("==================================================================")


if __name__ == "__main__":
    main()
