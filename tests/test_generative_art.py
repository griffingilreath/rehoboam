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
        # It's hard to verify exact geometry, but we can check if it's not empty
        # Convert to numpy to check for black pixels (0)
        arr = np.array(img)
        if arr.dtype == bool:
             self.assertTrue(np.any(arr == False), "Image should contain black (False) pixels")
        else:
             self.assertTrue(np.any(arr == 0), "Image should contain black (0) pixels")
        
        # Draw with high divergence
        img2 = Image.new("1", (200, 200), 1)
        draw2 = ImageDraw.Draw(img2)
        GenerativeAlgorithms.schotter_grid(draw2, (0, 0, 200, 200), rows=5, cols=5, divergence=1.0)
        arr2 = np.array(img2)
        if arr2.dtype == bool:
             self.assertTrue(np.any(arr2 == False), "High divergence image should contain black (False) pixels")
        else:
             self.assertTrue(np.any(arr2 == 0), "High divergence image should contain black (0) pixels")

    def test_floating_horizon(self):
        """Test floating horizon rendering."""
        img = Image.new("1", (200, 200), 1)
        draw = ImageDraw.Draw(img)
        
        # Simple flat function
        func = lambda x, z: 0.5
        
        GenerativeAlgorithms.floating_horizon(draw, (0, 0, 200, 200), func, steps=10, z_depths=5)
        
        arr = np.array(img)
        if arr.dtype == bool:
             self.assertTrue(np.any(arr == False), "Floating horizon should draw lines (False pixels)")
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
        # In 1-bit image, usually 0 is black, 255 (or 1/True) is white
        # Pillow might convert 1-bit to boolean array in numpy
        if arr.dtype == bool:
             self.assertTrue(np.any(arr == True), "Should have True (white) pixels")
             self.assertTrue(np.any(arr == False), "Should have False (black) pixels")
        else:
             # Check for both extremes. Note: 1-bit images often map to True/False in recent numpy/pillow versions
             # Or 0/1, or 0/255.
             self.assertTrue(np.any(arr != 0), "Should have non-zero pixels")
             self.assertTrue(np.any(arr == 0), "Should have zero pixels")

if __name__ == "__main__":
    unittest.main()
