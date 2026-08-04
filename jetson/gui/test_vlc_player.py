"""Unit tests for the embedded libVLC adapter without native VLC."""

import tempfile
import unittest
import sys
from pathlib import Path
from types import SimpleNamespace

GUI_DIR = Path(__file__).resolve().parent
if str(GUI_DIR) not in sys.path:
    sys.path.insert(0, str(GUI_DIR))

from vlc_player import EmbeddedVlcPlayer, VlcPlayerError


class FakeSurface:
    def update_idletasks(self):
        pass

    def winfo_id(self):
        return 1234


class FakeMedia:
    def __init__(self, path):
        self.path = path
        self.released = False

    def release(self):
        self.released = True


class FakePlayer:
    def __init__(self):
        self.window_id = None
        self.media = None
        self.playing = False
        self.position = 0.0
        self.time = 1500
        self.length = 5000
        self.state = "stopped"
        self.released = False

    def set_xwindow(self, window_id):
        self.window_id = window_id

    def set_media(self, media):
        self.media = media

    def play(self):
        self.playing = True
        self.state = "playing"
        return 0

    def pause(self):
        self.playing = False
        self.state = "paused"

    def stop(self):
        self.playing = False
        self.state = "stopped"

    def set_position(self, position):
        self.position = position

    def get_position(self):
        return self.position

    def get_time(self):
        return self.time

    def get_length(self):
        return self.length

    def is_playing(self):
        return self.playing

    def get_state(self):
        return self.state

    def release(self):
        self.released = True


class FakeInstance:
    def __init__(self):
        self.player = FakePlayer()
        self.released = False

    def media_player_new(self):
        return self.player

    def media_new(self, path):
        return FakeMedia(path)

    def release(self):
        self.released = True


class FakeVlc:
    State = SimpleNamespace(Ended="ended")

    def __init__(self):
        self.instance = FakeInstance()
        self.arguments = None

    def Instance(self, *arguments):
        self.arguments = arguments
        return self.instance


class EmbeddedVlcPlayerTests(unittest.TestCase):
    def setUp(self):
        self.fake_vlc = FakeVlc()
        self.player = EmbeddedVlcPlayer(
            FakeSurface(),
            vlc_module=self.fake_vlc,
        )

    def tearDown(self):
        self.player.release()

    def test_load_play_pause_seek_and_stop(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            video_path = Path(temporary_directory) / "annotated.mkv"
            video_path.touch()

            self.assertEqual(self.player.load(video_path), video_path)
            self.player.play()
            self.assertTrue(self.player.is_playing())
            self.player.pause()
            self.assertFalse(self.player.is_playing())
            self.player.set_position(0.75)
            self.assertEqual(self.player.get_position(), 0.75)
            self.player.stop()

        self.assertEqual(self.player.get_time_ms(), 1500)
        self.assertEqual(self.player.get_length_ms(), 5000)

        self.player.unload()
        self.assertIsNone(self.fake_vlc.instance.player.media)
        self.assertEqual(self.player.get_time_ms(), 0)

    def test_missing_video_is_rejected(self):
        with self.assertRaises(FileNotFoundError):
            self.player.load("/missing/annotated.mkv")

    def test_release_is_idempotent(self):
        native_player = self.fake_vlc.instance.player
        native_instance = self.fake_vlc.instance

        self.player.release()
        self.player.release()

        self.assertTrue(native_player.released)
        self.assertTrue(native_instance.released)
        with self.assertRaisesRegex(VlcPlayerError, "released"):
            self.player.play()

    def test_end_state_is_reported(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            video_path = Path(temporary_directory) / "annotated.mkv"
            video_path.touch()
            self.player.load(video_path)
            self.fake_vlc.instance.player.state = "ended"

            self.assertTrue(self.player.has_ended())


if __name__ == "__main__":
    unittest.main()
