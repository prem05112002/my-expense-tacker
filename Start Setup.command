#!/bin/bash
# Expense Tracker — Setup Wizard
# Double-click this file on Mac/Linux to run the setup wizard.

# Move to the project root (same folder as this script)
cd "$(dirname "$0")"

# Run the setup wizard
python3 setup/setup.py
