# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution    
#    Copyright (C) 2010, Open Labs Business Solution
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

{
    'name' : 'Promotions for Open ERP',
    'version' : '0.1',
    'author' : 'Open Labs Business Solutions',
    'website': 'http://openlabs.co.in',
    'category' : 'Customised Modules',
    'depends' : [
                 "base",
                 "sale",
                 ],
    'init_xml' : [],
    'demo_xml' : [],
    'description': """
    Promotions on Sale Order for Open ERP
    = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
    Features:
    1. Promotions based on conditions and coupons
    2. Web services API compliance
    
    Credits:
        This design is based/inspired by the Magento commerce
        Special Thanks to Yannick Buron for analysis
    """,
    'update_xml': [
        'views/rule.xml',
        'views/sale.xml',
                ],
    'installable': True,
    'active': False,
}
