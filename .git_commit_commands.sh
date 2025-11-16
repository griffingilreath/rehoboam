#!/bin/bash
# Git commands for committing and pushing Rehoboam updates
# Run this script or copy/paste commands individually

set -e  # Exit on error

echo "=== Rehoboam Git Commit & Push ==="
echo ""

# 1. Show current status
echo "📋 Current status:"
git status --short
echo ""

# 2. Show what will be committed (optional review)
echo "📝 Reviewing changes..."
git diff --stat
echo ""

# 3. Stage all changes (modified + new files)
echo "➕ Staging all changes..."
git add -A
echo "✓ All changes staged"
echo ""

# 4. Show what's staged
echo "📦 Staged changes:"
git status --short
echo ""

# 5. Commit with descriptive message
echo "💾 Committing changes..."
git commit -m "Add LED panel testing and HA helpers export tools

- Add devtools/test_led_panel.py: interactive LED test/calibration tool
  - Lights each LED sequentially for port mapping
  - Quick connection test mode
  - Integrated into setup wizard

- Add CLI export-ha-config command to devtools/cli.py
  - Export ready-to-use Home Assistant helpers configuration
  - Option to merge current values from led_config.json
  - Preserves comments and structure

- Add docs/home_assistant_helpers.example.yaml
  - Complete HA helper configuration for all 16 LEDs
  - Pre-configured with R1-R8, S1-S8 defaults
  - Ready to copy into Home Assistant

- Update documentation
  - README: LED panel testing section, CLI tool docs
  - docs/home_assistant.md: quick start with export command
  - Service READMEs: references to new tools

- Update led_encoder_service
  - Auto-detection for Teensy serial port (serial_device: auto)
  - Improved error handling and reconnection logic"
echo "✓ Changes committed"
echo ""

# 6. Push to GitHub
echo "🚀 Pushing to GitHub..."
git push origin main
echo ""

echo "✅ Done! Changes pushed to https://github.com/griffingilreath/rehoboam"
echo ""
echo "View your changes at:"
echo "  https://github.com/griffingilreath/rehoboam/commits/main"

