import array
import queue
import threading
import wave
from pathlib import Path
from typing import Callable, Optional

import config
from logHandler import log
import nvwave


def get_output_device() -> str:
	try:
		return config.conf["audio"]["outputDevice"]
	except KeyError:
		try:
			return config.conf["speech"]["outputDevice"]
		except KeyError:
			return "Microsoft Sound Mapper"


class SoundWorker(threading.Thread):
	"""Plays queued sound effects serially, off the main thread.

	The worker keeps only the most recent request so a burst of navigation
	events never backlogs audio. Termination is race-free: the stop event is
	checked after every dequeue, so the thread always exits even when a
	pending task occupies the bounded queue.
	"""

	def __init__(self, manager):
		super().__init__(daemon=True)
		self.manager = manager
		self.queue = queue.Queue(maxsize=1)
		self._stop_event = threading.Event()
		self.start()

	def play(self, player: nvwave.WavePlayer, data: bytes) -> None:
		if self._stop_event.is_set():
			return

		try:
			self.queue.get_nowait()
		except queue.Empty:
			pass

		try:
			self.queue.put_nowait((player, data))
		except queue.Full:
			pass

	def stop(self, timeout: float = 5.0) -> None:
		if self._stop_event.is_set():
			return
		self._stop_event.set()
		try:
			self.queue.put_nowait(None)
		except queue.Full:
			# A pending task exists; the run loop will see the stop event
			# right after processing it and exit anyway.
			pass
		if self.is_alive():
			self.join(timeout)

	def run(self) -> None:
		while True:
			task = self.queue.get()
			if task is None or self._stop_event.is_set():
				break

			player, data = task
			try:
				player.stop()
				player.feed(data)
			except Exception as error:
				log.error("Playback error: %s", str(error))


# Every cached sound is converted to this format so exactly one WavePlayer
# (one audio device stream) serves all effects.
# Values derived from analyzing the bundled packs: the default pack mixes
# 42 mono and 44 stereo files, almost all 16-bit, dominated by 44100 Hz with
# single outliers at 11025/22050/48000/96000 Hz. Canonicalizing to STEREO
# 48 kHz keeps the original stereo imaging, and every source except the one
# 96 kHz file is UP-sampled (linear-interpolation upsampling does not alias,
# while downsampling without an anti-alias filter produces harsh artifacts).
CANONICAL_FORMAT: tuple[int, int, int] = (2, 2, 48000)
_CANONICAL_CHANNELS = CANONICAL_FORMAT[0]
_SUPPORTED_SAMPLE_WIDTHS = (1, 2)


def _decode_pcm(raw: bytes, channels: int, sampwidth: int) -> array.array:
	"""Decode raw PCM bytes to interleaved signed 16-bit samples."""
	frames = len(raw) // (channels * sampwidth)
	raw = raw[: frames * channels * sampwidth]
	if sampwidth == 1:
		# 8-bit PCM is unsigned with a 128 center point.
		src = array.array("B", raw)
		out = array.array("h", bytes(2 * len(src)))
		for i, value in enumerate(src):
			out[i] = (value - 128) << 8
		return out
	return array.array("h", raw)


def _to_stereo(samples: array.array, channels: int) -> array.array:
	"""Map interleaved samples with N channels onto the canonical 2 channels."""
	if channels == _CANONICAL_CHANNELS:
		return samples
	if channels == 1:
		out = array.array("h", bytes(4 * len(samples)))
		out[0::2] = samples
		out[1::2] = samples
		return out
	# More than two channels: fold everything to mono first, then duplicate.
	frames = len(samples) // channels
	folded = array.array("h", bytes(2 * frames))
	for i in range(frames):
		total = 0
		base = i * channels
		for c in range(channels):
			total += samples[base + c]
		folded[i] = total // channels
	return _to_stereo(folded, 1)


def _apply_volume(samples: array.array, volume: int) -> array.array:
	factor = max(0, min(100, int(volume))) / 100.0
	if factor >= 0.999:
		return samples
	for i in range(len(samples)):
		# Scaling by a factor <= 1.0 can never exceed the int16 range.
		samples[i] = int(samples[i] * factor)
	return samples


def _resample(samples: array.array, channels: int, src_rate: int, dst_rate: int) -> array.array:
	"""Frame-aware linear-interpolation resampler; good enough for UI effects."""
	if src_rate == dst_rate or not samples:
		return samples
	frames = len(samples) // channels
	out_frames = max(1, round(frames * dst_rate / src_rate))
	out = array.array("h", bytes(2 * out_frames * channels))
	last = frames - 1
	step = src_rate / dst_rate
	for i in range(out_frames):
		pos = min(i * step, last)
		i0 = int(pos)
		frac = pos - i0
		src_base = i0 * channels
		dst_base = i * channels
		if frac == 0.0 or i0 >= last:
			for c in range(channels):
				out[dst_base + c] = samples[src_base + c]
			continue
		next_base = src_base + channels
		for c in range(channels):
			s0 = samples[src_base + c]
			s1 = samples[next_base + c]
			out[dst_base + c] = int(s0 + (s1 - s0) * frac)
	return out


class AudioCache:
	"""Decoded PCM audio in the canonical format, ready for playback."""

	def __init__(self, params: tuple[int, int, int], data: bytes):
		self._params = params
		self._data = data

	@property
	def params(self) -> tuple[int, int, int]:
		if self._params is None:
			raise ValueError("Audio parameters not set")
		return self._params

	@property
	def data(self) -> bytes:
		if self._data is None:
			raise ValueError("Audio data bytes not set")
		return self._data

	@classmethod
	def from_file(cls, sound_file: Path, volume: int) -> "AudioCache":
		with wave.open(str(sound_file), "rb") as wf:
			channels = wf.getnchannels()
			sampwidth = wf.getsampwidth()
			rate = wf.getframerate()
			raw = wf.readframes(wf.getnframes())
		if sampwidth not in _SUPPORTED_SAMPLE_WIDTHS:
			raise wave.Error(f"unsupported sample width {sampwidth * 8} bit")
		channels = max(1, channels)
		samples = _decode_pcm(raw, channels, sampwidth)
		samples = _to_stereo(samples, channels)
		samples = _apply_volume(samples, volume)
		samples = _resample(samples, _CANONICAL_CHANNELS, rate, CANONICAL_FORMAT[2])
		return cls(CANONICAL_FORMAT, samples.tobytes())


class MultiPlayerManager:
	def __init__(self, volume: int) -> None:
		self.volume: int = volume
		self.cache: dict[str, AudioCache] = {}
		self.format_players: dict[tuple[int, int, int], nvwave.WavePlayer] = {}
		self._last_device = get_output_device()
		self.worker = SoundWorker(self)
		self._loader: Optional[threading.Thread] = None
		self._load_generation = 0

	def load_sounds(self, entries: list[tuple[str, Path]], on_done: Optional[Callable[[], None]] = None) -> None:
		"""Decode sound files on a background thread, then swap the cache atomically.

		Entries are (cache_key, wav_path) pairs. A generation counter makes
		stale loads (from a reload started while decoding is still running)
		discard their results. on_done runs on the loader thread; it must only
		touch plain Python data structures.
		"""
		self._load_generation += 1
		generation = self._load_generation
		if self._loader is not None and self._loader.is_alive():
			# Decoding is fast; avoid piling up concurrent loaders.
			self._loader.join(10.0)

		def run() -> None:
			loaded: dict[str, AudioCache] = {}
			for name, path in entries:
				if generation != self._load_generation:
					return
				try:
					loaded[name] = AudioCache.from_file(path, self.volume)
				except (OSError, wave.Error, EOFError) as error:
					log.warning("Error reading file '%s': %s", str(path), str(error))
			if generation != self._load_generation:
				return
			self.cache = loaded
			if on_done is not None:
				try:
					on_done()
				except Exception as error:
					log.error("Sound cache refresh callback failed: %s", str(error))

		loader = threading.Thread(target=run, daemon=True, name="NavSoundsLoader")
		self._loader = loader
		loader.start()

	def _get_player_for_format(self, params: tuple[int, int, int]) -> Optional[nvwave.WavePlayer]:
		current_device = get_output_device()

		if self._last_device != current_device:
			self.clear_players()
			self._last_device = current_device

		if params not in self.format_players:
			channels, sampwidth, framerate = params
			try:
				player = nvwave.WavePlayer(
					channels=channels,
					samplesPerSec=framerate,
					bitsPerSample=sampwidth * 8,
					outputDevice=current_device,
					wantDucking=False,
				)
				self.format_players[params] = player

			except Exception as error:
				log.error("Failed to init audio device: %s", str(error))
				return None

		return self.format_players[params]

	def play(self, sound_id: str) -> None:
		if sound_id not in self.cache:
			return

		sound = self.cache[sound_id]
		player = self._get_player_for_format(sound.params)

		if player:
			self.worker.play(player, sound.data)

	def update_volume(self, volume: int) -> None:
		self.volume = volume

	def clear_players(self) -> None:
		for player in self.format_players.values():
			player.stop()
		self.format_players.clear()

	def clear_all(self) -> None:
		self._load_generation += 1
		self.clear_players()
		self.cache.clear()

	def terminate(self) -> None:
		self.clear_all()
		self.worker.stop()
		if self._loader is not None and self._loader.is_alive():
			self._loader.join(5.0)
