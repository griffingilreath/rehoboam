import random
import math
import numpy as np
from PIL import Image, ImageDraw

class GenerativeAlgorithms:
    """
    Implementation of 1960s-70s generative art algorithms for the E-ink display.
    Based on research into Georg Nees, David E. Johnson, and textile theory.
    """

    @staticmethod
    def schotter_grid(draw, bounds, rows=10, cols=10, divergence=0.0):
        """
        Draws a grid of squares that becomes increasingly chaotic (Georg Nees' "Schotter").
        
        Args:
            draw: PIL ImageDraw object
            bounds: tuple (x, y, w, h)
            rows: number of rows
            cols: number of columns
            divergence: 0.0 to 1.0 (amount of chaos)
        """
        x_start, y_start, width, height = bounds
        cell_w = width / cols
        cell_h = height / rows
        
        # Calculate base padding to keep squares inside cells
        padding = min(cell_w, cell_h) * 0.1
        rect_w = cell_w - (padding * 2)
        rect_h = cell_h - (padding * 2)

        for y in range(rows):
            for x in range(cols):
                # Chaos factor increases down the rows AND with global divergence
                # Row 0 has 0 chaos. Row N has max chaos.
                row_chaos = (y / rows) * divergence
                
                # Rotation: Random angle between -45 and +45 degrees * chaos
                angle = (random.random() - 0.5) * 90 * row_chaos
                
                # Translation: Random offset * chaos
                dx = (random.random() - 0.5) * cell_w * row_chaos
                dy = (random.random() - 0.5) * cell_h * row_chaos
                
                # Center of the cell
                cx = x_start + (x * cell_w) + (cell_w / 2) + dx
                cy = y_start + (y * cell_h) + (cell_h / 2) + dy
                
                # Draw rotated rectangle
                # 1. Calculate unrotated corners relative to center
                rw2 = rect_w / 2
                rh2 = rect_h / 2
                corners = [(-rw2, -rh2), (rw2, -rh2), (rw2, rh2), (-rw2, rh2)]
                
                # 2. Rotate and translate
                rad = math.radians(angle)
                cos_a = math.cos(rad)
                sin_a = math.sin(rad)
                
                transformed_corners = []
                for px, py in corners:
                    tx = (px * cos_a - py * sin_a) + cx
                    ty = (px * sin_a + py * cos_a) + cy
                    transformed_corners.append((tx, ty))
                
                # Draw polygon (no anti-aliasing handled by PIL usage usually, 
                # but we stick to 1-pixel outlines)
                draw.polygon(transformed_corners, outline=0, fill=None)

    @staticmethod
    def floating_horizon(draw, bounds, data_function, steps=50, z_depths=20):
        """
        Draws a 3D surface using the "Floating Horizon" hidden-line removal algorithm
        (David E. Johnson style).
        
        Args:
            draw: PIL ImageDraw object
            bounds: tuple (x, y, w, h)
            data_function: lambda(x, z) -> height (0.0 to 1.0)
            steps: number of X steps
            z_depths: number of Z slices (depth)
        """
        bx, by, bw, bh = bounds
        
        # Horizon array tracks the highest Y drawn so far for each X column.
        # Initialize to "bottom" of screen (actually highest pixel value, since 0 is top)
        # But for this logic, we want to hide things "behind" mountains.
        # Usually floating horizon draws Front-to-Back or Back-to-Front.
        # Back-to-Front (Painters algo) is easier if we fill with white, 
        # but pure line art needs Front-to-Back with a horizon check.
        
        # We'll map screen X coordinates to this array.
        horizon = [bh + by] * int(bw) 
        
        # Parameters for projection
        x_step = bw / steps
        z_step_y = (bh * 0.4) / z_depths # How much lines move up per Z step
        z_step_x = (bw * 0.2) / z_depths # Isometric shift
        
        amp = bh * 0.3 # Height amplitude

        for z in range(z_depths):
            # Draw from Front (z=0) to Back (z=max) ?? 
            # Actually Front-to-Back is best for "Horizon" logic.
            # Let's try drawing simple lines first without complex hiding to see aesthetic.
            
            points = []
            for i in range(steps):
                x_pct = i / steps
                
                # Get height from function
                val = data_function(x_pct, z / z_depths)
                
                # Project
                # Screen X = base X + z_shift
                sx = bx + (i * x_step) + (z * z_step_x)
                
                # Screen Y = base Y - height - z_shift
                # Base Y is near bottom
                base_y = by + bh - (z * z_step_y)
                sy = base_y - (val * amp)
                
                points.append((sx, sy))
            
            # Simple polyline for now - hidden line is complex to impl perfectly in one go
            draw.line(points, fill=0, width=2)

    @staticmethod
    def jacquard_noise(width, height, warp_prob=0.8, weft_prob=0.2):
        """
        Generates a PIL Image containing "Jacquard Noise" (warp/weft faults).
        Returns a 1-bit image.
        """
        # Create numpy grid
        grid = np.zeros((height, width), dtype=np.uint8)
        
        # Warp faults (vertical lines stuck)
        # 1 means "white/paper", 0 means "black/ink". E-paper is additive? 
        # Usually 0=Black, 255=White. Let's make noise BLACK on WHITE.
        
        # Start white
        grid.fill(255)
        
        # Generate fault maps
        # Warp: columns that have a glitch
        warp_faults = np.random.choice([0, 1], size=width, p=[1.0 - (1-warp_prob)*0.1, (1-warp_prob)*0.1])
        
        # Weft: rows that have a glitch
        weft_faults = np.random.choice([0, 1], size=height, p=[1.0 - (1-weft_prob)*0.1, (1-weft_prob)*0.1])
        
        # Apply noise
        for y in range(height):
            for x in range(width):
                # If this is a fault intersection
                if warp_faults[x] or weft_faults[y]:
                    # Draw a pixel (black)
                    if random.random() > 0.5:
                        grid[y, x] = 0
        
        return Image.fromarray(grid, mode='L').convert('1')

