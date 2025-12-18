# Early Digital Art & Generative Systems Research

This document collects research on early digital art (1960s-1970s), specifically focusing on generative techniques using FORTRAN and mainframe computers like the IBM 370. This research serves as an aesthetic and technical foundation for the "Divergence" and generative art scenes on the project's e-ink display.

## Historical Context: The Era of Plotters and Mainframes

In the late 1960s and 1970s, computer art was emerging as a new form. Unlike today's pixel-based raster graphics, much of this early art was vector-based, designed to be drawn by mechanical plotters (like the CalComp 565) or printed on line printers. The aesthetic was defined by the limitations of the hardware: high contrast, monochrome lines, and mathematical precision.

## Key Figures and Evolution (1965–1980)

The evolution of early digital art moved from simple stochastic (random) variations to complex, system-based explorations of geometry and topology.

### Phase 1: The Pioneers (1965–1970) — Order vs. Chaos
*Focus: Randomness constrained by grids.*

1.  **Georg Nees (Germany)**
    *   *Work:* "Schotter" (Gravel), 1968.
    *   *Concept:* A grid of squares that starts orderly at the top and becomes progressively more chaotic (rotated and displaced) towards the bottom.
    *   *Relevance:* Perfect metaphor for "Divergence" (system health degrading).
2.  **Frieder Nake (Germany)**
    *   *Work:* "Hommage à Paul Klee", 1965.
    *   *Concept:* Algorithms influenced by matrix multiplication to generate structural relationships rather than just shapes.
3.  **A. Michael Noll (USA/Bell Labs)**
    *   *Work:* "Gaussian Quadratic", 1963.
    *   *Concept:* One of the first 3D wireframe projections. He experimented with stereoscopic 3D plotting.
4.  **Hiroshi Kawano (Japan)**
    *   *Work:* "Design" series (1964).
    *   *Concept:* Used Markov chains to determine color/shape placement, effectively "teaching" the computer aesthetic rules.
5.  **Bela Julesz (USA)**
    *   *Work:* Random Dot Stereograms.
    *   *Concept:* Investigation of visual perception using computer-generated noise.

### Phase 2: The Structurists (1970–1975) — Logic & Geometry
*Focus: Exhaustive exploration of shapes (cubes, lines) and subtle algorithms.*

6.  **Manfred Mohr (Germany)**
    *   *Work:* "Cubic Limit", 1973–74.
    *   *Concept:* Systematically exploring every possible rotation and truncation of a cube. He viewed the computer as an extension of the mind to visualize high-dimensional logic.
7.  **Vera Molnár (Hungary/France)**
    *   *Work:* "Structure de quadrilatères".
    *   *Concept:* "1% Disorder." She would draw a perfect grid and introduce tiny, algorithmic interruptions to humanize the machine output.
8.  **David E. Johnson (USA)**
    *   *Work:* "Sine Waves" (The folded surface style).
    *   *Concept:* Floating-horizon algorithms to create 3D topographies.
9.  **Edward Zajec (Italy)**
    *   *Work:* "RAM" series.
    *   *Concept:* Modular composition where the program defines a "syntax" of shapes that can be combined in infinite variations.
10. **Manuel Barbadillo (Spain)**
    *   *Work:* Modular computer art based on single recurring forms rotated and combined.

### Phase 3: The Topologists & Organics (1975–1980) — Systems & Landscapes
*Focus: Mathematical surfaces, mapping, and organic algorithms.*

11. **Colette & Charles Bangert (USA)**
    *   *Work:* "Landscapes" and "Computer Grass".
    *   *Concept:* Used distinct algorithms to draw curved lines that mimicked natural forms (grass, leaves) using purely mathematical curves.
12. **Grace Hertlein (USA)**
    *   *Work:* "The Grid" series.
    *   *Concept:* Combined organic forms (textural) with rigid geometric structures.
13. **Ruth Leavitt (USA)**
    *   *Work:* "Prismatic Variations".
    *   *Concept:* Distortion of grids to create optical illusions of stretching and folding (similar to the "Divergence" concept).
14. **Jean-Pierre Hébert (France/USA)**
    *   *Work:* Plotter drawings focusing on sand and wave patterns.
    *   *Concept:* Single-line drawings (writing the pen down once and never lifting it until the end).
15. **Paul Brown (UK)**
    *   *Work:* Cellular automata explorations.
    *   *Concept:* Using simple rules (like Conway's Game of Life) to generate tiling patterns that look like mosaics.

### Phase 4: The Visionaries (Late 70s) — AI & Motion
16. **Harold Cohen (UK/USA)**
    *   *Work:* "AARON".
    *   *Concept:* An early AI program that "learned" rules of composition and drawing, capable of generating never-ending original drawings of people and plants.
17. **Lillian Schwartz (USA)**
    *   *Work:* "Pixillation".
    *   *Concept:* Early experimentation with texture and pattern mapping, often collaborating with Ken Knowlton at Bell Labs.
18. **Ken Knowlton (USA)**
    *   *Work:* BEFLIX (Bell Flicks).
    *   *Concept:* ASCII art animation and mosaic representations of images.
19. **Herbert W. Franke (Austria)**
    *   *Work:* "Electronic Graphics".
    *   *Concept:* Oscillograms and mathematical transformations visualized on CRTs and plotted.
20. **Muriel Cooper (USA/MIT)**
    *   *Concept:* While more design-focused, her work at MIT on "Visible Language" pioneered the aesthetic of digital typography and information layout.

---

## Technical Deep Dive: Algorithms & Logic

The creation process was purely mathematical. There were no "paint" programs. Below are Python implementations of the core algorithms used by these artists, adapted for our project.

### 1. The "Schotter" Algorithm (Controlled Chaos)
*Inspired by Georg Nees.*
Used to visualize the degradation of a system (Divergence).

**Original Logic (Pseudo-FORTRAN):**
```fortran
DO 10 Y = 1, ROWS
DO 10 X = 1, COLS
    ROTATION = (Y / ROWS) * MAX_ROT
    DISPLACEMENT = (Y / ROWS) * MAX_DISP
    CALL DRAW_SQUARE(X + RAND()*DISPLACEMENT, Y + RAND()*DISPLACEMENT, ROTATION)
10 CONTINUE
```

**Python Implementation (for Project):**
```python
import random
import math

def generate_schotter_grid(rows=10, cols=10, cell_size=20, divergence_score=0.5):
    """
    divergence_score (0.0 - 1.0): Multiplier for the chaos.
    """
    shapes = []
    for y in range(rows):
        for x in range(cols):
            # Chaos increases with Y depth AND divergence score
            chaos_factor = (y / rows) * divergence_score
            
            # Rotation limit (e.g., +/- 45 degrees at max chaos)
            angle = (random.random() - 0.5) * math.pi/2 * chaos_factor
            
            # Translation limit
            dx = (random.random() - 0.5) * cell_size * chaos_factor
            dy = (random.random() - 0.5) * cell_size * chaos_factor
            
            base_x = x * cell_size + dx
            base_y = y * cell_size + dy
            
            shapes.append({
                "type": "rect",
                "x": base_x, "y": base_y, 
                "w": cell_size, "h": cell_size, 
                "rotation": angle
            })
    return shapes
```

### 2. The "Floating Horizon" (3D Surface)
*Inspired by David E. Johnson.*
Used to visualize complex data landscapes.

**Concept:**
To draw a 3D mesh $z = f(x, y)$ on a 2D plotter without overlapping lines, you track a "horizon" array.
1. Start at the "front" ($z=0$).
2. Calculate screen $Y$ for every $X$.
3. If the new $Y$ is higher than the `horizon[x]`, draw the point and update `horizon[x]`.
4. If lower, it's behind a hill—skip (pen up).

**Python Logic:**
```python
import math

def floating_horizon(width, steps, z_depths, func):
    horizon = [0] * width  # Initialize horizon at bottom of screen
    lines = []

    for z in range(z_depths):
        current_line = []
        for x in range(0, width, steps):
            # 1. Calculate 3D height
            y_height = func(x, z) 
            
            # 2. Project to 2D (Simple Isometric-ish)
            screen_x = x + (z * 10)
            screen_y = 500 - (y_height * 50) - (z * 5)
            
            # 3. Check Visibility
            if screen_y < horizon[x]:
                # Visible (above horizon) - note: screen_y 0 is usually top
                # In this logic assuming 0 is bottom for simplicity, 
                # but screens are inverted. Let's assume larger Y = higher visual.
                pass 
                
            # Simplified "Max" logic for screen coords (0 at top)
            if screen_y < horizon[x] or horizon[x] == 0:
                current_line.append((screen_x, screen_y))
                horizon[x] = screen_y # New horizon
            else:
                current_line.append(None) # Pen up
        
        lines.append(current_line)
    return lines
```

### 3. The "Molnár" Interruption (Subtle Anomaly)
*Inspired by Vera Molnár.*
Used to show "OK" status with slight imperfections.

**Logic:**
Draw a concentric pattern or grid. With probability $P$ (where $P$ is the system divergence), delete a line, shift a vertex, or break symmetry.

```python
def molnar_rectangles(count, size, divergence_score):
    lines = []
    for i in range(count):
        # Perfect square logic
        tl = (0, 0)
        tr = (size, 0)
        br = (size, size)
        bl = (0, size)
        
        points = [tl, tr, br, bl, tl]
        
        # Divergence: Jitter points
        noisy_points = []
        for (px, py) in points:
            if random.random() < divergence_score:
                px += random.randint(-5, 5)
                py += random.randint(-5, 5)
            noisy_points.append((px, py))
            
        lines.append(noisy_points)
    return lines
```

## Influence on E-ink Generations

The constraints and aesthetics of 1970s plotter art are uniquely suited for modern e-ink displays.

### 1. Aesthetic Alignment
*   **High Contrast:** E-ink is fundamentally bi-stable (black/white). While it supports grayscale, it excels at crisp line art.
*   **Resolution:** Modern e-ink panels have high DPI (similar to the pen precision of old plotters), making fine lines look printed.
*   **Static Nature:** E-ink doesn't refresh constantly (60Hz). It updates and holds an image, much like a plotter drawing a static piece of art.

### 2. Implementation Strategy for "Divergence"
*   **"Retro Plotter" Scene:** A scene that generates a new 3D surface function every few hours.
    *   **Algorithm:** Use the "Horizon" floating-horizon hidden line removal algorithm (simple and period-correct).
    *   **Style:** Draw lines across the surface (cross-sections) rather than shading pixels. This minimizes ghosting on e-ink since it's pure black/white lines.
*   **Divergence Visualization:**
    *   Instead of a standard bar chart, use a "distorted mesh" where the magnitude of divergence deforms a perfect grid.
    *   Higher divergence = more chaotic peaks and valleys in the generated surface.

## References
*   *Computer Graphics: Principles and Practice* (Foley et al.) - For algorithms.
*   *When the Machine Made Art* (Grant D. Taylor).
*   *The Computer in the Visual Arts* (Anne Morgan Spalter).
