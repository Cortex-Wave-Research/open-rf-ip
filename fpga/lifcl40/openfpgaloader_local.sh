#!/usr/bin/env bash
# Locally extracted Ubuntu packages; this launcher performs only the requested action.
set -euo pipefail
project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
loader_root="$project_root/build/lifcl40/tools/openfpgaloader"
export LD_LIBRARY_PATH="$loader_root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$loader_root/usr/bin/openFPGALoader" "$@"
