"""
Rules for evaluation

This design is inspired by magento
"""
#########################################################################
#                                                                       #
# Copyright (C) 2010 Open Labs Business Solutions                       #
# Special Credit: Yannick Buron for design evaluation                   #
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
        'name':fields.char('Promo Name', size=50, required=True),
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
                            'promotion',
                            string='Expressions/Conditions'
                            ),
        'actions':fields.one2many(
                    'promos.rules.actions',
                    'rule',
                    string="Actions"
                        )
    }
    _defaults = {
        'logic':lambda * a:'and',
        'expected_logic_result':lambda * a:'True'
    }
    
    def evaluate(self, cursor, user, promo_id, order_id, context=None):
        """
        Evaluates if a promotion is valid
        TODO: Doc this
        @param promo_id: id of the promotion
        @param order_id: id of the sale order
        """
        if not context:
            context = {}
        promotion_rule = self.browse(cursor, user, promo_id, context)
        order = self.pool.get('sale.order').browse(cursor, user,
                                                   order_id, context=context)
        expected_result = eval(promotion_rule.expected_logic_result)
        logic = eval(promotion_rule.logic)
        #Evaluate each expression
        for expression in promotion_rule.expressions:
            result = expression.evaluate(cursor, user,
                                         expression, object, context)
            #For and logic, any False is completely false
            if (not (result == expected_result)) and (logic == 'and'):
                return False
            #For OR logic any True is completely True
            if (result == expected_result) and (logic=='or'):
                return True
            #If stop_further is given, then execution stops  if the
            #condition was satisfied
            if (result == expected_result) and expression.stop_further:
                return True
        if logic == 'and':
            #If control comes here for and logic, then all conditions were 
            #satisfied
            return True
        else:
            #if control comes here for OR logic, none were satisfied
            return False
        
PromotionsRules()


class PromotionsRulesConditionsExprs(osv.osv):
    "Expressions for conditions"
    _name = 'promos.rules.conditions.exps'
    _description = __doc__
    _order = "sequence"
    _rec_name = 'serialised_expr'
    
    def _get_attributes(self, cursor, user, ids=None, context=None):
        """
        Gets the attributes in predefined format
        """
        return [
                ('subtotal', 'Sub Total'),
                ('tot_item_qty', 'Total Items Quantity'),
                ('tot_weight', 'Total Weight'),
                ('tot_item_qty', 'Total Items Quantity'),
                ('custom', 'Custom domain expression')
                ]
    
    def _get_comparators(self, cursor, user, ids=None, context=None):
        """
        Gets the attributes in predefined format
        """
        return [
#                ('is', 'is'),
#                ('isnot', 'is not'),
                ('==', 'equals'),
                ('!=', 'not equal to'),
                ('>', 'greater than'),
                ('>=', 'greater than or equal to'),
                ('<', 'less than'),
                ('<=', 'less than or equal to'),
                ('in', 'is in'),
                ('not in', 'is not in')
                ]
    
    _columns = {
        'sequence':fields.integer('Sequence'),
        'attribute':fields.selection(_get_attributes,
                                     'Attribute', required=True),
        'comparator':fields.selection(_get_comparators,
                                      'Comparator', required=True),
        'value':fields.char('Value', size=100),
        'serialised_expr':fields.char('Expression', size=255),
        'promotion': fields.many2one('promos.rules',
                                     'Promotion'),
        'stop_further':fields.boolean('Stop further checks')
        
    }
    _defaults = {
        'comparator': lambda * a:'==',
        'stop_further': lambda * a: '1'
    }
        
    def serialise(self, attribute, comparator, value):
        """
        Constructs an expression from the entered values
        which can be quickly evaluated
        TODO: Doc this
        """
        if attribute == 'custom':
            return value
        return "object.%s %s %s" % (
                                    attribute,
                                    comparator,
                                    value) 
        
    def evaluate(self, cursor, user,
                 expression, object, context=None):
        """
        Evaluates the expression in given environment
        TODO: Doc the rest
        @param expression_id: Browserecord of expression
        @param object: BrowseRecord of sale order
        @return: True if evaluation succeeded
        """
        return eval(expression.serialised_expr) 
    
    def create(self, cursor, user, vals, context=None):
        """
        Serialise before save
        """
        vals['serialised_expr'] = self.serialise(vals['attribute'],
                                                 vals['comparator'],
                                                 vals['value'])
        super(PromotionsRulesConditionsExprs, self).create(cursor, user,
                                                           vals, context)
    
    def write(self, cursor, user, ids, vals, context):
        """
        Serialise before Write
        """
        vals['serialised_expr'] = self.serialise(vals['attribute'],
                                                 vals['comparator'],
                                                 vals['value'])
        super(PromotionsRulesConditionsExprs, self).write(cursor, user, ids,
                                                           vals, context)
        
PromotionsRulesConditionsExprs()


class PromotionsRulesActions(osv.osv):
    "Promotions actions"
    _name = 'promos.rules.actions'
    _description = __doc__
    _columns = {
        'promotion':fields.many2one('promos.rules', 'Promotion'),
    }
PromotionsRulesActions()
