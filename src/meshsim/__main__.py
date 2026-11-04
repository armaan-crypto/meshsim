"""Allow ``python -m meshsim`` as an alternative to the ``meshsim`` command."""

import sys

from .cli import main

sys.exit(main())
