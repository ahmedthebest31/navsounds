import queue
from pathlib import Path
import threading
from typing import Optional
import wave

from logHandler import log
import nvwave


class SoundWorker(threading.Thread):

    def __init__(self) -> None:
        super().__init__(daemon=True)

        self.queue: queue.Queue = queue.Queue()
        self.start()

    def play(self, player: nvwave.WavePlayer, data: bytes) -> None:
        self.queue.put((player, data,))

    def run(self) -> None:
        while True:
            player, data = self.queue.get()
            try:
                player.stop()
                player.feed(data)
            except RuntimeError as error:
                log.error("Playback error NVDA nvwave: %s", str(error))
            except TypeError:
                log.error("Incorrect data sent to player.feed")

            self.queue.task_done()


class AudioCache:

    def __init__(self, sound_file: Path):
        self._params = None
        self._data = None

        with wave.open(str(sound_file), "rb") as wf:
            self._params = (wf.getnchannels(), wf.getsampwidth(), wf.getframerate(),)
            self._data = wf.readframes(wf.getnframes())

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


class MultiPlayerManager:

    def __init__(self, volume: int) -> None:
        self.volume: int = volume
        self.cache: dict[str, AudioCache] = {}
        self.format_players: dict[tuple[int, int, int], nvwave.WavePlayer] = {}

        self.worker = SoundWorker()

    def preload_sound(self, name: str, sound_file: Path) -> None:
        if sound_file.exists():
            try:
                self.cache[name] = AudioCache(sound_file)
            except OSError as error:
                log.warning("Error reading file '%s': %s", str(sound_file), str(error))

    def _get_player_for_format(self, params: tuple[int, int, int]) -> Optional[nvwave.WavePlayer]:
        if params not in self.format_players:
            channels, sampwidth, framerate = params
            try:
                player = nvwave.WavePlayer(
                    channels=channels,
                    samplesPerSec=framerate,
                    bitsPerSample=sampwidth * 8,
                )
                player.setVolume(all=self.volume / 100)
                self.format_players[params] = player

            except (RuntimeError, OSError) as error:
                log.error("Failed to initialize audio device: %s", str(error))
                return None

            except (ValueError, KeyError, TypeError) as error:
                log.error("Incorrect audio or configuration settings: %s", str(error))
                return None

        player = self.format_players[params]
        return player

    def play(self, sound_id: str) -> None:
        if sound_id not in self.cache:
            return

        sound = self.cache[sound_id]
        player = self._get_player_for_format(sound.params)

        if player:
            self.worker.play(player, sound.data)

    def update_volume(self, volume: int) -> None:
        for player in self.format_players.values():
            player.setVolume(all=volume / 100)

    def clear_all(self) -> None:
        for player in self.format_players.values():
            player.stop()

        self.format_players.clear()
        self.cache.clear()
