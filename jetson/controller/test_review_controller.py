"""Focused tests for annotated-video handling in ReviewController."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


CONTROLLER_DIR = Path(__file__).resolve().parent
if str(CONTROLLER_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROLLER_DIR))


import review_controller_config
from review_controller import ReviewController


class ReviewControllerAnnotatedVideoTests(unittest.TestCase):
    def test_returns_none_when_session_has_no_annotated_video(self):
        controller = ReviewController()

        self.assertIsNone(
            controller.get_annotated_video_path_from_session({})
        )

    def test_remaps_container_path_to_local_annotated_directory(self):
        controller = ReviewController()

        with tempfile.TemporaryDirectory() as temporary_directory:
            annotated_directory = Path(temporary_directory) / "annotated"
            annotated_directory.mkdir()
            local_video = annotated_directory / "annotate_session_v2.mkv"
            local_video.touch()

            session_data = {
                "artifacts": {
                    "annotated_video_path": (
                        "/workspace/tcubed/project/jetson/review/annotated/"
                        "annotate_session_v2.mkv"
                    )
                }
            }

            with mock.patch.object(
                review_controller_config,
                "ANNOTATED_DIR",
                annotated_directory,
            ):
                resolved_path = (
                    controller.get_annotated_video_path_from_session(
                        session_data
                    )
                )

            self.assertEqual(resolved_path, local_video)

    def test_missing_video_raises_file_error(self):
        controller = ReviewController()

        with self.assertRaises(FileNotFoundError):
            controller.open_annotated_video("missing_video.mkv")

    def test_missing_vlc_raises_runtime_error(self):
        controller = ReviewController()

        with tempfile.TemporaryDirectory() as temporary_directory:
            video_path = Path(temporary_directory) / "annotated.mkv"
            video_path.touch()

            missing_paths = [Path(temporary_directory) / "missing-vlc"]
            with mock.patch.object(
                review_controller_config,
                "VLC_EXECUTABLE_PATHS",
                missing_paths,
            ), mock.patch("review_controller.shutil.which", return_value=None):
                with self.assertRaisesRegex(RuntimeError, "VLC could not be found"):
                    controller.open_annotated_video(video_path)

    def test_finds_configured_vlc_when_path_lookup_fails(self):
        controller = ReviewController()

        with tempfile.TemporaryDirectory() as temporary_directory:
            configured_vlc = Path(temporary_directory) / "vlc"
            configured_vlc.touch()

            with mock.patch.object(
                review_controller_config,
                "VLC_EXECUTABLE_PATHS",
                [configured_vlc],
            ), mock.patch("review_controller.shutil.which", return_value=None):
                vlc_path = controller._find_vlc_executable()

            self.assertEqual(vlc_path, str(configured_vlc))

    def test_launches_existing_video_with_vlc(self):
        controller = ReviewController()

        with tempfile.TemporaryDirectory() as temporary_directory:
            video_path = Path(temporary_directory) / "annotated.mkv"
            video_path.touch()

            with mock.patch(
                "review_controller.shutil.which",
                return_value="/usr/bin/vlc",
            ), mock.patch("review_controller.subprocess.Popen") as popen:
                opened_path = controller.open_annotated_video(video_path)

            popen.assert_called_once_with(
                ["/usr/bin/vlc", str(video_path)],
                stdout=mock.ANY,
                stderr=mock.ANY,
            )
            self.assertEqual(opened_path, video_path)
            self.assertEqual(controller.last_opened_file_path, video_path)

    def test_vlc_launch_failure_raises_runtime_error(self):
        controller = ReviewController()

        with tempfile.TemporaryDirectory() as temporary_directory:
            video_path = Path(temporary_directory) / "annotated.mkv"
            video_path.touch()

            with mock.patch(
                "review_controller.shutil.which",
                return_value="/usr/bin/vlc",
            ), mock.patch(
                "review_controller.subprocess.Popen",
                side_effect=OSError("launch failed"),
            ):
                with self.assertRaisesRegex(RuntimeError, "VLC could not be opened"):
                    controller.open_annotated_video(video_path)


class ReviewControllerMetricTests(unittest.TestCase):
    def test_extracts_speed_and_shot_percentage_metrics(self):
        controller = ReviewController()
        session_data = {
            "training_settings": {"number_of_shots": 10},
            "summary": {
                "total_bounces": 8,
                "average_return_speed_kmh": 25.5,
                "fastest_return_speed_kmh": 34.25,
            },
        }

        stats = controller.extract_stats_from_session(session_data)

        self.assertEqual(stats["average_return_speed_kmh"], 25.5)
        self.assertEqual(stats["fastest_return_speed_kmh"], 34.25)
        self.assertEqual(stats["shot_percentage"], 0.8)

    def test_missing_shot_or_speed_data_uses_unavailable_values(self):
        controller = ReviewController()

        stats = controller.extract_stats_from_session(
            {"summary": {"total_bounces": 2}}
        )

        self.assertIsNone(stats["average_return_speed_kmh"])
        self.assertIsNone(stats["fastest_return_speed_kmh"])
        self.assertIsNone(stats["shot_percentage"])


if __name__ == "__main__":
    unittest.main()
