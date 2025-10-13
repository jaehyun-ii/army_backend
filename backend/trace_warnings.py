#!/usr/bin/env python3
"""
Trace where Pydantic model_ field warnings come from
"""
import warnings
import traceback
import sys

def warning_with_traceback(message, category, filename, lineno, file=None, line=None):
    """Show warning with full traceback"""
    if 'model_' in str(message):
        log = file if hasattr(file, 'write') else sys.stderr
        traceback.print_stack(file=log)
        log.write(f'\n{filename}:{lineno}: {category.__name__}: {message}\n\n')

# Replace default warning handler
warnings.showwarning = warning_with_traceback
warnings.filterwarnings('always', category=UserWarning)

# Now import the app
print("Importing app modules...")
sys.path.insert(0, 'app')

try:
    # Import main app to trigger all module loads
    from app import main
    print("App imported successfully!")
except Exception as e:
    print(f"Error importing app: {e}")
    traceback.print_exc()
