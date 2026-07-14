#!/usr/bin/env bash
# Deprecated compatibility entry point.
#
# Custom checkpoint modules are loaded from repository-controlled source by
# backend/app/integrations/legacy_checkpoint_compat.py.  Modifying the active
# Ultralytics site-packages would make deployments environment-dependent.

set -eu

echo "No installation is required."
echo "The FastAPI backend loads approved custom checkpoint modules from the repository."
echo "Do not copy or inject files into Ultralytics site-packages."
