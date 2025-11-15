# Teensy LED Status Panel

A modular project for driving a rack-mounted LED status display with a Teensy 4.x microcontroller and a host supervisor (Raspberry Pi, Jetson Nano, or Mac mini). The codebase is organized for clean separation between firmware animations, host side monitoring logic, and shared protocol documentation.

## Repository Layout

- `docs/` – architecture notes, state diagrams, communication protocol references.
- `firmware/` – Teensy source, header, and test code organized by role.
- `host/` – host-side supervisor scripts and services for monitoring systems.
- `shared/` – shared assets such as protocol definitions or lookup tables.
- `tools/` – auxiliary scripts for development, flashing, or diagnostics.

See `docs/architecture.md` for a deeper breakdown of the system design.
