"""Focused tests for model-information text on annotated video frames."""

from importlib.machinery import ModuleSpec
import importlib.util
import sys
import types
from unittest.mock import Mock, patch
import unittest


if importlib.util.find_spec("cv2") is None:
    fake_cv2 = types.ModuleType("cv2")
    fake_cv2.__spec__ = ModuleSpec("cv2", loader=None)
    sys.modules["cv2"] = fake_cv2

from analysis.annotate import annotate_frame, draw_model_info


class ModelInfoAnnotationTests(unittest.TestCase):
    @patch("analysis.annotate.draw_text")
    def test_draws_below_enabled_frame_information(self, draw_text_mock):
        frame = object()

        result = draw_model_info(
            frame,
            ("Table: V2 FP32", "Ball: V3 INT8"),
            frame_info_enabled=True,
        )

        self.assertIs(result, frame)
        self.assertEqual(
            draw_text_mock.call_args_list,
            [
                unittest.mock.call(frame, "Table: V2 FP32", (20, 150)),
                unittest.mock.call(frame, "Ball: V3 INT8", (20, 180)),
            ],
        )

    @patch("analysis.annotate.draw_text")
    def test_moves_to_first_line_when_frame_information_is_disabled(
        self,
        draw_text_mock,
    ):
        frame = object()

        draw_model_info(
            frame,
            ("Models: V2 PT",),
            frame_info_enabled=False,
        )

        draw_text_mock.assert_called_once_with(
            frame,
            "Models: V2 PT",
            (20, 30),
        )

    @patch("analysis.annotate.draw_model_info")
    def test_independent_toggle_suppresses_model_information(
        self,
        draw_model_info_mock,
    ):
        frame = Mock()
        copied_frame = object()
        frame.copy.return_value = copied_frame

        result = annotate_frame(
            frame=frame,
            frame_index=0,
            fps=30.0,
            model_info_lines=("Models: V2 FP32",),
            draw_frame_info_enabled=False,
            draw_model_info_enabled=False,
            draw_table=False,
            draw_ball=False,
            draw_active_ball=False,
            draw_ball_trail=False,
            draw_bounces=False,
            draw_launch_region=False,
        )

        self.assertIs(result, copied_frame)
        draw_model_info_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
