# -*- coding: utf-8 -*-
"""
    sale

    :copyright: (c) 2014 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""
from decimal import Decimal

from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval

__all__ = ['Sale', 'PaymentTransaction']
__metaclass__ = PoolMeta


class Sale:
    'Sale'
    __name__ = 'sale.sale'

    payment_required_to_process = fields.Boolean(
        "Payment Required To Process",
        states={'readonly': Eval('state') != 'draft'}
    )
    amount_payment_received = fields.Function(
        fields.Numeric("Payment Received"), "get_payment"
    )
    amount_payment_in_progress = fields.Function(
        fields.Numeric("Payment In Progress"), "get_payment"
    )
    amount_to_receive = fields.Function(
        fields.Numeric("Amount to Received"), "get_payment"
    )
    gateway_transactions = fields.One2Many(
        'payment_gateway.transaction', 'sale', 'Gateway Transactions',
        readonly=True,
    )

    def get_payment(self, name):
        """
        Getter method for 'payment_received', 'payment_in_progress' and
        'balance_to_received' fields.

        :param name: name of the field
        """
        # TODO: Do currency converstions
        sum_transactions = lambda txns: sum((txn.amount for txn in txns))

        if name == 'amount_payment_received':
            transactions = filter(
                lambda txn: txn.state in ('completed', 'posted'),
                self.gateway_transactions
            )
            return Decimal(sum_transactions(transactions))

        elif name == 'amount_payment_in_progress':
            transactions = filter(
                lambda txn: txn.state in ('authorized', 'in-progress'),
                self.gateway_transactions
            )
            return Decimal(sum_transactions(transactions))

        elif name == 'amount_to_receive':
            return self.total_amount - (
                self.amount_payment_in_progress + self.amount_payment_received
            )


class PaymentTransaction:
    "Gateway Transaction"
    __name__ = 'payment_gateway.transaction'

    sale = fields.Many2One('sale.sale', 'Sale')
