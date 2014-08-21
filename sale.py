# -*- coding: utf-8 -*-
"""
    sale

    :copyright: (c) 2014 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""
from decimal import Decimal

from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction

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

    def _pay_using_credit_card(self, gateway, credit_card, amount):
        '''
        Complete using the given credit card and finish the transaction.

        :param gateway: Active record of the payment gateway to process card
        :param credit_card: A dictionary with either of the following
                            information sets:

                            * owner: name of the owner (unicode)
                            * number: number of the credit card
                            * expiry_month: expiry month (int or string)
                            * expiry_year: year as string
                            * cvv: the cvv number

                            In future this method will accept track1 and track2
                            as valid information.
        :param amount: Decimal amount to charge the card for
        '''
        TransactionUseCardWizard = Pool().get(
            'payment_gateway.transaction.use_card', type='wizard'
        )
        PaymentTransaction = Pool().get('payment_gateway.transaction')

        # Manual card based operation
        payment_transaction = PaymentTransaction(
            party=self.party,
            address=self.invoice_address,
            amount=amount,
            currency=self.currency,
            gateway=gateway,
            sale=self,
        )
        payment_transaction.save()

        use_card_wiz = TransactionUseCardWizard(
            TransactionUseCardWizard.create()[0]        # Wizard session
        )
        use_card_wiz.card_info.owner = credit_card['owner']
        use_card_wiz.card_info.number = credit_card['number']
        use_card_wiz.card_info.expiry_month = credit_card['expiry_month']
        use_card_wiz.card_info.expiry_year = credit_card['expiry_year']
        use_card_wiz.card_info.csc = credit_card['cvv']

        with Transaction().set_context(active_id=payment_transaction.id):
            use_card_wiz.transition_capture()

    def _pay_using_profile(self, payment_profile, amount):
        '''
        Complete the Checkout using a payment_profile. Only available to the
        registered users of the website.


        :param payment_profile: Active record of payment profile
        :param amount: Decimal amount to charge the card for
        '''
        PaymentTransaction = Pool().get('payment_gateway.transaction')

        if payment_profile.party != self.party:
            self.raise_user_error(
                "Payment profile'd owner is %s, but the customer is %s" % (
                    payment_profile.party.name,
                    self.party.name,
                )
            )

        payment_transaction = PaymentTransaction(
            party=self.party,
            address=self.invoice_address,
            payment_profile=payment_profile,
            amount=amount,
            currency=self.currency,
            gateway=payment_profile.gateway,
            sale=self,
        )
        payment_transaction.save()

        PaymentTransaction.capture([payment_transaction])


class PaymentTransaction:
    "Gateway Transaction"
    __name__ = 'payment_gateway.transaction'

    sale = fields.Many2One('sale.sale', 'Sale')
