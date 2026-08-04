"""Small libVLC adapter for embedding muted video in a Tkinter frame."""

import importlib
from pathlib import Path


class VlcPlayerError(RuntimeError):
    """Raised when embedded VLC cannot initialize or play media."""


class EmbeddedVlcPlayer:
    """Own one libVLC instance and bind it to a Linux/X11 Tk widget."""

    def __init__(self, video_surface, vlc_module=None):
        self.video_surface = video_surface
        self.vlc = vlc_module or self._import_vlc()
        self.instance = None
        self.player = None
        self.media = None
        self.media_path = None
        self.released = False

        try:
            self.instance = self.vlc.Instance(
                "--no-audio",
                "--no-video-title-show",
                "--quiet",
            )
            if self.instance is None:
                raise VlcPlayerError("libVLC did not create an instance.")
            self.player = self.instance.media_player_new()
            if self.player is None:
                raise VlcPlayerError("libVLC did not create a media player.")
            self.attach_video_surface()
        except VlcPlayerError:
            self.release()
            raise
        except Exception as error:
            self.release()
            raise VlcPlayerError(
                f"Embedded VLC could not be initialized: {error}"
            ) from error

    @staticmethod
    def _import_vlc():
        try:
            return importlib.import_module("vlc")
        except (ImportError, OSError) as error:
            raise VlcPlayerError(
                "Embedded VLC is unavailable. Install the system 'vlc' "
                "package and the Python 'python-vlc' package."
            ) from error

    def attach_video_surface(self):
        """Bind libVLC output to the native X11 window owned by Tk."""

        if self.player is None:
            raise VlcPlayerError("The VLC media player is not initialized.")
        self.video_surface.update_idletasks()
        window_id = int(self.video_surface.winfo_id())
        if window_id <= 0:
            raise VlcPlayerError("Tkinter did not provide a valid X11 window ID.")
        self.player.set_xwindow(window_id)

    def load(self, media_path):
        """Load an existing video without starting playback."""

        self._require_active()
        media_path = Path(media_path)
        if not media_path.is_file():
            raise FileNotFoundError(f"Video does not exist: {media_path}")

        self.unload()
        try:
            self.media = self.instance.media_new(str(media_path))
            if self.media is None:
                raise VlcPlayerError("libVLC could not create video media.")
            self.player.set_media(self.media)
            self.attach_video_surface()
        except VlcPlayerError:
            raise
        except Exception as error:
            self._release_media()
            raise VlcPlayerError(f"VLC could not load the video: {error}") from error

        self.media_path = media_path
        return media_path

    def unload(self):
        """Stop and detach the current media while keeping libVLC ready."""

        self._require_active()
        self.stop()
        try:
            self.player.set_media(None)
        except Exception:
            pass
        self._release_media()

    def play(self):
        self._require_media()
        self.attach_video_surface()
        try:
            result = self.player.play()
        except Exception as error:
            raise VlcPlayerError(f"VLC playback failed: {error}") from error
        if result == -1:
            raise VlcPlayerError("VLC could not start playback.")

    def pause(self):
        self._require_media()
        self.player.pause()

    def stop(self):
        if self.player is not None:
            try:
                self.player.stop()
            except Exception:
                pass

    def set_position(self, position):
        self._require_media()
        position = max(0.0, min(1.0, float(position)))
        self.player.set_position(position)

    def get_position(self):
        if self.player is None or self.media is None:
            return 0.0
        try:
            return max(0.0, float(self.player.get_position()))
        except (TypeError, ValueError):
            return 0.0

    def get_time_ms(self):
        return self._get_non_negative_player_value("get_time")

    def get_length_ms(self):
        return self._get_non_negative_player_value("get_length")

    def is_playing(self):
        if self.player is None:
            return False
        try:
            return bool(self.player.is_playing())
        except Exception:
            return False

    def has_ended(self):
        if self.player is None:
            return False
        try:
            state = self.player.get_state()
            ended_state = getattr(getattr(self.vlc, "State", None), "Ended", None)
            if ended_state is not None:
                return state == ended_state
            return str(state).lower().endswith("ended")
        except Exception:
            return False

    def release(self):
        """Release native resources; safe to call more than once."""

        if self.released:
            return
        self.stop()
        if self.player is not None:
            try:
                self.player.set_media(None)
            except Exception:
                pass
        self._release_media()
        if self.player is not None:
            try:
                self.player.release()
            except Exception:
                pass
        if self.instance is not None:
            try:
                self.instance.release()
            except Exception:
                pass
        self.player = None
        self.instance = None
        self.released = True

    def _release_media(self):
        if self.media is not None:
            try:
                self.media.release()
            except Exception:
                pass
        self.media = None
        self.media_path = None

    def _require_active(self):
        if self.released or self.instance is None or self.player is None:
            raise VlcPlayerError("The VLC player has been released.")

    def _require_media(self):
        self._require_active()
        if self.media is None:
            raise VlcPlayerError("No annotated video is loaded.")

    def _get_non_negative_player_value(self, method_name):
        if self.player is None or self.media is None:
            return 0
        try:
            value = int(getattr(self.player, method_name)())
        except (AttributeError, TypeError, ValueError):
            return 0
        return max(0, value)
