# -*- coding: utf-8 -*-
"""
    __init__

    :copyright: (c) 2014 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""
from trytond.pool import Pool
from sale import Sale, PaymentTransaction


def register():
    Pool.register(
        Sale,
        PaymentTransaction,
        module='sale_payment_gateway', type_='model'
    )
