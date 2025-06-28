#!/bin/bash
# Script to ensure correct token is used

# Unset system environment variable that overrides .env
unset ZAGADKA_TOKEN

# Add this to your shell config to make it permanent:
echo "# Fix for ZAGADKA_TOKEN override"
echo "unset ZAGADKA_TOKEN" 

# To make permanent, run:
# echo "unset ZAGADKA_TOKEN" >> ~/.bashrc