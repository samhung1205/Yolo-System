#!/usr/bin/env bash
# Install custom YOLO modules into the active ultralytics environment.
# Usage:
#   conda activate yolo-backend
#   bash models/custom_modules/install_to_ultralytics.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ULTRA_MODULES="$(python -c "import ultralytics, os; print(os.path.join(os.path.dirname(ultralytics.__file__), 'nn', 'modules'))")"

echo "ultralytics modules dir: $ULTRA_MODULES"

# 1. Copy ASFFHead.py
cp "$SCRIPT_DIR/ASFFHead.py" "$ULTRA_MODULES/ASFFHead.py"
echo "✅ Copied ASFFHead.py"

# 2. Inject import into __init__.py if not already present
INIT_FILE="$ULTRA_MODULES/__init__.py"
if ! grep -q "from .ASFFHead import" "$INIT_FILE"; then
    # Insert after the docstring block, before the first 'from .block' line
    sed -i '' 's/^from \.block import/from .ASFFHead import DetectASFF, SegmentASFF\n\nfrom .block import/' "$INIT_FILE"
    echo "✅ Patched __init__.py"
else
    echo "ℹ️  __init__.py already patched, skipping"
fi

# 3. Verify
python -c "from ultralytics.nn.modules import DetectASFF, SegmentASFF; print('✅ Import OK:', DetectASFF)"
