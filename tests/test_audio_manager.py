import importlib.util
import sys
import time
from pathlib import Path
from types import SimpleNamespace


class FakeWavePlayer:
	created_with = []

	def __init__(self, **kwargs):
		self.created_with.append(kwargs)

	def stop(self):
		pass


def load_audio_module(monkeypatch):
	FakeWavePlayer.created_with.clear()
	monkeypatch.setitem(
		sys.modules,
		"config",
		SimpleNamespace(conf={"audio": {"outputDevice": "test-device"}, "speech": {}}),
	)
	monkeypatch.setitem(
		sys.modules,
		"logHandler",
		SimpleNamespace(log=SimpleNamespace(error=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None)),
	)
	monkeypatch.setitem(sys.modules, "nvwave", SimpleNamespace(WavePlayer=FakeWavePlayer))

	module_path = Path(__file__).resolve().parents[1] / "navsounds" / "globalPlugins" / "NavigationSounds" / "audio.py"
	spec = importlib.util.spec_from_file_location("navsounds_audio_under_test", module_path)
	audio = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(audio)
	return audio


def test_navigation_sound_player_does_not_request_audio_ducking(monkeypatch):
	audio = load_audio_module(monkeypatch)
	manager = audio.MultiPlayerManager.__new__(audio.MultiPlayerManager)
	manager.format_players = {}
	manager._last_device = "test-device"

	player = manager._get_player_for_format((2, 2, 44100))

	assert player is not None
	assert len(FakeWavePlayer.created_with) == 1
	assert FakeWavePlayer.created_with[0]["wantDucking"] is False


def test_sound_worker_stop_exits_thread_and_ignores_late_work(monkeypatch):
	audio = load_audio_module(monkeypatch)
	manager = audio.MultiPlayerManager(50)
	worker = manager.worker
	assert worker.is_alive()

	worker.play(FakeWavePlayer(), b"\x00\x00")
	worker.stop(timeout=5.0)

	assert not worker.is_alive()
	worker.stop(timeout=5.0)

	worker.play(FakeWavePlayer(), b"\x00\x00")

	assert not worker.is_alive()


def test_manager_terminate_stops_worker_and_loader_cleanly(monkeypatch):
	audio = load_audio_module(monkeypatch)
	manager = audio.MultiPlayerManager(50)
	manager.load_sounds([], on_done=None)

	manager.terminate()

	time.sleep(0.1)
	assert not manager.worker.is_alive()
	assert manager._loader is None or not manager._loader.is_alive()
