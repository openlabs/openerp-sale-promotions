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

try:
    #Backward compatible
    from sets import Set as set
except:
    pass
from osv import osv, fields
from tools.misc import ustr
import netsvc

LOGGER = netsvc.Logger()
DEBUG = True
PRODUCT_UOM_ID = 1

class PromotionsRules(osv.osv):
    "Promotion Rules"
    _name = "promos.rules"
    _description = __doc__
    _order = 'sequence'
    
    _columns = {
        'name':fields.char('Promo Name', size=50, required=True),
        'description':fields.text('Description'),
        'active':fields.boolean('Active'),
        'stop_further':fields.boolean('Stop Checks',
                              help="Stops further promotions being checked"),
        'shop':fields.many2one('sale.shop', 'Shop', required=True),
        'partner_categories':fields.many2many(
                  'res.partner.category',
                  'rule_partner_cat_rel',
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
                    'promotion',
                    string="Actions"
                        )
    }
    _defaults = {
        'logic':lambda * a:'and',
        'expected_logic_result':lambda * a:'True'
    }
    
    def _date(self, str_date):
        "Converts string date to date"
        import time
        try:
            return time.strptime(str_date, '%Y-%m-%d %H:%M:%S') 
        except:
            try:
                return time.strptime(str_date, '%Y-%m-%d')
            except:
                return str_date
            
        
    def _check_primary_conditions(self, cursor, user,
                                  promotion_rule, order, context):
        """
        Checks the conditions for 
            Coupon Code
            Validity Date
        
        """
        sales_obj = self.pool.get('sale.order')
        #Check if the customer is in the specified partner cats
        if promotion_rule.partner_categories:
            applicable_ids = [
                        category.id \
                          for category in promotion_rule.partner_categories
                            ]
            partner_categories = [
                        category.id \
                            for category in order.partner_id.category_id
                                ]
            if not set(applicable_ids).intersection(partner_categories):
                raise Exception("Not applicable to Partner Category")
        if promotion_rule.coupon_code:
            #If the codes don't match then this is not the promo 
            if not order.coupon_code == promotion_rule.coupon_code:
                raise Exception("Coupon codes do not match")
            #If there is use per coupon defined check if its overused
            if promotion_rule.uses_per_coupon > -1:
                matching_ids = sales_obj.search(cursor, user,
                         [
                          ('coupon_code', '=', promotion_rule.coupon_code),
                          ('state', '<>', 'cancel')
                          ], context=context)
                if len(matching_ids) > promotion_rule.uses_per_coupon:
                    raise Exception("Coupon is overused")
            #If a limitation exists on the usage per partner
            if promotion_rule.uses_per_partner > -1:
                matching_ids = sales_obj.search(cursor, user,
                         [
                          ('partner_id', '=', order.partner_id.id),
                          ('coupon_code', '=', promotion_rule.coupon_code),
                          ('state', '<>', 'cancel')
                          ], context=context)
                if len(matching_ids) > promotion_rule.uses_per_partner:
                    raise Exception("Customer already used coupon")
        #if a start date has been specified
        if promotion_rule.from_date and \
            not (self._date(
                order.date_order) >= self._date(promotion_rule.from_date)):
            raise Exception("Order before start of promotion")
        #If an end date has been specified
        if promotion_rule.to_date and \
            not (self._date(
                order.date_order) <= self._date(promotion_rule.to_date)):
            raise Exception("Order after end of promotion")
        #All tests have succeeded
        return True
        
    def evaluate(self, cursor, user, promotion_rule, order, context=None):
        """
        Evaluates if a promotion is valid
        TODO: Doc this
        @param promo_rule: Browse Record
        @param order: Browse Record
        """
        if not context:
            context = {}
        expression_obj = self.pool.get('promos.rules.conditions.exps')
        try:
            self._check_primary_conditions(
                                           cursor, user,
                                           promotion_rule, order,
                                           context)
        except Exception, e:
            if DEBUG:
                LOGGER.notifyChannel("Promotions",
                                     netsvc.LOG_INFO,
                                     ustr(e))
            return False
        #Now to the rules checking
        expected_result = eval(promotion_rule.expected_logic_result)
        logic = promotion_rule.logic
        #Evaluate each expression
        for expression in promotion_rule.expressions:
            result = 'Execution Failed'
            try:
                result = expression_obj.evaluate(cursor, user,
                                             expression, order, context)
                #For and logic, any False is completely false
                if (not (result == expected_result)) and (logic == 'and'):
                    return False
                #For OR logic any True is completely True
                if (result == expected_result) and (logic == 'or'):
                    return True
                #If stop_further is given, then execution stops  if the
                #condition was satisfied
                if (result == expected_result) and expression.stop_further:
                    return True
            except Exception, e:
                raise osv.except_osv("Expression Error", e)
            finally:
                if DEBUG:
                    LOGGER.notifyChannel(
                        "Promotions",
                        netsvc.LOG_INFO,
                        "%s evaluated to %s" % (
                                               expression.serialised_expr,
                                               result
                                               )
                        )
        if logic == 'and':
            #If control comes here for and logic, then all conditions were 
            #satisfied
            return True
        else:
            #if control comes here for OR logic, none were satisfied
            return False
    
    def execute_actions(self, cursor, user, promotion_rule,
                            order_id, context):
        """
        Executes the actions associated with this rule
        TODO: Doc this
        """
        action_obj = self.pool.get('promos.rules.actions')
        if DEBUG:
            LOGGER.notifyChannel(
                        "Promotions", netsvc.LOG_INFO,
                        "Applying promo %s to %s" % (
                                               promotion_rule.id,
                                               order_id
                                               ))
        order = self.pool.get('sale.order').browse(cursor, user,
                                                   order_id, context)
        for action in promotion_rule.actions:
            try:
                action_obj.execute(cursor, user, action.id,
                                   order, context=None)
            except Exception, error:
                raise error
        return True
        
        
    def apply_promotions(self, cursor, user, order_id, context=None):
        """
        Applies promotions
        TODO: Doc this
        """
        order = self.pool.get('sale.order').browse(cursor, user,
                                                   order_id, context=context)
        active_promos = self.search(cursor, user,
                                    [('active', '=', True)],
                                    context=context)
        for promotion_rule in self.browse(cursor, user,
                                          active_promos, context):
            result = self.evaluate(cursor, user,
                                   promotion_rule, order,
                                   context)
            #If evaluates to true
            if result:
                try:
                    self.execute_actions(cursor, user,
                                     promotion_rule, order_id,
                                     context)
                except Exception, e:
                    raise osv.except_osv(
                                         "Promotions",
                                         ustr(e)
                                         )
                #If stop further is true
                if promotion_rule.stop_further:
                    return True
        return True
            

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
                ('amount_untaxed', 'Untaxed Total'),
                ('amount_tax', 'Tax Amount'),
                ('amount_total', 'Total Amount'),
                ('product', 'Product Code in order'),
                ('prod_qty', 'Product Quantity combination'),
                ('prod_unit_price', 'Product UnitPrice combination'),
                ('prod_sub_total', 'Product SubTotal combination'),
                ('prod_net_price', 'Product NetPrice combination'),
                ('prod_discount', 'Product Discount combination'),
                ('prod_weight', 'Product Weight combination'),
                ('comp_sub_total', 'Compute sub total of products'),
                ('comp_sub_total_x', 'Compute sub total excluding products'),
                #('tot_item_qty', 'Total Items Quantity'),
                #('tot_weight', 'Total Weight'),
                #('tot_item_qty', 'Total Items Quantity'),
                ('custom', 'Custom domain expression'),
                ]
        
    def _on_change(self, cursor, user, ids=None,
                   attribute=None, value=None, context=None):
        """
        Set the value field to the format if nothing is there
        TODO: Doc this
        """
        #If attribute is not there then return.
        #Will this case be there?
        if not attribute:
            return {}
        #If value is not null or one of the defaults
        if not value in [
                         False,
                         "'product_code'",
                         "'product_code',0.00",
                         "['product_code','product_code2']|0.00",
                         "0.00",
                         ]:
            return {}
        #Case 1
        if attribute == 'product':
            return {
                    'value':{
                             'value':"'product_code'"
                             }
                    }
        #Case 2
        if attribute in [
                         'prod_qty',
                         'prod_unit_price',
                         'prod_sub_total',
                         'prod_discount',
                         'prod_weight',
                         'prod_net_price',
                         ]:
            return {
                    'value':{
                             'value':"'product_code',0.00"
                             }
                    }
        #Case 3
        if attribute in [
                         'comp_sub_total',
                         'comp_sub_total_x',
                         ]:
            return {
                    'value':{
                             'value':"['product_code','product_code2']|0.00"
                             }
                    }
        #Case 4
        if attribute in [
                         'amount_untaxed',
                         'amount_tax',
                         'amount_total',
                         ]:
            return {
                    'value':{
                             'value':"0.00"
                             }
                    }
        return {}
            
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
                ('not in', 'is not in'),
                ]
    
    _columns = {
        'sequence':fields.integer('Sequence'),
        'attribute':fields.selection(_get_attributes,
                                     'Attribute', size=50, required=True),
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
    
    def validate(self, cursor, user, vals, context=None):
        """
        Checks the validity
        TODO: Doc this
        """
        NUMERCIAL_COMPARATORS = ['==', '!=', '<=', '<', '>', '>=']
        ITERATOR_COMPARATORS = ['in', 'not in']
        attribute = vals['attribute']
        comparator = vals['comparator']
        value = vals['value']
        #Mismatch 1:
        if attribute in [
                         'amount_untaxed',
                         'amount_tax',
                         'amount_total',
                         'prod_qty',
                         'prod_unit_price',
                         'prod_sub_total',
                         'prod_discount',
                         'prod_weight',
                         'prod_net_price',
                         'comp_sub_total',
                         'comp_sub_total_x',
                         ] and \
            not comparator in NUMERCIAL_COMPARATORS:
            raise Exception(
                            "Only %s can be used with %s"
                            % ",".join(NUMERCIAL_COMPARATORS), attribute
                            )
        #Mismatch 2:
        if attribute == 'product' and \
            not comparator in ITERATOR_COMPARATORS:
            raise Exception(
                            "Only %s can be used with Product Code" 
                            % ",".join(ITERATOR_COMPARATORS)
                            )
        #Mismatch 3:
        if attribute in [
                         'prod_qty',
                         'prod_unit_price',
                         'prod_sub_total',
                         'prod_discount',
                         'prod_weight',
                         'prod_net_price',
                         ]:
            try:
                product_code, quantity = value.split(",")
                if not (type(eval(product_code)) == str \
                    and type(eval(quantity)) in [int, long, float]):
                    raise
            except:
                raise Exception(
                        "Value for %s combination is invalid\n"
                        "Eg for right format is `'PC312',120.50`" % attribute)
        #Mismatch 4:
        if attribute in [
                         'comp_sub_total',
                         'comp_sub_total_x',
                         ]:
            try:
                product_codes_iter, quantity = value.split("|")
                if not (type(eval(product_codes_iter)) in [tuple, list] \
                    and type(eval(quantity)) in [int, long, float]):
                    raise
            except:
                raise Exception(
                        "Value for computed subtotal combination is invalid\n"
                        "Eg for right format is `['code1,code2',..]|120.50`")
        #After all validations say True
        return True
        
    def serialise(self, attribute, comparator, value):
        """
        Constructs an expression from the entered values
        which can be quickly evaluated
        TODO: Doc this
        """
        if attribute == 'custom':
            return value
        if attribute == 'product':
            return '%s %s products' % (value,
                                       comparator)
        if attribute in [
                         'prod_qty',
                         'prod_unit_price',
                         'prod_sub_total',
                         'prod_discount',
                         'prod_weight',
                         'prod_net_price',
                         ]:
            product_code, quantity = value.split(",")
            return '(%s in products) and (%s["%s"] %s %s)' % (
                                                           product_code,
                                                           attribute,
                                                           eval(product_code),
                                                           comparator,
                                                           quantity
                                                           )
        if attribute == 'comp_sub_total':
            product_codes_iter, value = value.split("|")
            return """sum(
                [prod_sub_total.get(prod_code,0) for prod_code in %s]
                ) %s %s""" % (
                               eval(product_codes_iter),
                               comparator,
                               value
                               )
        if attribute == 'comp_sub_total_x':
            product_codes_iter, value = value.split("|")
            return """(sum(prod_sub_total.values()) - sum(
                [prod_sub_total.get(prod_code,0) for prod_code in %s]
                )) %s %s""" % (
                               eval(product_codes_iter),
                               comparator,
                               value
                               )
        return "order.%s %s %s" % (
                                    attribute,
                                    comparator,
                                    value) 
        
    def evaluate(self, cursor, user,
                 expression, order, context=None):
        """
        Evaluates the expression in given environment
        
        TODO: Doc the rest
        @param expression_id: Browserecord of expression
        @param object: BrowseRecord of sale order
        @return: True if evaluation succeeded
        """
        products = []   # List of product Codes
        prod_qty = {}   # Dict of product_code:quantity
        prod_unit_price = {}
        prod_sub_total = {}
        prod_discount = {}
        prod_weight = {}
        prod_net_price = {}
        prod_lines = {}
        for line in order.order_line:
            if line.product_id:
                product_code = line.product_id.code
                products.append(product_code)
                prod_lines[product_code] = line.product_id
                prod_qty[product_code] = prod_qty.get(
                                            product_code, 0.00
                                                    ) + line.product_uom_qty
                prod_net_price[product_code] = prod_net_price.get(
                                                    product_code, 0.00
                                                            ) + line.price_net
                prod_unit_price[product_code] = prod_unit_price.get(
                                                    product_code, 0.00
                                                            ) + line.price_unit
                prod_sub_total[product_code] = prod_sub_total.get(
                                                    product_code, 0.00
                                                            ) + line.price_subtotal
                prod_discount[product_code] = prod_discount.get(
                                                    product_code, 0.00
                                                            ) + line.discount
                prod_weight[product_code] = prod_weight.get(
                                                    product_code, 0.00
                                                            ) + line.th_weight 
        return eval(expression.serialised_expr) 
    
    def create(self, cursor, user, vals, context=None):
        """
        Serialise before save
        """
        try:
            self.validate(cursor, user, vals, context)
        except Exception, e:
            raise osv.except_osv("Invalid Expression", ustr(e))
        vals['serialised_expr'] = self.serialise(vals['attribute'],
                                                 vals['comparator'],
                                                 vals['value'])
        super(PromotionsRulesConditionsExprs, self).create(cursor, user,
                                                           vals, context)
    
    def write(self, cursor, user, ids, vals, context):
        """
        Serialise before Write
        """
        #Validate before save
        if type(ids) in [list, tuple] and ids:
            ids = ids[0]
        try:
            old_vals = self.read(cursor, user, ids,
                                 ['attribute', 'comparator', 'value'],
                                 context)
            old_vals.update(vals)
            old_vals.has_key('id') and old_vals.pop('id')
            self.validate(cursor, user, old_vals, context)
        except Exception, e:
            raise osv.except_osv("Invalid Expression", ustr(e))
        #only value may have changed and client gives only value
        vals = old_vals 
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
    _rec_name = 'action_type'

    def _on_change(self, cursor, user, ids=None,
                   action_type=None, product_code=None,
                   arguments=None, context=None):
        """
        Sets the arguments as templates according to action_type
        TODO: Doc this
        """
        if not action_type:
            return {}
        if not arguments in [
                             False,
                             "0.00",
                             "1,1",
                             ] and product_code in [
                                        "'product_code'",
                                        "'product_code_of_y'"
                                        "'product_code_x','product_code_y'"
                                                  ]:
            return {}
        if action_type in [
                           'prod_disc_perc',
                           'prod_disc_fix',
                           ] :
            return {
                    'value':{
                             'product_code':"'product_code'",
                             'arguments':"0.00",
                             }
                    }
        if action_type in [
                           'cart_disc_perc',
                           'cart_disc_fix',
                           ] :
            return {
                    'value':{
                             'product_code':False,
                             'arguments':"0.00",
                             }
                    }
        if action_type in [
                           'prod_x_get_y',
                           ] :
            return {
                    'value':{
                         'product_code':"'product_code_x','product_code_y'",
                         'arguments':"1,1",
                             }
                    }
        #Finally if nothing works
        return {}
    
    def _get_action_types(self, cursor, user, ids=None, context=None):
        """
        Gets the action types in predefined format
        TODO: Doc this
        """
        return [
                ('prod_disc_perc', 'Discount % on Product'),
                ('prod_disc_fix', 'Fixed amount on Product'),
                ('cart_disc_perc', 'Discount % on Sub Total'),
                ('cart_disc_fix', 'Fixed amount on Sub Total'),
                ('prod_x_get_y', 'Buy X get Y free')
                ]
            
    _columns = {
        'sequence':fields.integer('Sequence', required=True),
        'action_type':fields.selection(_get_action_types,
                                       'Action',
                                       required=True),
        'product_code':fields.char('Product Code',
                                   size=100,
                                   ),
        'arguments':fields.char('Arguments', size=100),
        'promotion':fields.many2one('promos.rules',
                                    'Promotion'),
    }
    
    def _clear_existing_promotion_lines(self, cursor, user,
                                        order, context=None):
        """
        Deletes existing promotion lines before applying
        """
        order_line_obj = self.pool.get('sale.order.line')
        #Delete all promotion lines
        order_line_ids = order_line_obj.search(cursor, user,
                                            [
                                             ('order_id', '=', order.id),
                                             ('promotion_line', '=', True),
                                            ], context=context
                                            )
        if order_line_ids:
            order_line_obj.unlink(cursor, user, order_line_ids, context)
        #Clear discount column
        order_line_ids = order_line_obj.search(cursor, user,
                                            [
                                             ('order_id', '=', order.id),
                                            ], context=context
                                            )
        if order_line_ids:
            order_line_obj.write(cursor, user,
                                 order_line_ids,
                                 {'discount':0.00},
                                 context=context)
        return True
        
    def _action_prod_disc_perc(self, cursor, user,
                               action, order, context=None):
        """
        Action for 'Discount % on Product'
        DOC this
        """
        order_line_obj = self.pool.get('sale.order.line')
        for order_line in order.order_line:
            if order_line.product_id.code == eval(action.product_code):
                return order_line_obj.write(cursor,
                                     user,
                                     order_line.id,
                                     {
                                      'discount':eval(action.arguments),
                                      },
                                     context
                                     )
    
    def _action_prod_disc_fix(self, cursor, user,
                              action, order, context=None):
        """
        Action for 'Fixed amount on Product'
        DOC this
        """
        order_line_obj = self.pool.get('sale.order.line')
        product_obj = self.pool.get('product.product')
        line_name = '%s on %s' % (action.promotion.name,
                                     eval(action.product_code))
        product_id = product_obj.search(cursor, user,
                               [('default_code', '=', eval(action.product_code))],
                               context=context)
        if not product_id:
            raise Exception("No product with the product code")
        if len(product_id) > 1:
            raise Exception("Many products with same code")
        product = product_obj.browse(cursor, user, product_id[0], context)
        return order_line_obj.create(cursor,
                              user,
                              {
                              'order_id':order.id,
                              'name':line_name,
                              'promotion_line':True,
                              'price_unit':-eval(action.arguments),
                              'product_uom_qty':1,
                              'product_uom':product.uom_id.id
                              },
                              context
                              )
    
    def _action_cart_disc_perc(self, cursor, user,
                               action, order, context=None):
        """
        'Discount % on Sub Total'
        DOC this
        """
        order_line_obj = self.pool.get('sale.order.line')
        return order_line_obj.create(cursor,
                                  user,
                                  {
                      'order_id':order.id,
                      'name':action.promotion.name,
                      'price_unit':-(order.amount_untaxed \
                                    * eval(action.arguments) / 100),
                      'product_uom_qty':1,
                      'promotion_line':True,
                      'product_uom':PRODUCT_UOM_ID
                                  },
                                  context
                                  )
        
    def _action_cart_disc_fix(self, cursor, user,
                              action, order, context=None):
        """
        'Fixed amount on Sub Total'
        DOC this
        """
        order_line_obj = self.pool.get('sale.order.line')
        if action.action_type == 'cart_disc_fix':
            return order_line_obj.create(cursor,
                                  user,
                                  {
                      'order_id':order.id,
                      'name':action.promotion.name,
                      'price_unit':-eval(action.arguments),
                      'product_uom_qty':1,
                      'promotion_line':True,
                      'product_uom':PRODUCT_UOM_ID
                                  },
                                  context
                                  )
    
    def _create_y_line(self, cursor, user, action,
                       order, quantity, product_id, context=None):
        """
        Create new order line for product
        TODO: Doc thos
        """
        order_line_obj = self.pool.get('sale.order.line')
        product_obj = self.pool.get('product.product')
        product_y = product_obj.browse(cursor, user, product_id[0])
        return order_line_obj.create(cursor, user, {
                                             'order_id':order.id,
                                             'product_id':product_y.id,
                                             'name':'[%s]%s (%s)' % (
                                                                     product_y.default_code,
                                                                     product_y.name,
                                                                     action.promotion.name),
                                              'price_unit':0.00, 'promotion_line':True,
                                              'product_uom_qty':quantity,
                                              'product_uom':product_y.uom_id.id
                                              }, context)

    def _action_prod_x_get_y(self, cursor, user,
                             action, order, context=None):
        """
        'Buy X get Y free:[Only for integers]'
        TODO: Large method split
        """
        order_line_obj = self.pool.get('sale.order.line')
        product_obj = self.pool.get('product.product')
        
        vals = prod_qty = {}
        #Get Product
        product_x_code, product_y_code = [eval(code) \
                                for code in action.product_code.split(",")]
        product_id = product_obj.search(cursor, user, [('default_code', '=', product_y_code)],
            context=context)
        if not product_id:
            raise Exception("No product with the code for Y")
        if len(product_id) > 1:
            raise Exception("Many products with same code")
        #get Quantity
        qty_x, qty_y = [eval(arg) \
                                for arg in action.arguments.split(",")]
        #Build a dictionary of product_code to quantity 
        for order_line in order.order_line:
            if order_line.product_id:
                product_code = order_line.product_id.default_code
                prod_qty[product_code] = prod_qty.get(
                                        product_code, 0.00
                                                ) + order_line.product_uom_qty
        #Total number of free units of y to give
        tot_free_y = int(int(prod_qty.get(product_x_code, 0) / qty_x) * qty_y)
        #If y is already in the cart discount it?
        qty_y_in_cart = prod_qty.get(product_y_code, 0)
        existing_order_line_ids = order_line_obj.search(cursor, user,
                                           [
                                ('order_id', '=', order.id),
                                ('product_id.default_code',
                                            '=', product_y_code)
                                            ],
                                           context=context
                                                )
        if existing_order_line_ids:
            update_order_line = order_line_obj.browse(cursor, user,
                                            existing_order_line_ids[0],
                                            context)
            #Update that line
            #The replace is required because on secondary update 
            #the name may be repeated
            if tot_free_y:
                line_name = "%s (%s)" % (
                                    update_order_line.name.replace(
                                                    '(%s)' % action.promotion.name,
                                                            ''),
                                    action.promotion.name
                                            )
                if qty_y_in_cart <= tot_free_y:
                    #Quantity in cart is less then increase to total free
                    order_line_obj.write(cursor, user, update_order_line.id,
                                     {
                                      'name':line_name,
                                      'product_uom_qty': tot_free_y,
                                      'discount': 100,
                                      }, context)
                    
                else:
                    #If the order has come for 5 and only 3 are free
                    #then convert paid order to 2 units and rest free
                    order_line_obj.write(cursor, user, update_order_line.id,
                                     {
                                      'product_uom_qty': qty_y_in_cart - tot_free_y,
                                      }, context)
                    self._create_y_line(cursor, user, action,
                                        order,
                                        tot_free_y,
                                        product_id,
                                        context
                                        )
                #delete the other lines
                existing_order_line_ids.remove(existing_order_line_ids[0])
                if existing_order_line_ids:
                    order_line_obj.unlink(cursor, user,
                                              existing_order_line_ids, context)
                return True
        else:
            #Dont create line if quantity is not there
            if not tot_free_y:
                return True
            return self._create_y_line(cursor, user, action,
                                       order, tot_free_y, product_id, context)
                                
    def execute(self, cursor, user, action_id,
                                   order, context=None):
        """
        Executes the action into the order
        TODO: Doc this
        """
        self._clear_existing_promotion_lines(cursor, user, order, context)
        action = self.browse(cursor, user, action_id, context)
        method_name = '_action_' + action.action_type
        return getattr(self, method_name).__call__(cursor, user, action,
                                                   order, context)
        
    def validate(self, cursor, user, vals, context):
        """
        Validates if the values are coherent with
        attribute
        """
        if vals['action_type'] in [
                           'prod_disc_perc',
                           'prod_disc_fix',
                           ] :
            if not type(eval(vals['product_code'])) == str:
               raise Exception(
                        "Invalid product code\nHas to be 'product_code'"
                            ) 
            if not type(eval(vals['arguments'])) in [int, long, float]:
                raise Exception("Argument has to be numeric. eg: 10.00")
        
        if vals['action_type'] in [
                           'cart_disc_perc',
                           'cart_disc_fix',
                           ]:
            if vals['product_code']:
                   raise Exception("Product code is not used in cart actions") 
            if not type(eval(vals['arguments'])) in [int, long, float]:
                raise Exception("Argument has to be numeric. eg: 10.00")
        
        if vals['action_type'] in ['prod_x_get_y', ]:
            try:
                code_1, code_2 = vals['product_code'].split(",")
                assert (type(eval(code_1)) == str)
                assert (type(eval(code_2)) == str)
            except: 
                raise Exception(
                  "Product codes have to be of form 'product_x','product_y'"
                            )
            try:
                qty_1, qty_2 = vals['arguments'].split(',')
                assert (type(eval(qty_1)) in [int, long])
                assert (type(eval(qty_2)) in [int, long])
            except:
                raise Exception("Argument has to be qty of x,y eg.`1, 1`")
        
        return True
    
    def create(self, cursor, user, vals, context=None):
        """
        Validate before save
        """
        try:
            self.validate(cursor, user, vals, context)
        except Exception, e:
            raise osv.except_osv("Invalid Expression", ustr(e))
        super(PromotionsRulesActions, self).create(cursor, user,
                                                           vals, context)
    
    def write(self, cursor, user, ids, vals, context):
        """
        Validate before Write
        """
        #Validate before save
        if type(ids) in [list, tuple] and ids:
            ids = ids[0]
        try:
            old_vals = self.read(cursor, user, ids,
                                 ['action_type', 'product_code', 'arguments'],
                                 context)
            old_vals.update(vals)
            old_vals.has_key('id') and old_vals.pop('id')
            self.validate(cursor, user, old_vals, context)
        except Exception, e:
            raise osv.except_osv("Invalid Expression", ustr(e))
        #only value may have changed and client gives only value
        vals = old_vals 
        super(PromotionsRulesActions, self).write(cursor, user, ids,
                                                           vals, context)
    
PromotionsRulesActions()
