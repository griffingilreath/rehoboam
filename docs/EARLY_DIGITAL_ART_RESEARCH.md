# Early Digital Art & Generative Systems Research

This document collects research on early digital art (1960s-1970s), specifically focusing on generative techniques, the lineage of code from textile looms, and the use of mainframes like the IBM 370. This research serves as an aesthetic and technical foundation for the "Divergence" and generative art scenes on the project's e-ink display.

## 1. The Prehistory: Textiles, Logic, and the Grid

The history of digital art does not begin with the screen, but with the thread. The connection between weaving and computing is literal, not just metaphorical.

### The Jacquard Loom (1804) & The First Binary Image
Joseph Marie Jacquard invented a mechanism that used a chain of punched cards to control the raising and lowering of warp threads on a loom.
*   **The Mechanism:** A hole in the card meant "yes" (lift thread), no hole meant "no" (leave thread). This is the ancestor of the binary 0 and 1.
*   **The Aesthetic:** Woven fabric is inherently a grid (warp and weft). Any image produced on a loom is pixelated by definition.
*   **Influence on Computing:** Charles Babbage adopted Jacquard's punch cards for the Analytical Engine (the first general-purpose computer design). Ada Lovelace famously noted: *"The Analytical Engine weaves algebraic patterns just as the Jacquard loom weaves flowers and leaves."*

### IBM Punch Cards & The "Textile" of Data
By the 1960s/70s, the IBM punch card (standardized in 1928) was the primary interface for mainframes.
*   **Physicality:** A standard card had 80 columns and 12 rows. This fixed grid imposed a strict constraint on data entry and programming, echoing the fixed grid of a loom.
*   **ASCII Art & Overstriking:** Before plotters were common, "images" were printed on line printers using these same grids. Artists created shading not by changing color, but by "weaving" characters—printing an 'H', backing up, and printing an 'I' over it to create a darker block (overstriking). This is identical to increasing thread count or ply in weaving to create density.

---

## 2. Lineages of Influence: How the "Schools" Formed

Early digital art wasn't a singular movement but sprang up in isolated clusters of scientists and philosophers who influenced each other deeply.

### A. The Stuttgart School (Information Aesthetics)
*Location: Germany | Key Figure: Max Bense*
Max Bense was a philosopher who argued that "aesthetic state" could be calculated mathematically. His influence created a generation of "exact aesthetics."

1.  **Frieder Nake (1938–)**
    *   *Background:* Mathematician.
    *   *Influence:* Student of Bense. He rejected the "subjective" artist in favor of objective algorithms.
    *   *Evolution:* Started with matrix multiplications to generate structures. Later grew critical of the computer's role in capitalism, moving towards critical theory.
    *   *Style:* Extreme precision, tension between macro-structure and micro-randomness.
2.  **Georg Nees (1926–2016)**
    *   *Background:* Siemens engineer.
    *   *Influence:* Also influenced by Bense. He produced the first-ever exhibition of computer art (1965).
    *   *Style:* "Schotter" (Gravel) is the definitive work of this era—showing the transition from order (the grid) to entropy (chaos), a direct visualization of thermodynamics.

### B. The Bell Labs Circle
*Location: New Jersey, USA | Key Context: Access to cutting-edge hardware*
Engineers working on visual perception and signals found art as a byproduct of research.

3.  **A. Michael Noll (1939–)**
    *   *Background:* Engineer.
    *   *Experiment:* He created a "Gaussian Quadratic" that mimicked Mondrian’s painting style. When shown to subjects, they preferred the computer version over the real Mondrian, sparking a debate on creativity.
    *   *Technique:* Stereoscopic 3D plotting (early VR concepts).
4.  **Lillian Schwartz (1927–)**
    *   *Background:* Traditional artist who entered Bell Labs.
    *   *Connection:* Worked with Ken Knowlton. She brought the "painterly" eye; Knowlton brought the code (BEFLIX language).
    *   *Style:* She used errors, glitches, and the raw texture of the cathode ray tube, linking back to the tactile nature of textiles/materials.

### C. The Algorists (The French/European Connect)
*Focus: The "Hand" in the Machine*

5.  **Vera Molnár (1924–2024)**
    *   *Background:* Traditional painter (Constructivism).
    *   *The "Machine Imaginaire":* Before she had access to a computer, she "computed" drawings by hand using strict rules and dice, acting as the CPU herself.
    *   *Evolution:* When she finally got computer access (1968), she used it to perform the "1% Disorder"—drawing thousands of squares but slightly vibrating the angles to see at what point "order" becomes "art."
6.  **Manfred Mohr (1938–)**
    *   *Background:* Jazz musician and painter.
    *   *Connection:* Deeply influenced by music theory (rhythm, repetition). He saw the computer as a way to access "hyper-cubes" and dimensions impossible to visualize mentally.
    *   *Style:* The "Cube" series. He fractured the cube, unfolding it like a complex origami structure.

---

## 3. Artist Profiles & Techniques (1965–1980)

### 1. The Grid Breakers
*The grid is the loom. These artists explored how to break it.*

*   **Vera Molnár (Work: *Structure de Quadrilatères*)**
    *   *Technique:* Draw a grid. For each cell, draw a square. Randomly perturb the corners by a tiny amount $\delta$.
    *   *Legacy:* Proved that "perfect" geometry is boring; "almost perfect" is human.
*   **Georg Nees (Work: *Schotter*)**
    *   *Technique:* Accumulation of chaos. Row 1: Rotation 0. Row 2: Rotation $rand(0, 5)$. Row 10: Rotation $rand(0, 90)$.
    *   *Legacy:* The visual definition of entropy.

### 2. The Topologists
*Drawing landscapes that don't exist.*

*   **David E. Johnson (Work: *Scalar Fields*)**
    *   *Technique:* Floating Horizon algorithm.
    *   *Concept:* Using sine waves ($z = \sin(r)$) to mimic fabric folds. The lines look like threads draping over an invisible object.
*   **Grace Hertlein (Work: *The Grid*)**
    *   *Technique:* She would define a strict grid (machines) and grow "organic" algorithms (plants) inside them, representing the struggle of nature vs. technology.

### 3. The Weavers (Direct Textile Connection)
*   **Anni Albers (Bauhaus)**
    *   *Note:* While a weaver, not a "digital" artist, her work at the Bauhaus (1920s) prefigured digital logic. She built textiles using strict modular "units" (triangles/squares) that could be encoded. She is the spiritual grandmother of pixel art.
*   **Beryl Korot (1970s)**
    *   *Work:* Video art installations treating screens as "threads" in a loom.
    *   *Concept:* "Video weaving"—using multiple monitors to create a synchronized pattern, explicitly referencing the Jacquard loom.

---

## 4. Technical Implementation: "Weaving" with Code

To emulate this history, we don't just "draw lines"; we "weave" pixels.

### Algorithm A: The "Jacquard" Noise (Binary Texture)
Instead of standard random noise, we generate noise that respects a "warp and weft."

```python
import numpy as np

def jacquard_noise(width, height, warp_strength=0.8, weft_strength=0.2):
    """
    Simulates a textile defect or 'slub' in the digital weave.
    """
    grid = np.zeros((height, width))
    
    # 1. Warp (Vertical threads)
    # Some threads are "stuck" high or low
    warp_faults = np.random.choice([0, 1], size=width, p=[1-warp_strength, warp_strength])
    
    # 2. Weft (Horizontal threads)
    weft_faults = np.random.choice([0, 1], size=height, p=[1-weft_strength, weft_strength])
    
    # 3. Weave
    for y in range(height):
        for x in range(width):
            # A simplistic logic: The pixel is ON if Warp OR Weft is active
            # mimicking thread lifting.
            if warp_faults[x] > 0.5 or weft_faults[y] > 0.5:
                # Add moire/interference pattern
                if (x + y) % 2 == 0: 
                    grid[y, x] = 1.0
                    
    return grid
```

### Algorithm B: The "Schotter" (Entropy)
This is the standard for our "Divergence" meter.

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

### Algorithm C: The "Floating Horizon" (Folded Fabric)
This mimics the David E. Johnson "draped cloth" aesthetic.

```python
def floating_horizon(width, steps, z_depths, func):
    horizon = [0] * width  # Track highest Y drawn so far
    lines = []

    for z in range(z_depths):
        current_line = []
        for x in range(0, width, steps):
            # 1. Calculate height based on function (e.g., Sine wave)
            y_height = func(x, z) 
            
            # 2. Project to 2D
            screen_x = x + (z * 10)
            screen_y = 500 - (y_height * 50) - (z * 5)
            
            # 3. Horizon Check (Hidden Surface Removal)
            if screen_y < horizon[x] or horizon[x] == 0:
                current_line.append((screen_x, screen_y))
                horizon[x] = screen_y 
            else:
                current_line.append(None) # Pen up (hidden behind fold)
        
        lines.append(current_line)
    return lines
```
