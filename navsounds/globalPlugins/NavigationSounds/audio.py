import array
import queue
import threading
import wave
from pathlib import Path
from typing import Optional

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

    def __init__(self, manager):
        super().__init__(daemon=True)
        self.manager = manager
        self.queue = queue.Queue(maxsize=1)
        self.start()

    def play(self, player: nvwave.WavePlayer, data: bytes) -> None:
        try:
            self.queue.get_nowait()
        except queue.Empty:
            pass
        
        try:
            self.queue.put_nowait((player, data))
        except queue.Full:
            pass

    def run(self) -> None:
        while True:
            task = self.queue.get()
            if task is None:
                break
                
            player, data = task
            try:
                for p in self.manager.format_players.values():
                    if p is not player:
                        p.stop()
                
                player.stop()
                player.feed(data)
            except Exception as error:
                log.error("Playback error: %s", str(error))


class AudioCache:

    def __init__(self, sound_file: Path, volume: int):
        self._params = None
        self._data = None

        with wave.open(str(sound_file), "rb") as wf:
            self._params = (wf.getnchannels(), wf.getsampwidth(), wf.getframerate())
            raw_data = wf.readframes(wf.getnframes())
            sampwidth = wf.getsampwidth()
            
            if sampwidth == 2:
                samples = array.array('h', raw_data)
                vol = max(0, min(100, volume))
                factor = vol / 100.0
                
                for i in range(len(samples)):
                    val = int(samples[i] * factor)
                    samples[i] = max(-32768, min(32767, val))
                    
                self._data = samples.tobytes()
            else:
                self._data = raw_data

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
        self._last_device = get_output_device()
        self.worker = SoundWorker(self)

    def preload_sound(self, name: str, sound_file: Path) -> None:
        if sound_file.exists():
            try:
                self.cache[name] = AudioCache(sound_file, self.volume)
            except OSError as error:
                log.warning("Error reading file '%s': %s", str(sound_file), str(error))

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
                    outputDevice=current_device
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
        self.clear_players()
        self.cache.clear()

    def terminate(self) -> None:
        self.clear_all()
        try:
            self.worker.queue.put_nowait(None)
        except queue.Full:
            pass