# Copy this into the WSGI file on PythonAnywhere's Web tab (it replaces everything there).
# Change YOUR_USERNAME to your PythonAnywhere username.

import sys

path = "/home/YOUR_USERNAME/AnimoNav-SourceCode/Backend-DB"
if path not in sys.path:
    sys.path.insert(0, path)

from app import app as application  # noqa: E402
