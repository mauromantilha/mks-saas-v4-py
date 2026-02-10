# Re-export tests from parent tests.py module for backward compatibility
# This allows Django to find tests in both tests.py and tests/ directory
# See: https://docs.djangoproject.com/en/stable/topics/testing/overview/

from operational.tests.test_security import *  # noqa
