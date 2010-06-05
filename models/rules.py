"""
Rules for evaluation
"""
#########################################################################
#                                                                       #
# Copyright (C) 2010 Open Labs Business Solutions                       #
#                                                                       #
#This program is free software: you can redistribute it and/or modify   #
#it under the terms of the GNU General Public License as published by   #
#the Free Software Foundation, either version 3 of the License, or      #
#(at your option) any later version.                                    #
#                                                                       #
#This program is distributed in the hope that it will be useful,        #
#but WITHOUT ANY WARRANTY; without even the implied warranty of         #
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the          #
#GNU General Public License for more details.                           #
#                                                                       #
#You should have received a copy of the GNU General Public License      #
#along with this program.  If not, see <http://www.gnu.org/licenses/>.  #
#########################################################################

from osv import osv, fields

class PromotionsRules(osv.osv):
    "Promotion Rules"
    _name = "promos.rules"
    _description = __doc__
    _order = 'sequence'
    
    _columns = {
        'name':fields.char('Name of Rule', size=50, required=True),
        'description':fields.text('Description'),
        'active':fields.boolean('Active'),
        'shop':fields.many2one('sale.shop', 'Shop', required=True),
        'partner_categories':fields.many2many(
                  'res.partner.category',
                  'rule_partner_rel',
                  'category_id',
                  'rule_id',
                  string="Partner Categories",
                  help="Applicable to all if none is selected"
                                              ),
        'coupon_code':fields.char('Coupon Code', size=20),
        'uses_per_coupon':fields.integer('Uses per Coupon'),
        'uses_per_partner':fields.integer('Uses per Partner'),
        'from_date':fields.datetime('From Date'),
        'to_date':fields.datetime('To Date'),
        'sequence':fields.integer('Sequence', required=True),
        'conditions':fields.one2many(
                     'promos.rules.conditions',
                     'rule',
                     string="Conditions"
                         ),
        'actions':fields.one2many(
                    'promos.rules.actions',
                    'rule',
                    string="Actions"
                        )
    }
PromotionsRules()


class PromotionsRulesConditions(osv.osv):
    "Conditions evaluated for rules"
    _name = "promos.rules.conditions"
    _description = __doc__
    _order = 'sequence'
    _columns = {
        'rule':fields.many2one('promos.rules', 'Rule'),
        'sequence':fields.integer('Sequence', required=True),
        'name':fields.char('Condition Name', size=50,
                           help="Leave blank for auto generation"),
        'logic':fields.selection([
                            ('and', 'All'),
                            ('or', 'Any'),
                                  ], string="Logic", required=True),
        'expected_logic_result':fields.selection([
                            ('True', 'True'),
                            ('False', 'False')
                                    ], string="Output", required=True),
        'expressions':fields.one2many(
                            'promos.rules.conditions.exps',
                            'condition',
                            string='Expressions/Conditions'
                            )
    }
    _defaults = {
        'logic':lambda * a:'and',
        'expected_logic_result': lambda * a:'True'
    }
PromotionsRulesConditions()


class PromotionsRulesConditionsExprs(osv.osv):
    "Expressions for conditions"
    _name = 'promos.rules.conditions.exps'
    _description = __doc__
    _order = "sequence"
    _rec_name='serialised_expr'
    _columns = {
        'sequence':fields.integer('Sequence'),
        'serialised_expr':fields.char('Expression', size=255),
        'condition': fields.many2one('promos.rules.conditions',
                                     'Condition')
    }
    _defaults = {
    }
PromotionsRulesConditionsExprs()


class PromotionsRulesActions(osv.osv):
    "Promotions actions"
    _name = 'promos.rules.actions'
    _description = __doc__
    _columns = {
        'rule':fields.many2one('promos.rules', 'Rule'),
    }
PromotionsRulesActions()
