"""Focused tests for the cancellable Training start delay."""

import sys
import threading
import unittest
from pathlib import Path
from unittest import mock


CONTROLLER_DIR = Path(__file__).resolve().parent
if str(CONTROLLER_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROLLER_DIR))


import training_controller_config
from training_controller import TrainingController


class TrainingStartDelayTests(unittest.TestCase):
    def setUp(self):
        self.controller = TrainingController()

    def test_accepts_zero_and_fifteen_second_boundaries(self):
        self.assertEqual(
            self.controller._validate_start_delay_seconds(0),
            0.0,
        )
        self.assertEqual(
            self.controller._validate_start_delay_seconds(15),
            15.0,
        )

    def test_rejects_values_outside_delay_range(self):
        for invalid_delay in (-0.5, 15.5, "invalid"):
            with self.subTest(invalid_delay=invalid_delay):
                with self.assertRaises(ValueError):
                    self.controller._validate_start_delay_seconds(
                        invalid_delay
                    )

    def test_zero_delay_begins_training_immediately(self):
        with mock.patch.object(
            self.controller,
            "_begin_training_sequence",
            return_value=True,
        ) as begin_training:
            started = self.controller.start_training(
                ball_speed=75,
                pace_seconds=1.5,
                number_of_shots=10,
                start_delay_seconds=0,
            )

        self.assertTrue(started)
        begin_training.assert_called_once_with(
            self.controller.current_settings
        )

    def test_positive_delay_begins_training_after_countdown(self):
        settings = self.controller.validate_training_settings(
            ball_speed=75,
            pace_seconds=1.5,
            number_of_shots=10,
        )
        self.controller.state = training_controller_config.STATE_DELAYING
        self.controller._start_delay_cancel_event = threading.Event()

        with mock.patch.object(
            self.controller,
            "_begin_training_sequence",
        ) as begin_training:
            self.controller._run_start_delay(0.01, settings)

        begin_training.assert_called_once_with(settings)

    def test_stop_cancels_delay_without_starting_training(self):
        with mock.patch.object(
            self.controller,
            "_begin_training_sequence",
        ) as begin_training:
            started = self.controller.start_training(
                ball_speed=75,
                pace_seconds=1.5,
                number_of_shots=10,
                start_delay_seconds=15,
            )
            delay_thread = self.controller._start_delay_thread
            stopped = self.controller.stop_training()
            delay_thread.join(timeout=1.0)

        self.assertTrue(started)
        self.assertTrue(stopped)
        self.assertFalse(delay_thread.is_alive())
        self.assertEqual(
            self.controller.state,
            training_controller_config.STATE_IDLE,
        )
        begin_training.assert_not_called()

    def test_delay_is_not_saved_in_session_json(self):
        self.controller.current_settings = (
            self.controller.validate_training_settings(
                ball_speed=75,
                pace_seconds=1.5,
                number_of_shots=10,
            )
        )
        self.controller.current_session_name = "delay-test"
        self.controller.last_recording_path = Path("delay-test.mkv")

        session_data = self.controller._build_session_metadata()

        self.assertNotIn(
            "start_delay_seconds",
            session_data["training_settings"],
        )


if __name__ == "__main__":
    unittest.main()
