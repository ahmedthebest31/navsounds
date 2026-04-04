import os
from pathlib import Path
from ctypes import *
from logHandler import log

# BASS Constants
BASS_UNICODE = 0x80000000
BASS_STREAM_AUTOFREE = 0x40000
BASS_ATTRIB_VOL = 2

class MultiPlayerManager:
    def __init__(self, volume: int) -> None:
        self.volume: float = volume / 100.0
        self.cache: dict[str, Path] = {}
        self.bass = None
        self._init_bass()

    def _init_bass(self):
        try:
            dll_path = str(Path(__file__).resolve().parent / "bass.dll")
            if not os.path.exists(dll_path):
                log.error(f"NavigationSounds: bass.dll not found at {dll_path}")
                return
            
            # Use windll for stdcall calling convention
            self.bass = windll.LoadLibrary(dll_path)
            
            # Set argtypes for safety
            self.bass.BASS_Init.argtypes = [c_int, c_uint32, c_uint32, c_void_p, c_void_p]
            self.bass.BASS_StreamCreateFile.argtypes = [c_bool, c_wchar_p, c_uint64, c_uint64, c_uint32]
            self.bass.BASS_StreamCreateFile.restype = c_uint32
            self.bass.BASS_ChannelSetAttribute.argtypes = [c_uint32, c_uint32, c_float]
            self.bass.BASS_ChannelPlay.argtypes = [c_uint32, c_bool]
            self.bass.BASS_Free.argtypes = []
            self.bass.BASS_ErrorGetCode.restype = c_int

            # Initialize BASS with default device, 44100Hz
            if not self.bass.BASS_Init(-1, 44100, 0, None, None):
                error_code = self.bass.BASS_ErrorGetCode()
                if error_code != 14:  # 14 = already initialized
                    log.error(f"NavigationSounds: BASS_Init failed with error {error_code}")
                    self.bass = None
        except Exception as e:
            log.error(f"NavigationSounds: Failed to load or initialize BASS: {e}")
            self.bass = None

    def preload_sound(self, name: str, sound_file: Path) -> None:
        if sound_file.exists():
            self.cache[name] = sound_file

    def play(self, sound_id: str) -> None:
        if not self.bass or sound_id not in self.cache:
            return

        sound_path = str(self.cache[sound_id])
        
        # Create a stream from the file
        handle = self.bass.BASS_StreamCreateFile(False, sound_path, 0, 0, BASS_UNICODE | BASS_STREAM_AUTOFREE)
        if handle != 0:
            self.bass.BASS_ChannelSetAttribute(handle, BASS_ATTRIB_VOL, self.volume)
            self.bass.BASS_ChannelPlay(handle, True)
        else:
            error_code = self.bass.BASS_ErrorGetCode()
            log.error(f"NavigationSounds: BASS_StreamCreateFile failed for {sound_path} with error {error_code}")

    def update_volume(self, volume: int) -> None:
        self.volume = volume / 100.0

    def clear_all(self) -> None:
        # BASS handles its own stream cleanup with AUTOFREE
        pass

    def terminate(self):
        if self.bass:
            self.bass.BASS_Free()
