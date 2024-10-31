#!/bin/bash

# Enable core dumps
ulimit -c unlimited
echo '/tmp/core.%e.%p' | sudo tee /proc/sys/kernel/core_pattern

# Run tests with xvfb
xvfb-run -a pytest -v test_minimal.py
