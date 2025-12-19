import unittest
from PIL import Image, ImageDraw
import numpy as np
from epaper.core.generative import GenerativeAlgorithms

class TestGenerativeAlgorithms(unittest.TestCase):
    def test_schotter_grid(self):
        """Test that schotter_grid draws something without crashing."""
        img = Image.new("1", (200, 200), 1)
        draw = ImageDraw.Draw(img)
        
        # Draw with 0 divergence (should be perfect grid)
        GenerativeAlgorithms.schotter_grid(draw, (0, 0, 200, 200), rows=5, cols=5, divergence=0.0)
        
        # Verify pixels were drawn (image shouldn't be all white)
        arr = np.array(img)
        if arr.dtype == bool:
             self.assertTrue(np.any(~arr), "Image should contain black (False) pixels")
        else:
             self.assertTrue(np.any(arr == 0), "Image should contain black (0) pixels")
        
        # Draw with high divergence
        img2 = Image.new("1", (200, 200), 1)
        draw2 = ImageDraw.Draw(img2)
        GenerativeAlgorithms.schotter_grid(draw2, (0, 0, 200, 200), rows=5, cols=5, divergence=1.0)
        arr2 = np.array(img2)
        if arr2.dtype == bool:
             self.assertTrue(np.any(~arr2), "High divergence image should contain black (False) pixels")
        else:
             self.assertTrue(np.any(arr2 == 0), "High divergence image should contain black (0) pixels")

    def test_floating_horizon(self):
        """Test floating horizon rendering."""
        img = Image.new("1", (200, 200), 1)
        draw = ImageDraw.Draw(img)
        
        # Simple flat function
        def flat_func(x, z):
            return 0.5
        
        GenerativeAlgorithms.floating_horizon(draw, (0, 0, 200, 200), flat_func, steps=10, z_depths=5)
        
        arr = np.array(img)
        if arr.dtype == bool:
             self.assertTrue(np.any(~arr), "Floating horizon should draw lines (False pixels)")
        else:
             self.assertTrue(np.any(arr == 0), "Floating horizon should draw lines (0 pixels)")

    def test_jacquard_noise(self):
        """Test jacquard noise generation."""
        width, height = 100, 100
        img = GenerativeAlgorithms.jacquard_noise(width, height, warp_prob=0.5, weft_prob=0.5)
        
        self.assertEqual(img.size, (width, height))
        self.assertEqual(img.mode, "1")
        
        arr = np.array(img)
        # Check values
        print(f"Unique values in array: {np.unique(arr)}")
        
        # Should have some black and some white pixels
        if arr.dtype == bool:
             self.assertTrue(np.any(arr), "Should have True (white) pixels")
             self.assertTrue(np.any(~arr), "Should have False (black) pixels")
        else:
             self.assertTrue(np.any(arr != 0), "Should have non-zero pixels")
             self.assertTrue(np.any(arr == 0), "Should have zero pixels")

if __name__ == "__main__":
    unittest.main()
