# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#
#    Copyright (c) 2013-2015 Noviat nv/sa (www.noviat.com).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp import models, fields, api, _
import openerp.addons.decimal_precision as dp
import time
from datetime import datetime, timedelta
import logging
_logger = logging.getLogger(__name__)

BaseTaxCodesIn = ['81', '82', '83', '84', '85', '86', '87', '88']
BaseTaxCodesOut = ['00', '01', '02', '03', '44', '45', '46', '46L', '46T',
                   '47', '48', '48s44', '48s46L', '48s46T', '49']
BaseTaxCodes = BaseTaxCodesIn + BaseTaxCodesOut


class account_invoice(models.Model):
    _inherit = 'account.invoice'

    @api.one
    @api.depends('amount_total', 'amount_tax')
    def _amount_cd(self):
        if self.company_id.country_id.code == 'BE':
            pct = self.percent_cd
            if pct:
                self.amount_cd = self.amount_untaxed * (1 - pct/100) \
                    + self.amount_tax

    # To DO : hide Cash Discount fields from User Interface
    # when company country != 'BE'

    percent_cd = fields.Float(
        string='Cash Discount (%)',
        readonly=True, states={'draft': [('readonly', False)]},
        help="Add Cash Discount according to Belgian Tax Legislation.")
    amount_cd = fields.Float(
        string='Cash Discount', digits=dp.get_precision('Account'),
        compute='_amount_cd',
        help="Total amount to pay with Cash Discount")
    date_cd = fields.Date(
        string='Cash Discount Date',
        help="Due Date for Cash Discount Conditions")

    @api.multi
    def action_date_assign(self):
        super(account_invoice, self).action_date_assign()
        for inv in self:
            if inv.type == 'out_invoice' and inv.percent_cd:
                if not inv.date_cd:
                    term_cd = inv.company_id.out_inv_cd_term
                    if inv.date_invoice:
                        date_invoice = inv.date_invoice
                    else:
                        date_invoice = time.strftime('%Y-%m-%d')
                    date_invoice = datetime.strptime(
                        date_invoice, '%Y-%m-%d').date()
                    date_cd = date_invoice + timedelta(term_cd)
                    inv.write({'date_cd': date_cd.isoformat()})
        return True

    @api.multi
    def onchange_payment_term_date_invoice(
            self, payment_term_id, date_invoice):
        res = super(account_invoice, self).onchange_payment_term_date_invoice(
            payment_term_id, date_invoice)
        reset_date_cd = {'date_cd': False}
        if not res.get('value'):
            res['value'] = reset_date_cd
        else:
            res['value'].update(reset_date_cd)
        return res

    @api.multi
    def finalize_invoice_move_lines(self, move_lines):
        for invoice in self:
            pct = invoice.percent_cd
            if pct and invoice.company_id.country_id.code == 'BE':
                tax_codes = self.env['account.tax.code'].search(
                    [('code', 'in', BaseTaxCodes)])
                if invoice.type in ['out_invoice', 'out_refund']:
                    cd_account_id = invoice.company_id.out_inv_cd_account_id.id
                else:
                    cd_account_id = invoice.company_id.in_inv_cd_account_id.id
                multiplier = 1 - pct / 100
                cd_line = False
                cd_vals = {
                    'name': _('Cash Discount'),
                    'account_id': cd_account_id,
                    'debit': 0.0,
                    'credit': 0.0,
                    'partner_id': invoice.partner_id.id,
                    # no foreign currency support since
                    # extra Cash Discount line
                    #  only applies to Belgian transactions
                    'currency_id': False,
                }
                for line in move_lines:
                    vals = line[2]
                    if vals['tax_code_id'] in [x.id for x in tax_codes]:
                        cd_line = True
                        # round on dp2 since always euro
                        if vals.get('debit'):
                            debit = round(vals['debit'], 2)
                            vals['debit'] = round(debit * multiplier, 2)
                            cd_vals['debit'] += debit - vals['debit']
                        if vals.get('credit'):
                            credit = round(vals['credit'], 2)
                            vals['credit'] = round(credit * multiplier, 2)
                            cd_vals['credit'] += credit - vals['credit']
                        vals['tax_amount'] = vals.get('tax_amount') \
                            and vals['tax_amount'] * multiplier
                if cd_line:
                    move_lines.append((0, 0, cd_vals))
        return move_lines

    @api.model
    def _prepare_refund(self, invoice, date=None, period_id=None,
                        description=None, journal_id=None):
        res = super(account_invoice, self)._prepare_refund(
            invoice, date, period_id, description, journal_id)
        res['reference_type'] = self.reference_type
        res['percent_cd'] = self.percent_cd
        return res


class account_invoice_tax(models.Model):
    _inherit = 'account.invoice.tax'

    # change compute method according to belgian regulation for Cash Discount
    def compute(self, invoice):
        tax_grouped = super(account_invoice_tax, self).compute(invoice)
        # _logger.warn('tax_grouped=%s', tax_grouped)
        if invoice.company_id.country_id.code == 'BE':
            tax_codes = self.env['account.tax.code'].search(
                [('code', 'in', BaseTaxCodes)])
            atc_ids = [x.id for x in tax_codes]
            pct = invoice.percent_cd
            if pct:
                multiplier = 1 - pct / 100
                for k in tax_grouped.keys():
                    if k[1] in atc_ids:
                        tax_grouped[k].update({
                            'base': multiplier * tax_grouped[k]['base'],
                            'amount': multiplier * tax_grouped[k]['amount'],
                            'base_amount':
                                multiplier * tax_grouped[k]['base_amount'],
                            'tax_amount':
                                multiplier * tax_grouped[k]['tax_amount'],
                            })
        return tax_grouped
