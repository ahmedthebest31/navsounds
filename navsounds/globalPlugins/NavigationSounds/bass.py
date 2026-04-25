from ctypes import *
import os

BASS_UNICODE = 0x80000000
BASS_SAMPLE_FLOAT = 256
BASS_STREAM_AUTOFREE = 0x40000

class BASS:
    def __init__(self, dll_path):
        self.bass = windll.LoadLibrary(dll_path)
        self.bass.BASS_Init(-1, 44100, 0, 0, 0)

    def stream_create_file(self, mem, file, offset, length, flags):
        return self.bass.BASS_StreamCreateFile(mem, file, offset, length, flags | BASS_UNICODE)

    def channel_play(self, handle, restart):
        return self.bass.BASS_ChannelPlay(handle, restart)

    def channel_stop(self, handle):
        return self.bass.BASS_ChannelStop(handle)

    def channel_set_attribute(self, handle, attrib, value):
        # BASS_ATTRIB_VOL = 2
        return self.bass.BASS_ChannelSetAttribute(handle, attrib, c_float(value))

    def free(self):
        self.bass.BASS_Free()
