"""Testes de contrato e comportamento para cópia do clipboard (TRANSCRITA-021)."""

import subprocess
import unittest
from pathlib import Path


class ClipboardContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = Path("transcrita/static/index.html").read_text(encoding="utf-8")

    def test_clipboard_fallback_present(self) -> None:
        """Garante que a implementação não depende exclusivamente da Clipboard API."""
        self.assertIn("copyTextToClipboard", self.html)
        self.assertIn("document.execCommand('copy')", self.html)
        self.assertIn("navigator.clipboard && typeof navigator.clipboard.writeText", self.html)

    def test_manual_selection_fallback_present(self) -> None:
        """Garante que se ambos os métodos automáticos falharem, orienta Pressione Ctrl+C."""
        self.assertIn("Pressione Ctrl+C", self.html)
        self.assertIn("selectNodeContents(outputText)", self.html)

    def test_cleanup_temporary_textarea(self) -> None:
        """Garante que o elemento temporário textarea é removido e seleção restaurada."""
        self.assertIn("document.body.removeChild(textArea)", self.html)
        self.assertIn("originalRange", self.html)

    def test_preserves_accents_and_newlines_in_node_simulation(self) -> None:
        """Executa simulação de execução JavaScript no Node para validar HTTP fallback e acentuação."""
        js_code = """
        const assert = require('assert');

        // Simula ambiente HTTP sem navigator.clipboard
        let execCommandCalled = false;
        let lastCopiedValue = null;
        const dom = {
            body: {
                children: [],
                appendChild(el) { this.children.push(el); },
                removeChild(el) {
                    const idx = this.children.indexOf(el);
                    if (idx !== -1) this.children.splice(idx, 1);
                }
            }
        };

        global.navigator = {}; // Sem clipboard API (contexto HTTP inseguro)
        global.document = {
            body: dom.body,
            createElement(tag) {
                return {
                    tag,
                    value: '',
                    style: {},
                    setAttribute() {},
                    focus() {},
                    select() {},
                    setSelectionRange() {}
                };
            },
            execCommand(cmd) {
                if (cmd === 'copy') {
                    execCommandCalled = true;
                    // Valor do último textarea adicionado
                    lastCopiedValue = dom.body.children[dom.body.children.length - 1].value;
                    return true;
                }
                return false;
            },
            getSelection() {
                return { rangeCount: 0, removeAllRanges() {}, addRange() {} };
            }
        };

        // Extrai a função copyTextToClipboard do index.html
        const fs = require('fs');
        const html = fs.readFileSync('transcrita/static/index.html', 'utf8');
        const match = html.match(/async function copyTextToClipboard[\\s\\S]*?\\n  \\}/);
        assert(match, 'Função copyTextToClipboard não encontrada');

        const fn = new Function(match[0] + '; return copyTextToClipboard;')();

        (async () => {
            const sampleText = 'Transcrição com acentuação: João, coração, água, café!\\nSegunda linha com pontuação: R$ 1.250,50.';
            const result = await fn(sampleText);
            assert.strictEqual(result, true, 'Deveria ter retornado true via execCommand');
            assert.strictEqual(execCommandCalled, true, 'execCommand deveria ter sido chamado');
            assert.strictEqual(lastCopiedValue, sampleText, 'Texto copiado deve preservar acentos e quebras');
            assert.strictEqual(dom.body.children.length, 0, 'Textarea temporário deve ter sido removido');
            console.log('OK_SIMULATION');
        })();
        """
        proc = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, f"Node script falhou: {proc.stderr}")
        self.assertIn("OK_SIMULATION", proc.stdout)


if __name__ == "__main__":
    unittest.main()
