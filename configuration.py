# -*- coding: utf-8 -*-
from trytond.model import fields
from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = ['SaleConfiguration']


class SaleConfiguration:
    __name__ = "sale.configuration"

    payment_authorize_on = fields.Selection(
        "get_authorize_options", "Payment Authorize On", required=True,
    )
    payment_capture_on = fields.Selection(
        "get_capture_options", "Payment Capture On", required=True,
    )

    @classmethod
    def __setup__(cls):
        super(SaleConfiguration, cls).__setup__()

        cls._error_messages.update({
            "auth_before_capture":
                "Payment authorization must happen before capture"
        })

    @classmethod
    def validate(cls, records):
        super(SaleConfiguration, cls).validate(records)

        for record in records:
            record.validate_payment_combination()

    def validate_payment_combination(self):
        if self.payment_authorize_on == 'sale_process' and \
                self.payment_capture_on == 'sale_confirm':
            self.raise_user_error("auth_before_capture")

    @staticmethod
    def default_payment_authorize_on():
        return "sale_confirm"

    @staticmethod
    def default_payment_capture_on():
        return "sale_process"

    @classmethod
    def get_authorize_options(cls):
        return [
            ("manual", "Manual"),
            ("sale_confirm", "Sale Confirm"),
            ("sale_process", "Sale Process"),
        ]

    @classmethod
    def get_capture_options(cls):
        return [
            ("manual", "Manual"),
            ("sale_confirm", "Sale Confirm"),
            ("sale_process", "Sale Process"),
        ]
