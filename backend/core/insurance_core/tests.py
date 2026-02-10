# Re-export tests from tests package
# Original test classes have been organized into tests/ directory
# to avoid import conflicts between tests.py and tests/ directory
from insurance_core.tests.test_insurers_api import *  # noqa: F401,F403
