import logging

from django.test import SimpleTestCase

from tenancy.logging import MaskCPFCNPJFilter, mask_cpf_cnpj


class MaskCPFCNPJTests(SimpleTestCase):
    def test_masks_formatted_values(self):
        msg = "cpf=123.456.789-09 cnpj=12.345.678/0001-90"
        masked = mask_cpf_cnpj(msg)
        self.assertNotIn("123.456.789-09", masked)
        self.assertNotIn("12.345.678/0001-90", masked)
        self.assertIn("***CPF***", masked)
        self.assertIn("***CNPJ***", masked)

    def test_logging_filter_masks_message(self):
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="cpf=%s",
            args=("123.456.789-09",),
            exc_info=None,
        )
        MaskCPFCNPJFilter().filter(record)
        self.assertIn("***CPF***", record.msg)
        self.assertNotIn("123.456.789-09", record.msg)
