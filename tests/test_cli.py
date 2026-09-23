import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from music_studio import cli


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="music test ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = dict(title="한강", style="R&B; $(test)", lyrics="[Verse]\n새벽의 노래",
                         seed=42, cot="off", steps=8, threads=4, timeout=10)
        self.config = dict(executable=str(self.root / "fake engine.exe"), model_dir=str(self.root),
                           model="main.gguf", vae="vae.gguf", backend="cuda")
        for name in ["fake engine.exe", "main.gguf", "vae.gguf"]:
            (self.root / name).write_bytes(b"test fixture")
        (self.root / "sidecars").mkdir()
        for name in cli.SIDECARS:
            (self.root / "sidecars" / name).write_bytes(b"test fixture")
        self.sampler = patch.object(cli.GpuSampler, "run", return_value=None)
        self.sampler.start()
        self.addCleanup(self.sampler.stop)

    def run_generation(self, runner):
        return cli.generate(self.config, self.data, self.root / "outputs", runner=runner)

    @staticmethod
    def valid_runner(command, log, timeout):
        output = command[command.index("--out") + 1]
        with wave.open(output, "wb") as f:
            f.setnchannels(2)
            f.setsampwidth(2)
            f.setframerate(48000)
            f.writeframes(b"\x01\x00" * 480 * 2)
        return 0

    def test_success_preserves_unicode_and_arguments(self):
        folder, meta = self.run_generation(self.valid_runner)
        self.assertEqual(meta["status"], "succeeded")
        self.assertEqual(meta["wav"]["channels"], 2)
        saved = cli.read_json(folder / "metadata.json")
        self.assertEqual(saved["input"], self.data)
        self.assertIn("style=R&B; $(test)", saved["command"])
        self.assertIn(self.data["lyrics"], saved["command"])
        self.assertFalse((self.root / "outputs/.generation.lock").exists())

    def test_nonzero_exit_persists_failure(self):
        folder, meta = self.run_generation(lambda *args: 3)
        self.assertEqual(meta["status"], "failed")
        self.assertEqual(meta["returncode"], 3)
        self.assertIsNone(meta["audio_path"])
        self.assertTrue((folder / "engine.log").exists())

    def test_missing_wav_is_failure(self):
        _, meta = self.run_generation(lambda *args: 0)
        self.assertEqual(meta["status"], "failed")

    def test_timeout_and_interrupt_release_lock(self):
        for exception, expected in [(subprocess.TimeoutExpired("fake", 10), "timed_out"),
                                    (KeyboardInterrupt(), "cancelled")]:
            def runner(*args):
                raise exception
            _, meta = self.run_generation(runner)
            self.assertEqual(meta["status"], expected)
            self.assertFalse((self.root / "outputs/.generation.lock").exists())

    def test_invalid_input_before_output_creation(self):
        for field, value in [("lyrics", " "), ("seed", -1), ("steps", True), ("timeout", 0), ("cot", "invalid")]:
            data = copy.deepcopy(self.data)
            data[field] = value
            with self.assertRaises(ValueError):
                cli.generate(self.config, data, self.root / "outputs", runner=self.valid_runner)
        self.assertFalse((self.root / "outputs").exists())

    def test_lock_prevents_concurrent_runs(self):
        output = self.root / "outputs"
        output.mkdir()
        lock = output / ".generation.lock"
        lock.write_text("123")
        with self.assertRaisesRegex(ValueError, "lock"):
            self.run_generation(self.valid_runner)
        self.assertEqual(lock.read_text(), "123")

    def test_missing_model_fails_preflight(self):
        (self.root / "main.gguf").unlink()
        with self.assertRaisesRegex(ValueError, "Missing"):
            self.run_generation(self.valid_runner)

    def test_truncated_wav_rejected(self):
        path = self.root / "truncated.wav"
        self.valid_runner(["--out", str(path)], None, 1)
        path.write_bytes(path.read_bytes()[:-10])
        with self.assertRaisesRegex(ValueError, "Truncated"):
            cli.inspect_wav(path)

    def test_real_subprocess_timeout_is_terminated(self):
        self.data["timeout"] = 1
        command = [sys.executable, "-c", "import time; time.sleep(60)"]
        with patch.object(cli, "build_command", return_value=command):
            folder, meta = cli.generate(self.config, self.data, self.root / "outputs")
        self.assertEqual(meta["status"], "timed_out")
        self.assertLess(meta["elapsed_seconds"], 10)
        self.assertEqual(cli.read_json(folder / "metadata.json")["status"], "timed_out")
        self.assertFalse((self.root / "outputs/.generation.lock").exists())

    def test_real_subprocess_failure_captures_log(self):
        command = [sys.executable, "-c", "import sys; print('engine diagnostic'); sys.exit(7)"]
        with patch.object(cli, "build_command", return_value=command):
            folder, meta = cli.generate(self.config, self.data, self.root / "outputs")
        self.assertEqual(meta["status"], "failed")
        self.assertEqual(meta["returncode"], 7)
        self.assertIn("engine diagnostic", (folder / "engine.log").read_text())

    def test_replay_uses_original_settings_and_parent(self):
        path = self.root / "metadata.json"
        cli.save_json(path, dict(config=self.config, input=self.data, id="original"))
        with patch.object(cli, "generate", return_value=(self.root, {"status": "succeeded"})) as run:
            self.assertEqual(cli.main(["replay", str(path)]), 0)
        self.assertEqual(run.call_args.args[0], self.config)
        self.assertEqual(run.call_args.args[1], self.data)
        self.assertEqual(run.call_args.args[3], "original")


if __name__ == "__main__":
    unittest.main()
