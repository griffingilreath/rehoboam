#!/bin/bash
set -e

echo "Running Generative Scene Smoke Test..."

# Create dummy data
echo '{"house_activity": 0.5, "daylight": 0.8, "security_tension": 0.1}' > data/generative_channels.json

# Clean previous output
rm -rf /tmp/epaper_frames

# Run for 10 seconds, then kill
timeout 10s python3 -m epaper.cli.main --scene generative --backend fake --log-level DEBUG || true

# Cleanup dummy data
rm -f data/generative_channels.json

if [ -d "/tmp/epaper_frames" ]; then
    count=$(ls /tmp/epaper_frames/*.png 2>/dev/null | wc -l)
    if [ "$count" -gt 0 ]; then
        echo "Success: Generated $count frames in /tmp/epaper_frames"
        exit 0
    else
        echo "Failure: No frames generated"
        exit 1
    fi
else
    echo "Failure: Output directory not created"
    exit 1
fi
