# -*- coding: utf-8 -*-
from decimal import Decimal

from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Not, If
from trytond.transaction import Transaction
from trytond import backend

from sql.functions import Trim, Substring
from sql.operators import Concat

__all__ = ['Payment']
__metaclass__ = PoolMeta


class Payment(ModelSQL, ModelView):
    'Payment'
    __name__ = 'sale.payment'

    sequence = fields.Integer('Sequence', required=True, select=True)
    party = fields.Function(
        fields.Many2One('party.party', 'Party'),
        getter='on_change_with_party'
    )
    amount = fields.Numeric(
        'Amount', required=True, digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'],
    )
    sale = fields.Many2One(
        'sale.sale', 'Sale', required=True, select=True, ondelete='CASCADE'
    )
    gateway = fields.Many2One(
        'payment_gateway.gateway', 'Gateway', required=True,
        ondelete='RESTRICT', select=True,
    )
    payment_transactions = fields.One2Many(
        'payment_gateway.transaction', 'sale_payment', 'Payment Transactions',
        readonly=True
    )
    currency_digits = fields.Function(
        fields.Integer('Currency Digits'),
        getter='on_change_with_currency_digits'
    )
    amount_consumed = fields.Function(
        fields.Numeric(
            'Amount Consumed', digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits'],
        ), 'get_amount'
    )
    amount_available = fields.Function(
        fields.Numeric(
            'Amount Remaining', digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits'],
        ), 'get_amount'
    )
    amount_authorized = fields.Function(
        fields.Numeric(
            'Amount Authorized', digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits'],
        ), 'get_amount'
    )
    amount_captured = fields.Function(
        fields.Numeric(
            'Amount Captured', digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits'],
        ), 'get_amount'
    )
    payment_profile = fields.Many2One(
        'party.payment_profile', 'Payment Profile',
        domain=[
            ('party', '=', Eval('party')),
            ('gateway', '=', Eval('gateway')),
        ],
        states={
            'required': Eval('method') == 'credit_card',
            'invisible': Eval('method') != 'credit_card',
        },
        ondelete='RESTRICT', depends=['party', 'gateway', 'method'],
    )
    method = fields.Function(fields.Char('Method'), 'get_method')
    provider = fields.Function(fields.Char('Provider'), 'get_provider')
    reference = fields.Char(
        'Reference', states={
            'invisible': Not(Eval('method') == 'manual'),
        }
    )
    description = fields.Function(
        fields.Char('Description'), 'get_payment_description'
    )

    company = fields.Function(
        fields.Many2One(
            'company.company', 'Company',
            domain=[
                ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                    Eval('context', {}).get('company', -1)),
            ],
        ),
        getter='on_change_with_company',
        searcher='search_company',
    )
    credit_account = fields.Many2One(
        'account.account', 'Credit Account', required=True
    )

    def get_rec_name(self, name):
        if self.payment_profile:
            return "%s - %s - %s" % (
                self.gateway, self.payment_profile, self.amount
            )
        return "%s - %s" % (self.gateway, self.amount)

    def get_provider(self, name=None):
        """
        Return the gateway provider based on the gateway
        """
        return self.gateway and self.gateway.provider or None

    def get_method(self, name=None):
        """
        Return the method based on the gateway
        """
        return self.gateway and self.gateway.method or None

    @classmethod
    def __register__(cls, module_name):
        Party = Pool().get('party.party')
        Sale = Pool().get('sale.sale')
        Model = Pool().get('ir.model')
        ModelField = Pool().get('ir.model.field')
        Property = Pool().get('ir.property')
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

        migration_needed = False
        if not table.column_exist('credit_account'):
            migration_needed = True

        super(Payment, cls).__register__(module_name)

        if migration_needed and not Pool.test:
            # Migration
            # Set party's receivable account as the credit_account on
            # sale payments
            payment = cls.__table__()
            party = Party.__table__()
            property = Property.__table__()
            sale = Sale.__table__()

            account_model, = Model.search([
                ('model', '=', 'party.party'),
            ])
            account_receivable_field, = ModelField.search([
                ('model', '=', account_model.id),
                ('name', '=', 'account_receivable'),
                ('ttype', '=', 'many2one'),
            ])

            update = payment.update(
                columns=[payment.credit_account],
                values=[
                    Trim(
                        Substring(property.value, ',.*'), 'LEADING', ','
                    ).cast(cls.credit_account.sql_type().base)
                ],
                from_=[sale, party, property],
                where=(
                    payment.sale == sale.id
                ) & (
                    sale.party == party.id
                ) & (
                    property.res == Concat(Party.__name__ + ',', party.id)
                ) & (
                    property.field == account_receivable_field.id
                ) & (
                    property.company == sale.company
                )

            )
            cursor.execute(*update)

    @classmethod
    def __setup__(cls):
        super(Payment, cls).__setup__()

        cls._error_messages.update({
            'cannot_delete_payment':
                "Payment cannot be deleted as placeholder for amount consumed "
                "has already been consumed.",
        })

        cls.credit_account.domain = [
            ('company', '=', Eval('company', -1)),
            ('kind', 'in', cls._credit_account_domain())
        ]
        cls.credit_account.depends = ['company']

    @fields.depends('sale')
    def on_change_with_credit_account(self, name=None):
        if self.sale and self.sale.party:
            return self.sale.party.account_receivable and \
                self.sale.party.account_receivable.id

    @fields.depends('sale')
    def on_change_with_company(self, name=None):
        return self.sale and self.sale.company.id or None

    @fields.depends('sale')
    def on_change_with_party(self, name=None):
        return self.sale and self.sale.party.id or None

    @fields.depends('sale')
    def on_change_with_currency_digits(self, name=None):
        if self.sale.currency:
            return self.sale.currency.digits
        return 2

    @classmethod
    def search_company(cls, name, clause):
        """
        Searcher for field delivery_date
        """
        return [('sale.company', ) + tuple(clause[1:])]

    def get_amount(self, name):
        """Getter method for fetching amounts.
        """
        PaymentTransaction = Pool().get('payment_gateway.transaction')

        payment_transactions = PaymentTransaction.search([
            ('sale_payment', '=', self.id)
        ])
        sum_transactions = lambda txns: sum((txn.amount for txn in txns))

        if name == "amount_consumed":
            return sum_transactions(filter(
                lambda t: t.state in ('authorized', 'completed', 'posted'),
                payment_transactions
            ))

        elif name == "amount_authorized":
            return sum_transactions(filter(
                lambda t: t.state == 'authorized',
                payment_transactions
            ))

        elif name == "amount_captured":
            return sum_transactions(filter(
                lambda t: t.state in ('completed', 'posted'),
                payment_transactions
            ))

        elif name == "amount_available":
            return max(self.amount - self.amount_consumed, Decimal('0'))

    @staticmethod
    def default_sequence():
        return 10

    @classmethod
    def cancel(cls, payments):
        """
        Cancel all payment transactions related to payment
        """
        PaymentTransaction = Pool().get('payment_gateway.transaction')

        payment_transactions = []
        for payment in payments:
            payment_transactions.extend(payment.payment_transactions)

        PaymentTransaction.cancel(payment_transactions)

    def _create_payment_transaction(self, amount, description):
        """Creates an active record for gateway transaction.
        """
        PaymentTransaction = Pool().get('payment_gateway.transaction')
        Date = Pool().get('ir.date')

        return PaymentTransaction(
            description=description or 'Auto charge from sale',
            date=Date.today(),
            party=self.sale.party,
            credit_account=self.credit_account,
            payment_profile=self.payment_profile,
            address=(
                self.payment_profile and
                self.payment_profile.address or self.sale.invoice_address
            ),
            amount=self.sale.currency.round(amount),
            currency=self.sale.currency,
            gateway=self.gateway,
            sale_payment=self.id,
            provider_reference=self.reference,
        )

    def authorize(self):
        """Authorize all the transactions associated with the payment.
        """
        PaymentTransaction = Pool().get('payment_gateway.transaction')

        PaymentTransaction.authorize(
            filter(
                lambda txn: txn.state == 'draft',
                self.payment_transactions
            )
        )

    def capture(self):
        """
        Captures the given amount from this transaction
        """
        PaymentTransaction = Pool().get('payment_gateway.transaction')

        PaymentTransaction.capture(
            filter(
                lambda txn: txn.state in ('draft', 'authorized', 'in-progress'),
                self.payment_transactions
            )
        )

    @classmethod
    def delete(cls, payments):
        """
        Delete a payment only if there is no amount consumed
        """
        for payment in payments:
            if payment.amount_consumed:
                cls.raise_user_error("cannot_delete_payment")

        super(Payment, cls).delete(payments)

    def get_payment_description(self, name):
        """
        Return a short description of the sale payment
        This can be used in documents to show payment details
        """
        if self.method == 'manual':
            return "Paid by Cash"
        elif self.method == 'credit_card':
            return (
                "Paid by Card " + "(" + ("xxxx " * 3) +
                self.payment_profile.last_4_digits + ")"
            )

    @classmethod
    def _credit_account_domain(cls):
        """
        Return a list of account kind
        """
        return ['receivable']
