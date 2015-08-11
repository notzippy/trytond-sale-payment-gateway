# -*- coding: utf-8 -*-
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
