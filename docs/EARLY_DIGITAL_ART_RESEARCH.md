# Comprehensive Research: Early Digital Art, Mainframes, and the Textile Lineage (1960–1980)

## 1. Introduction: The Loom, The Grid, and The Mainframe

The history of generative art is not a history of screens, but a history of **instructions** and **grids**. This document explores the technical and aesthetic origins of digital art in the 1960s and 70s, tracing its lineage directly from the Jacquard loom to the IBM mainframe, and examining how these constraints can inform modern e-ink aesthetics.

### The Core Thesis
Early digital art was defined by **latency** and **blindness**. Artists working on IBM 370s or CDC 6600s did not see their work in real-time. They wrote code on punch cards, submitted a batch job, and waited hours or days for a physical plot. This forced a specific mode of thinking: **procedural logic over visual intuition**. The art was "constructed" in the mind before it was realized on paper, much like a weaver drafts a pattern before the loom is threaded.

---

## 2. The Hardware Context: The Aesthetics of Constraint

To understand the art, one must understand the machine. The aesthetic of "lines," "high contrast," and "geometry" was not just a stylistic choice; it was a hardware necessity.

### 2.1 The Mainframes (IBM 360/370, CDC 6600)
*   **Memory:** Extremely limited (often < 1MB RAM). Storing a full raster image (pixel grid) was impossible.
*   **Vector Display:** The concept of a "pixel" didn't exist in the modern sense. Graphics were **vector lists**—instructions to move a beam or a pen from coordinate $(x_1, y_1)$ to $(x_2, y_2)$.
*   **Language:** FORTRAN IV was the lingua franca. It was rigid, mathematical, and capitalized. It lacked modern object-oriented features, forcing artists to think in arrays (matrices) and nested loops.

### 2.2 The Output Devices
1.  **The Drum/Flatbed Plotter (CalComp 565, Benson-Lehner):**
    *   **Mechanism:** A physical pen moved over paper (or paper moved under the pen).
    *   **Aesthetic:** Constant line weight. No "shading" (except by cross-hatching). High precision.
    *   **The "Jitter":** Stepper motors had finite resolution. Diagonal lines sometimes had a characteristic "staircase" or mechanical vibration, which became part of the aesthetic.
2.  **The Storage Tube (Tektronix 4010/4014):**
    *   **Mechanism:** A CRT that used a "flood gun" to keep the phosphor lit without refreshing.
    *   **Connection to E-ink:** Like e-ink, the storage tube held an image indefinitely without power/refresh. It was **bi-stable** (lit or dark). There was no "undo" (you had to clear the whole screen). This encouraged additive, layered designs.
3.  **The Line Printer (IBM 1403):**
    *   **Mechanism:** Impact hammer printing alphanumeric characters.
    *   **Aesthetic:** ASCII art. Density was achieved by **overstriking** (printing 'M', backspacing, printing 'W', etc.) to create darkness values. This is directly analogous to "ply" in weaving.

---

## 3. The Textile Lineage: "Weaving" Data

The connection between textiles and computing is foundational.

### 3.1 The Jacquard Loom (1804)
*   **The Innovation:** Joseph Marie Jacquard used punch cards to control individual warp threads. A hole = thread up; no hole = thread down.
*   **The Grid:** A woven cloth is a Cartesian grid. Every intersection of warp and weft is a binary state (over/under).
*   **Legacy:** This mechanism was directly adopted by Charles Babbage for the Analytical Engine, and later by Herman Hollerith for the 1890 Census, leading to IBM.

### 3.2 Core Memory: The Woven Computer
*   **Physical Reality:** In the 1960s/70s, computer memory (RAM) was literally woven. **Magnetic Core Memory** consisted of ferrite rings threaded with copper wires (X, Y, and Sense lines).
*   **Labor:** This memory was woven by hand, often by female textile workers ("Little Old Ladies of Memory"), creating a literal bridge between textile labor and computation.

### 3.3 Anni Albers & The Bauhaus
While not a digital artist, Anni Albers (1899–1994) at the Bauhaus developed a theory of weaving that prefigured digital logic.
*   **"Designing" vs. "Making":** She emphasized the construction of structure through modular units (triangles, squares) rather than "painting" on canvas.
*   **Influence:** Her geometric, grid-based tapestries are visually indistinguishable from early 8-bit graphics or plotted grids, proving that the aesthetic of the "pixel" predates the computer.

---

## 4. The Pioneers: 20 Key Artists (1965–1980)

### Group A: The Stuttgart School (Information Aesthetics)
*Philosophy: Art is a calculable state. Entropy vs. Order.*

1.  **Max Bense (The Theorist)**
    *   Developed "Information Aesthetics" in the 1950s. Proposed that aesthetic "value" could be measured by the interplay of macro-order and micro-chaos.
2.  **Georg Nees**
    *   *Work:* *Schotter* (Gravel), 1968.
    *   *Algorithm:* A grid of squares. As $y$ increases, random rotation and displacement increase.
    *   *Significance:* It visualizes the Second Law of Thermodynamics (entropy).
3.  **Frieder Nake**
    *   *Work:* *Hommage à Paul Klee* (1965), *Walk-Through-Raster* (1966).
    *   *Method:* Used transition matrices (Markov chains) to determine the probability of the next line's position/color based on the previous one.
    *   *Quote:* "There are no images. There are only algorithmic situations."

### Group B: The Algorists & Structurists
*Philosophy: Exhaustive exploration of geometric logic.*

4.  **Manfred Mohr**
    *   *Work:* *Cubic Limit* (1973–74).
    *   *Method:* Systematically generated every possible rotation and edge-truncation of a 3D hypercube (tesseract) projected into 2D.
    *   *Deep Dive:* Mohr was a jazz musician. He treated lines like musical notes—improvising within a strict key signature (the cube).
5.  **Vera Molnár**
    *   *Work:* *Structure de Quadrilatères*.
    *   *Method:* The "Machine Imaginaire." She wrote programs in her head before getting computer access. She focused on the **"1% Disorder"**—rigid grids with tiny, humanizing faults.
6.  **Zdeněk Sýkora**
    *   *Work:* *Lines* series.
    *   *Method:* Used a computer to calculate the combinatorial possibilities of tiling modules (curved lines entering/exiting box edges).

### Group C: The American Plotters & Innovators
*Philosophy: New landscapes and organic forms.*

7.  **A. Michael Noll (Bell Labs)**
    *   *Work:* *Gaussian Quadratic* (1963).
    *   *Experiment:* Conducted a Turing Test for art, showing people a computer-generated Mondrian vs. a real one. (People preferred the computer).
8.  **Charles Csuri**
    *   *Work:* *Sine Wave Man* (1967).
    *   *Method:* Digitized a hand drawing of a man, then applied a mathematical sine wave transformation to the coordinate points. One of the first "morphing" effects.
9.  **Grace Hertlein**
    *   *Work:* *The Grid* series.
    *   *Style:* Often combined organic, botanical themes with rigid mechanical grids, exploring the tension between nature and machine.
10. **Colette & Charles Bangert**
    *   *Work:* *Computer Grass* (1970s).
    *   *Method:* Developed complex algorithmic curves to mimic natural growth patterns without using randomness, but rather complex, layered functions.
11. **Ruth Leavitt**
    *   *Work:* *Prismatic Variations*.
    *   *Method:* "Rubber sheet" geometry—mapping grids onto distorted, stretching coordinate systems.
12. **Ken Knowlton**
    *   *Work:* *BEFLIX* (Bell Flicks).
    *   *Innovation:* Invented a programming language specifically for bitmap movie making. Master of large-scale ASCII/mosaic portraits (e.g., *Martha*).

### Group D: The Film & Motion Pioneers
*Philosophy: Time as a dimension.*

13. **John Whitney Sr.**
    *   *Work:* *Permutations* (1968), *Catalog* (1961).
    *   *Method:* Built an analog mechanical computer (MDR—Motion Control) from anti-aircraft gun directors to create perfect harmonic oscillations. "Digital Harmony."
14. **Stan VanDerBeek**
    *   *Work:* *Poem Fields*.
    *   *Method:* Collaborated with Ken Knowlton to create "computer-animated poems" using mosaic block textures.
15. **Lillian Schwartz**
    *   *Work:* *Pixillation*.
    *   *Method:* Used the texture of the CRT and early color mapping to create visceral, glitch-heavy abstractions.

### Group E: The Conceptual & Cybernetic
16. **Edward Zajec**
    *   *Work:* *RAM* series.
    *   *Focus:* "Real-time" composition (even if plotted later). The program as a composer.
17. **Manuel Barbadillo**
    *   *Work:* Modular generation.
    *   *Focus:* The computer as a tool to exhaustively combine simple modular shapes into vast tapestries.
18. **Hiroshi Kawano**
    *   *Work:* *Design 3-1*.
    *   *Method:* Used Markov Chains to teach the computer aesthetic "rules" of color and adjacency.
19. **Harold Cohen**
    *   *Work:* *AARON* (started late 70s).
    *   *Innovation:* The first true AI artist. AARON didn't just draw shapes; it had an internal model of "what a person is" or "what a plant is" and drew from memory.
20. **David E. Johnson**
    *   *Work:* *Linear Surfaces*.
    *   *Focus:* The floating horizon algorithm. The "Reference Implementation" for 3D plotter landscapes.

---

## 5. Technical Deep Dive: The Algorithms of the Era

How did they actually do it?

### 5.1 The Floating Horizon (Hidden Line Removal)
**Problem:** In 1970, calculating a Z-buffer for pixels was too memory-intensive.
**Solution:**
1.  Draw the surface from "front" to "back" (coordinate $Z=0$ to $Z=N$).
2.  Maintain an array `Horizon[Screen_Width]` representing the highest $Y$ value drawn so far at each column.
3.  For a new point $(x, y)$, if $y > \text{Horizon}[x]$, draw it and update horizon. If $y \le \text{Horizon}[x]$, skip (it's hidden).

### 5.2 Super-Ellipses & Lissajous Figures
**Formula:** $|\frac{x}{a}|^n + |\frac{y}{b}|^n = 1$
*   Proposed by Piet Hein, popularized by Gardner.
*   By varying $n$, you transition smoothly from a circle ($n=2$) to a square ($n=\infty$) or a star ($n<1$). This was computationally cheap and aesthetically versatile.

### 5.3 Transformation Matrices
Every rotation or scale was a matrix multiplication.
$$
\begin{bmatrix} x' \\ y' \end{bmatrix} = \begin{bmatrix} \cos \theta & -\sin \theta \\ \sin \theta & \cos \theta \end{bmatrix} \begin{bmatrix} x \\ y \end{bmatrix}
$$
Artists like Nake and Mohr would apply these recursively. A "tree" was just a line, transformed, branching into two lines, transformed again.

### 5.4 Chaikin's Algorithm (Corner Cutting)
Before Bezier curves were standard, George Chaikin (1974) developed a way to smooth poly-lines by iteratively "cutting corners" (replacing a vertex with two new ones at 25% and 75% of the segment). This gave the "smooth" organic look to early plotter curves.

---

## 6. Relevance to Modern E-ink & The Project

This research is not just historical trivia; it is a **technical blueprint** for e-ink development.

1.  **The "Slow Display"**: E-ink has a low refresh rate (like the Tektronix Storage Tube or the time to plot a paper drawing). We should embrace **additive** drawing—adding lines to a scene over time rather than constant full-frame animation.
2.  **Aliasing as Aesthetic**: Anti-aliasing (blurring edges) looks bad on e-ink. The 1-bit, "staircase" aliasing of 1970s plotters is crisp and readable on e-ink. We should disable anti-aliasing in our renderers.
3.  **Divergence via Algorithms**:
    *   **Schotter Logic:** Use the "increasing entropy" algorithm to visualize system health.
        *   *Health 100%:* Perfect Grid.
        *   *Health 80%:* Slight rotation (Molnar style).
        *   *Health 50%:* High rotation (Nees style).
        *   *Health 20%:* Broken topology (glitch/noise).
    *   **Textile Logic:** Use "warp/weft" noise for background textures instead of Perlin noise. It looks digital and structured.

---

## 7. Selected Bibliography & Resources

1.  **"Computer Graphics: Principles and Practice"** (Foley et al.) – The bible of early algorithms.
2.  **"When the Machine Made Art"** (Grant D. Taylor) – excellent history of the "Stuttgart School".
3.  **"The Computer in the Visual Arts"** (Anne Morgan Spalter).
4.  **"White Heat Cold Logic: British Computer Art 1960–1980"**.
5.  **Recode Project (recodeproject.com)** – Modern processing implementations of these historic works.
6.  **"On Weaving"** (Anni Albers) – The theory of structure.
