# Design System: The Algorithmic Weave

## 1. Design Philosophy: "System Logic as Aesthetic"
This design system bridges the gap between **1970s Mainframe Art**, **Textile Theory**, and modern **System Monitoring**.

The core premise is that the system does not *decorate* data; it *weaves* it. The aesthetic is defined by the constraints of the hardware (the grid, the pixel, the thread) and visualizes the state of the system through **Entropy** (Order vs. Chaos).

### The Three Pillars
1.  **The Grid (Order/Health)**: The baseline state of the system is a perfect, rigid grid (referencing *Anni Albers* and *IBM Punch Cards*). A healthy system is aligned.
2.  **The Thread (Connection/Flow)**: Data is continuous. Visualization is "drawn" or "woven" line-by-line (referencing *Plotters* and *Jacquard Looms*). Lines are continuous; they don't fade out, they unravel.
3.  **The Glitch (Divergence/Entropy)**: Problems are not shown with red warning icons, but with **geometric distortion**. As the system diverges from "normal," the grid rotates, fractures, or dissolves (referencing *Georg Nees' Schotter*).

---

## 2. Visual Grammar

### 2.1 The "Material" (Texture & Resolution)
*   **No Anti-Aliasing:** We embrace the pixel/stitch. All lines on E-ink and Web dashboards should be sharp, aliased, and "stepped."
*   **The Weave (Dithering):** Never use opacity or gray fills. Use **dithering patterns** (Bayer matrix, cross-hatching) to simulate density. This mimics the "overstriking" of line printers and the "ply" of fabric.
    *   *Light:* Single pixel dots.
    *   *Medium:* Checkerboard (1-on-1-off).
    *   *Dark:* Cross-hatch lines.

### 2.2 Typography
*   **Primary Font:** Monospaced, reminiscent of OCR-A or Teletype machines (e.g., *IBM Plex Mono*, *Share Tech Mono*, *VT323*).
*   **Styling:** 
    *   Headers are **ALL CAPS**.
    *   Text is often framed by ASCII borders or block characters (`█`, `▌`, `─`).
    *   Leading (line height) is strict and grid-aligned.

### 2.3 Color Palette (The "Phosphor" Set)
Strictly limited to mimic specific hardware eras.

*   **E-ink (The Paper Mode):**
    *   `#000000` (Ink)
    *   `#FFFFFF` (Paper)
    *   `#AAAAAA` (Ghosting/Previous State)
*   **LEDs / Web (The Terminal Mode):**
    *   **Base:** Deep Black (`#050505`)
    *   **Signal Colors:**
        *   *Amber-500* (`#FFB000`) - Warning / Processing
        *   *Emerald-500* (`#00FF41`) - OK / Idle
        *   *Cyan-500* (`#00FFFF`) - Network / Data Flow
        *   *Ruby-500* (`#FF0033`) - Critical / Divergence

---

## 3. Data Visualization Metaphors

We replace standard dashboard widgets with "Generative Art" metaphors.

### 3.1 Status = "Entropy Grid" (The Schotter Metaphor)
*   **Concept:** A grid of 16 squares (representing the 16 LEDs/services).
*   **Visual:**
    *   **Healthy:** Perfectly aligned grid.
    *   **Activity:** Squares "breathe" (scale up/down slightly) or ripple.
    *   **Warning:** Squares rotate slightly (random -5° to +5°).
    *   **Critical:** Squares scatter (displacement + rotation), breaking the grid structure.

### 3.2 Time Series = "Floating Horizon" (The Johnson Metaphor)
*   **Concept:** Instead of a single line chart moving left-to-right, stack lines vertically to create a 3D landscape.
*   **Visual:** 
    *   New data draws a "ridge" in the foreground.
    *   Old data is pushed "back" (up the Y-axis) and hidden behind the new ridge.
    *   High activity creates "mountains"; silence creates "plains."

### 3.3 Loading / Processing = "The Loom"
*   **Concept:** Animating the construction of the view.
*   **Visual:** 
    *   Don't fade in. **Scan in.**
    *   Draw the UI from Top-Left to Bottom-Right, or "interlace" it (draw odd lines, then even lines).
    *   Show the "cursor" or "print head" location during updates.

---

## 4. Component Implementation Guide

### 4.1 The "Punch Card" Container
Used for grouping data on the Web Dashboard or E-ink layout.

*   **Shape:** Rectangular with a **cut corner** (top-right or top-left) to signify a punch card.
*   **Header:** A dense binary pattern or barcode at the top edge.
*   **Border:** 1px solid line (no shadow).

```
┌──────────────────────────/ /──┐
│ 0010110 SYSTEM_HEALTH   / /   │
├────────────────────────/ /────┤
│                               │
│   [ Content Goes Here ]       │
│                               │
└───────────────────────────────┘
```

### 4.2 The "Divergence" Meter
Instead of a gauge or percentage bar.

*   **Visual:** A **Lissajous figure** or a **Super-Ellipse**.
*   **Behavior:**
    *   *0% Divergence:* A perfect circle.
    *   *50% Divergence:* The shape distorts into a complex knot.
    *   *100% Divergence:* The shape becomes jagged, noisy, and unclosed ("frayed thread").

### 4.3 Background Textures
*   **Jacquard Noise:** 
    *   Generate a background texture using the `jacquard_noise` algorithm (simulating warp/weft errors) rather than random static.
    *   This gives the "empty" space a tactile, fabric-like quality.

---

## 5. Motion Principles (For LEDs & Web)

1.  **Step, Don't Glide:** Animations should feel mechanical. Use "stepped" easing curves (e.g., `steps(4)`) rather than smooth `ease-in-out`.
2.  **Persistence:** Mimic "phosphor decay" or "ghosting." When an element turns off, it shouldn't vanish instantly; it should leave a brief after-image or "burn-in" trace (cyan to dark blue to black).
3.  **The Sweep:** Updates happen in waves across the array (left-to-right or center-out), not instantly everywhere.

---

## 6. Implementation Checklist

- [ ] **E-ink Renderer:** Implement "Floating Horizon" chart for history.
- [ ] **E-ink Renderer:** Implement "Schotter" grid generator for current status.
- [ ] **Web Dashboard:** Create "Punch Card" CSS classes/components.
- [ ] **Web Dashboard:** Add "Scanline" and "CRT" overlay effects (optional).
- [ ] **LEDs:** Create a "Weave" animation pattern (pixels moving in cross-directions).
