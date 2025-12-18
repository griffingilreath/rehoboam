# Early Digital Art & Generative Systems Research

This document collects research on early digital art (1960s-1970s), specifically focusing on generative techniques using FORTRAN and mainframe computers like the IBM 370. This research serves as an aesthetic and technical foundation for the "Divergence" and generative art scenes on the project's e-ink display.

## Historical Context: The Era of Plotters and Mainframes

In the late 1960s and 1970s, computer art was emerging as a new form. Unlike today's pixel-based raster graphics, much of this early art was vector-based, designed to be drawn by mechanical plotters (like the CalComp 565) or printed on line printers.

### Key Characteristics
- **Medium:** Ink on paper (plotters) or ASCII/overstriking on line printers.
- **Hardware:** Mainframes (IBM 360/370, CDC 6600) and minicomputers (DEC PDP series).
- **Languages:** Primarily FORTRAN (Formula Translation), occasionally ALGOL.
- **Aesthetic:** High contrast, monochrome (usually black ink on white paper), geometric, mathematical, and often featuring moiré patterns or precise line work.

## Focus: David E. Johnson and the IBM 370

The aesthetic of "lines forming a 3D surface" (as seen in the reference image of a folded sine-like wave) is a hallmark of this era.

*   **Artist:** David E. Johnson (and contemporaries like Frieder Nake, Manfred Mohr, Vera Molnár).
*   **System:** IBM 370 (a dominant mainframe series introduced in 1970).
*   **Language:** FORTRAN.
*   **Output:** Likely a drum plotter or flatbed plotter.

### How These Generations Were Done

The creation process for these images was purely mathematical and algorithmic. There were no "paint" programs.

1.  **Mathematical Functions:** The core of the image is usually a mathematical function of two variables, $z = f(x, y)$.
    *   Common functions: Sine/Cosine waves, exponentials, and combinations thereof to create "peaks" and "folds".
    *   Example: $z = \sin(\sqrt{x^2 + y^2}) / \sqrt{x^2 + y^2}$ (the "sombrero" function).

2.  **Hidden Line Removal:** A critical technical challenge of the time. To make a wireframe look like a solid surface, lines "behind" the front folds must be hidden. Algorithms were written from scratch to calculate visibility.
    *   **The "Horizon" Algorithm:** A common technique involved drawing the surface from "front" to "back" (or vice versa) and maintaining a "horizon" array that tracked the highest (and sometimes lowest) $y$ value drawn so far for each $x$ coordinate. If a new point was below the current horizon, it was hidden.

3.  **FORTRAN Implementation:**
    *   The code would consist of nested loops iterating over the $x$ and $z$ (depth) coordinates.
    *   Coordinates would be transformed from 3D space $(x, y, z)$ to 2D page coordinates $(u, v)$ using isometric or perspective projection formulas.
    *   `CALL PLOT(X, Y, PEN_UP/DOWN)` subroutines would control the physical pen.

## Influence on E-ink Generations

The constraints and aesthetics of 1970s plotter art are uniquely suited for modern e-ink displays.

### 1. Aesthetic Alignment
*   **High Contrast:** E-ink is fundamentally bi-stable (black/white). While it supports grayscale, it excels at crisp line art.
*   **Resolution:** Modern e-ink panels have high DPI (similar to the pen precision of old plotters), making fine lines look printed.
*   **Static Nature:** E-ink doesn't refresh constantly (60Hz). It updates and holds an image, much like a plotter drawing a static piece of art.

### 2. Generative Techniques for the Project
We can emulate the IBM 370/FORTRAN style in Python using `numpy` and `PIL` (Pillow), but restricting ourselves to the algorithmic logic of the era.

*   **"Retro Plotter" Scene:** A scene that generates a new 3D surface function every few hours.
    *   **Algorithm:** Use the "Horizon" floating-horizon hidden line removal algorithm (simple and period-correct).
    *   **Style:** Draw lines across the surface (cross-sections) rather than shading pixels. This minimizes ghosting on e-ink since it's pure black/white lines.
*   **Divergence Visualization:**
    *   Instead of a standard bar chart, use a "distorted mesh" where the magnitude of divergence deforms a perfect grid.
    *   Higher divergence = more chaotic peaks and valleys in the generated surface.

### 3. Technical Implementation Strategy
Instead of ray-tracing or heavy 3D libraries (which might be slow on a Jetson/Pi for this specific look), we should implement the **vector math directly**:

```python
# Conceptual Python equivalent of the FORTRAN loop
for z_depth in range(far, near, step):
    for x in range(left, right, step):
        y_height = math.sin(x * freq + phase) * math.cos(z_depth * freq)
        
        # Project 3D (x, y_height, z_depth) to 2D (screen_x, screen_y)
        screen_x = x + z_depth * scale_factor
        screen_y = y_height + z_depth * scale_factor
        
        # Draw line to previous point if not hidden
```

## References & Further Reading
*   **"Computer Graphics: Principles and Practice"**: For historical hidden-line algorithms.
*   **Plotter Art History**: Works by Plottertwitter, Frieder Nake, and the "Computer Arts Society".
*   **IBM 370 Architecture**: Understanding the constraints (memory, processing) that led to these elegant, sparse designs.
