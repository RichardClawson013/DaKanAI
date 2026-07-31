#!/bin/bash
cd "$(dirname "$(readlink -f "$0")")"
source .venv/bin/activate
python monitor.py
