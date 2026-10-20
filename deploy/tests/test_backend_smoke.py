import io
from contextlib import redirect_stdout
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend_smoke as smoke


class VideoSmokeTests(unittest.TestCase):
    def setUp(self):
        self.cv = MagicMock()
        self.torch = MagicMock()
        self.model = MagicMock()
        self.model.model.parameters.return_value = iter([SimpleNamespace(device=SimpleNamespace(type='cuda'))])
        self.engine = MagicMock()
        self.engine._load_model.return_value = self.model
        self.result = SimpleNamespace(frame_count=4, image_width=64, image_height=64,
                                      preview_image=SimpleNamespace(size=(64, 64)))
        def detect(source, *, output_video_path):
            output_video_path.write_bytes(b'synthetic-test-output')
            return self.result
        self.engine.detect_video.side_effect = detect
        modules = {'cv2': self.cv, 'numpy': MagicMock(), 'torch': self.torch,
                   'app.integrations.yolo_engine': SimpleNamespace(YoloEngine=lambda **kwargs: self.engine)}
        self.modules = patch.dict(sys.modules, modules)
        self.modules.start()
        self.addCleanup(self.modules.stop)

    def test_real_engine_path_and_all_four_frames_are_required(self):
        output = io.StringIO()
        with patch.object(smoke, 'decoded_frames', side_effect=[4, 4]), redirect_stdout(output):
            smoke.video_smoke()
        self.engine.detect_video.assert_called_once()
        self.model.to.assert_called_once_with('cuda:0')
        self.assertEqual(self.cv.VideoWriter.return_value.write.call_count, 4)
        self.cv.VideoWriter.return_value.release.assert_called_once()
        self.assertIn('Container YOLO video smoke test: PASS', output.getvalue())

    def test_tracking_dependency_error_is_not_hidden(self):
        self.engine.detect_video.side_effect = ModuleNotFoundError("No module named 'lap'")
        with patch.object(smoke, 'decoded_frames', return_value=4):
            with self.assertRaises(ModuleNotFoundError):
                smoke.video_smoke()

    def test_truncated_result_is_not_success(self):
        with patch.object(smoke, 'decoded_frames', side_effect=[4, 3]):
            with self.assertRaisesRegex(RuntimeError, 'output must decode to four frames'):
                smoke.video_smoke()

    def test_gpu_video_never_silently_uses_cpu(self):
        self.torch.cuda.is_available.return_value = False
        with self.assertRaisesRegex(RuntimeError, 'CUDA unavailable'):
            smoke.video_smoke()
        self.engine.detect_video.assert_not_called()

    def test_failed_encoder_releases_resources(self):
        self.cv.VideoWriter.return_value.isOpened.return_value = False
        with self.assertRaisesRegex(RuntimeError, 'encoder unavailable'):
            smoke.video_smoke()
        self.cv.VideoWriter.return_value.release.assert_called_once()

    def test_decoding_counts_actual_frames_and_releases_capture(self):
        capture = self.cv.VideoCapture.return_value
        frame = SimpleNamespace(shape=(64, 64, 3))
        capture.read.side_effect = [(True, frame)] * 4 + [(False, None)]
        self.assertEqual(smoke.decoded_frames(Path('synthetic.mp4')), 4)
        capture.release.assert_called_once()


class RuntimeDependenciesTests(unittest.TestCase):
    def test_ci_delivery_includes_tracking_dependency_and_cpu_torch(self):
        script = Path(__file__).resolve().parents[1] / 'ci_requirements.py'
        result = subprocess.run([sys.executable, str(script)], check=True, capture_output=True, text=True)
        pins = result.stdout.splitlines()
        self.assertIn('lap==0.5.13', pins)
        self.assertIn('torch==2.11.0+cpu', pins)
        self.assertNotIn('torch==2.11.0+cu126', pins)


if __name__ == '__main__':
    unittest.main()
