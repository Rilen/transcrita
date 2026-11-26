"""Testes para o motor Piper TTS e endpoints da API (TRANSCRITA-022)."""

import os
import subprocess
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import transcrita.web as web
from transcrita.tts import (
    AUTHORIZED_VOICES,
    DEFAULT_VOICE_ID,
    list_voices_payload,
    max_tts_chars,
    piper_binary_path,
    piper_models_dir,
    tts_enabled,
    voice_availability,
)
from transcrita.tts.piper import PiperTTS, PiperTTSError


class TtsContractAndUnitTests(unittest.TestCase):
    def test_default_flag_disabled(self) -> None:
        """TRANSCRITA_ENABLE_TTS deve ser falso por padrão."""
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(tts_enabled())

    def test_flag_activation(self) -> None:
        """Garante leitura correta de valores positivos na flag."""
        for val in ["true", "1", "yes", "on", "TRUE"]:
            with patch.dict(os.environ, {"TRANSCRITA_ENABLE_TTS": val}):
                self.assertTrue(tts_enabled())

    def test_authorized_voices_only_pt_br(self) -> None:
        """Política de segurança estrita: apenas vozes em pt-BR autorizadas."""
        for voice_id, spec in AUTHORIZED_VOICES.items():
            self.assertEqual(spec.language, "pt-BR")
            self.assertTrue(voice_id.startswith("pt_BR-"))
        self.assertIn("pt_BR-faber-medium", AUTHORIZED_VOICES)
        self.assertTrue(AUTHORIZED_VOICES["pt_BR-faber-medium"].is_default)

    def test_rejection_of_unauthorized_voice(self) -> None:
        """Vozes fora da allowlist pt-BR devem ser rejeitadas."""
        unauthorized = ["en_US-lessac-medium", "es_ES-carlfm-x_low", "pt_PT-tu-medium", "arbitrary/path"]
        for voice in unauthorized:
            avail, reason = voice_availability(voice)
            self.assertFalse(avail)
            self.assertIn("não autorizada", reason)

            piper = PiperTTS()
            with self.assertRaises(ValueError) as ctx:
                piper.synthesize(text="Teste", voice=voice)
            self.assertIn("não autorizada", str(ctx.exception))

    def test_input_validation_empty_and_max_chars(self) -> None:
        piper = PiperTTS()
        # Vazio
        with self.assertRaises(ValueError) as ctx:
            piper.synthesize(text="")
        self.assertIn("não fornecido", str(ctx.exception))

        # Espaços em branco
        with self.assertRaises(ValueError) as ctx:
            piper.synthesize(text="   \n\t  ")
        self.assertIn("não fornecido", str(ctx.exception))

        # Limite de caracteres
        with patch.dict(os.environ, {"TRANSCRITA_TTS_MAX_CHARS": "50"}):
            with self.assertRaises(ValueError) as ctx:
                piper.synthesize(text="A" * 51)
            self.assertIn("excede o limite", str(ctx.exception))

    def test_speed_validation(self) -> None:
        piper = PiperTTS()
        for invalid_speed in [-1.0, 0.1, 0.49, 2.01, 5.0]:
            with self.assertRaises(ValueError) as ctx:
                piper.synthesize(text="Olá", speed=invalid_speed)
            self.assertIn("Velocidade", str(ctx.exception))

    def test_synthesize_subprocess_arguments_no_shell(self) -> None:
        """Garante execução segura por lista de argumentos e sem shell=True."""
        piper = PiperTTS()
        with patch("subprocess.run") as mock_run:
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_run.return_value = mock_proc

            # Simula arquivo WAV gerado
            def fake_run(cmd, **kwargs):
                self.assertIsInstance(cmd, list)
                self.assertNotIn("shell", kwargs)
                # Verifica argumento de saída
                out_idx = cmd.index("-f")
                out_file = Path(cmd[out_idx + 1])
                out_file.write_bytes(b"RIFF" + b"\x00" * 40 + b"data" + b"\x00" * 10)
                return mock_proc

            mock_run.side_effect = fake_run

            audio = piper.synthesize("Texto para teste", voice="pt_BR-faber-medium", speed=1.2)
            self.assertTrue(len(audio) > 44)
            self.assertTrue(audio.startswith(b"RIFF"))


class TtsApiEndpointsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(web.app)

    def test_get_voices_endpoint(self) -> None:
        res = self.client.get("/api/tts/voices")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("enabled", data)
        self.assertIn("default_voice", data)
        self.assertEqual(data["default_voice"], "pt_BR-faber-medium")
        self.assertIn("voices", data)
        voice_ids = [v["id"] for v in data["voices"]]
        self.assertIn("pt_BR-faber-medium", voice_ids)

    def test_synthesize_rejected_when_flag_disabled(self) -> None:
        with patch.dict(os.environ, {"TRANSCRITA_ENABLE_TTS": "false"}):
            res = self.client.post(
                "/api/tts/synthesize",
                json={"text": "Teste", "voice": "pt_BR-faber-medium", "speed": 1.0},
            )
            self.assertEqual(res.status_code, 503)
            self.assertIn("desabilitado", res.json()["detail"])

    def test_synthesize_rejected_unauthorized_voice(self) -> None:
        with patch.dict(os.environ, {"TRANSCRITA_ENABLE_TTS": "true"}):
            res = self.client.post(
                "/api/tts/synthesize",
                json={"text": "Teste", "voice": "en_US-unknown", "speed": 1.0},
            )
            self.assertEqual(res.status_code, 400)
            self.assertIn("não autorizada", res.json()["detail"])

    def test_synthesize_rejected_empty_text(self) -> None:
        with patch.dict(os.environ, {"TRANSCRITA_ENABLE_TTS": "true"}):
            res = self.client.post(
                "/api/tts/synthesize",
                json={"text": "   ", "voice": "pt_BR-faber-medium", "speed": 1.0},
            )
            self.assertEqual(res.status_code, 400)
            self.assertIn("Texto não fornecido", res.json()["detail"])

    def test_synthesize_rejected_invalid_speed(self) -> None:
        with patch.dict(os.environ, {"TRANSCRITA_ENABLE_TTS": "true"}):
            res = self.client.post(
                "/api/tts/synthesize",
                json={"text": "Teste", "voice": "pt_BR-faber-medium", "speed": 3.5},
            )
            self.assertEqual(res.status_code, 400)
            self.assertIn("Velocidade", res.json()["detail"])

    def test_synthesize_success_real_or_mocked(self) -> None:
        """Testa síntese via endpoint com flag ativada."""
        with patch.dict(os.environ, {"TRANSCRITA_ENABLE_TTS": "true"}):
            res = self.client.post(
                "/api/tts/synthesize",
                json={
                    "text": "Olá! Teste de síntese com acentos: coração, café, R$ 1.500,00.",
                    "voice": "pt_BR-faber-medium",
                    "speed": 1.0,
                },
            )
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.headers.get("content-type"), "audio/wav")
            self.assertTrue(len(res.content) > 1000)
            self.assertTrue(res.content.startswith(b"RIFF"))

    def test_synthesize_serializes_with_asr_semaphore(self) -> None:
        """Garante que requisições TTS simultâneas respeitam a serialização do semáforo."""
        with patch.dict(os.environ, {"TRANSCRITA_ENABLE_TTS": "true"}):
            fake_wav = b"RIFF" + b"\x00" * 40 + b"data" + b"\x00" * 100
            order = []
            lock = threading.Lock()

            def slow_synthesize(*args, **kwargs):
                with lock:
                    order.append("enter")
                time.sleep(0.1)
                with lock:
                    order.append("leave")
                return fake_wav

            with patch("transcrita.web.PiperTTS.synthesize", side_effect=slow_synthesize):
                results = []

                def worker():
                    res = self.client.post(
                        "/api/tts/synthesize",
                        json={"text": "Teste concorrente", "voice": "pt_BR-faber-medium", "speed": 1.0},
                    )
                    results.append(res)

                t1 = threading.Thread(target=worker)
                t2 = threading.Thread(target=worker)
                t1.start()
                t2.start()
                t1.join()
                t2.join()

                self.assertEqual(len(results), 2)
                for r in results:
                    self.assertEqual(r.status_code, 200)

                # Ordem esperada quando serializado: enter -> leave -> enter -> leave
                self.assertEqual(order, ["enter", "leave", "enter", "leave"])


class TtsUiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = Path("transcrita/static/index.html").read_text(encoding="utf-8")

    def test_two_tabs_present_and_accessible(self) -> None:
        """Verifica seletor de abas estruturado com ARIA role tablist e tab."""
        self.assertIn('role="tablist"', self.html)
        self.assertIn('id="tabBtnAsr"', self.html)
        self.assertIn('id="tabBtnTts"', self.html)
        self.assertIn('id="tabPanelAsr"', self.html)
        self.assertIn('id="tabPanelTts"', self.html)
        self.assertIn("Áudio/Vídeo para Texto", self.html)
        self.assertIn("Texto para Áudio", self.html)

    def test_tts_controls_present(self) -> None:
        """Verifica os controles exigidos para a Aba 2 (Piper TTS)."""
        self.assertIn("ttsVoiceSelect", self.html)
        self.assertIn("pt_BR-faber-medium", self.html)
        self.assertIn("ttsSpeedInput", self.html)
        self.assertIn("ttsTextInput", self.html)
        self.assertIn("ttsCharCount", self.html)
        self.assertIn("ttsSynthesizeBtn", self.html)
        self.assertIn("ttsClearBtn", self.html)
        self.assertIn("ttsAudioPlayer", self.html)
        self.assertIn("ttsDownloadBtn", self.html)
        self.assertIn("ttsProgressCard", self.html)

    def test_independent_state_and_tab_switching(self) -> None:
        """Verifica existência da função switchTab e navegação por teclado."""
        self.assertIn("switchTab", self.html)
        self.assertIn("ArrowRight", self.html)
        self.assertIn("ArrowLeft", self.html)
        self.assertIn("api/tts/voices", self.html)
        self.assertIn("api/tts/synthesize", self.html)


if __name__ == "__main__":
    unittest.main()
