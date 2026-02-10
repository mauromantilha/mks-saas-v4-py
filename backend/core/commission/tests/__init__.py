# Re-export tests from submodules
# This allows Django to properly discover and run tests
from commission.tests.test_engine import *  # noqa
from commission.tests.test_models import *  # noqa
