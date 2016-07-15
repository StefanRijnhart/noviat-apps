#!/usr/bin/env python2
# coding: utf-8
# Get the Full lists of current codes in xlsx format from
# https://www.nbb.be/nl/betalingssystemen/betalingsstandaarden/bankidentificatiecodes
# then run ./convert_bics.py *.xlsx > ../data/be_banks.xml

import codecs
import locale
import pyexcel
import re
import sys
from xml.sax.saxutils import escape

# http://wiki.python.org/moin/PrintFails
sys.stdout = codecs.getwriter(
    locale.getpreferredencoding())(sys.stdout)
sys.stderr = codecs.getwriter(
    locale.getpreferredencoding())(sys.stderr)

# Print footer
print """\
<?xml version="1.0" encoding="utf-8"?>
<openerp>
    <data noupdate="1">

        <!-- res.bank -->
"""

country_map = {'gb': 'uk'}

# Generate content
rows = pyexcel.get_array(file_name=sys.argv[1])
skip = 2
for row in rows:
    if skip:
        skip -= 1
        continue
    bic = row[1].replace(' ', '').upper()
    match = re.match('[A-Z]{4}([A-Z]{2})[A-Z0-9]{2}([A-Z0-9]{3})?', bic)
    if not match:
        continue
    country = match.group(1).lower()
    country = country_map.get(country, country)
    print u"""\
        <record id="bank_be_{code}" model="res.bank">
            <field name="code">{code}</field>
            <field name="bic">{bic}</field>
            <field name="name">{name}</field>
            <field name="country" ref="base.{country}"/>
        </record>""".format(code=row[0], bic=bic,
                            name=escape(row[2] or row[3]),
                            country=country)

# Print header
print """\

    </data>
</openerp>"""
