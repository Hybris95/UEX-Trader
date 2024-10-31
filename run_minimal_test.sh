#!/bin/bash

# Enable core dumps
ulimit -c unlimited
echo '/tmp/core.%e.%p' | sudo tee /proc/sys/kernel/core_pattern

# Run minimal test with nogui
pytest -v test_nogui_minimal.py

# Run minimal test with xvfb
xvfb-run -a pytest -v test_gui_minimal.py
