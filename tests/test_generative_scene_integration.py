import unittest
from unittest.mock import patch, MagicMock
from epaper.scenes.generative_art_scene import GenerativeArtScene
from PIL import Image

class TestGenerativeScene(unittest.TestCase):
    def test_landscape_generation(self):
        scene = GenerativeArtScene(mode="landscape")
        scene.panel = MagicMock()
        scene.panel.width = 100
        scene.panel.height = 100
        
        with patch("pathlib.Path.read_text", return_value='{"house_activity": 0.8, "daylight": 0.2}'), \
             patch("pathlib.Path.exists", return_value=True):
            
            frames = scene.frames()
            frame, hints = next(frames)
            
            self.assertIsInstance(frame, Image.Image)
            self.assertEqual(frame.size, (100, 100))

    def test_fabric_generation(self):
        scene = GenerativeArtScene(mode="fabric")
        scene.panel = MagicMock()
        scene.panel.width = 100
        scene.panel.height = 100
        
        with patch("pathlib.Path.read_text", return_value='{"house_activity": 0.1, "daylight": 0.9}'), \
             patch("pathlib.Path.exists", return_value=True):
            
            frames = scene.frames()
            frame, hints = next(frames)
            
            self.assertIsInstance(frame, Image.Image)
            self.assertEqual(frame.size, (100, 100))
