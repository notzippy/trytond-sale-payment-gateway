# -*- coding: utf-8 -*-
"""
    __init__

    :copyright: (c) 2014 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""
from trytond.pool import Pool
from sale import Sale, PaymentTransaction, AddSalePaymentView, AddSalePayment
from payment import Payment
from configuration import SaleConfiguration


def register():
    Pool.register(
        Payment,
        SaleConfiguration,
        Sale,
        PaymentTransaction,
        AddSalePaymentView,
        module='sale_payment_gateway', type_='model'
    )
    Pool.register(
        AddSalePayment,
        module='sale_payment_gateway', type_='wizard'
    )
