# pylint: disable=no-member

# Copyright 2020 Google LLC. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

'''
Constants used through Business Messages Bonjour Meal logic
'''

import stripe
from businessmessages.businessmessages_v1_messages import BusinessMessagesRepresentative

# String constants used in bot logic.
MSG_SHOW_FOOD_MENU = 'Show food menu'
MSG_SHOW_DRINKS_MENU = 'Show drinks menu'
MSG_PURCHASE_CART = 'Purchase items in cart'
MSG_ABANDON_CART = 'Abandon cart'
MSG_PURCHASE = 'Purchase now'
MSG_EMPTY_CART = 'Your shopping cart is empty.'
MSG_SEE_CART = 'See cart'
MSG_SEE_CART_BREAKDOWN = 'See cart breakdown'
MSG_CART_NOW_EMPTY = 'Your cart is now empty.'
MSG_CHECK_PENDING_ORDERS = 'Check pending orders'
MSG_ADD_TO_CART = 'Add to cart'
MSG_RESCHEDULE_ORDER = 'Reschedule order'
MSG_CHECK_ORDER_STATUS = 'Check order status'
MSG_COULD_NOT_PROCESS = 'There was an error and your payment was not processed.'
MSG_TRY_AGAIN = 'Try again'
MSG_REMOVE_ALL = 'Remove all'
MSG_SHOW_PAST_PURCHASES='Show past purchases'
MSG_CODELAB_NAME = 'Bonjour Meal Codelab'
MSG_PENDING_ORDERS = 'See pending orders'

# The domain is needed for sending the user to the correct callbacks.
DOMAIN = 'https://GCP_PROJECT_NAME.appspot.com'

# Set the Stripe API Key here.
stripe.api_key = 'YOUR_STRIPE_SECRET_KEY_HERE'

# Set of commands the bot understand.
CMD_SHOW_PENDING_PICKUP = 'show_pending_pickup'
CMD_SHOW_PURCHASES = 'show_purchases'
CMD_DRINK_MENU = 'show_drink_menu'
CMD_SHOW_HOURS = 'show_business_hours'
CMD_PURCHASE_CART = 'purchase_cart'
CMD_CART_BREAKDOWN = 'show_cart_receipt'
CMD_FOOD_MENU = 'show_food_menu'
CMD_SHOW_CART = 'show_cart'
CMD_ABANDON_CART = 'abandon_cart'
CMD_ADD_TO_CART = 'add_to_cart'
CMD_SET_PICKUP_DATE = 'set_pickup_date'
CMD_SET_PICKUP_TIME = 'set_pickup_time'
CMD_CONF_PICKUP_DETAILS = 'confirm_pickup_details'
CMD_RESET_PICKUP_DETAILS = 'reset_pickup_details'
CMD_CHECK_ORDER_STATUS = 'check_order_status'
CMD_RESCHEDULE_ORDER = 'reschedule_order'
# The location of the service account credentials.
SERVICE_ACCOUNT_LOCATION = 'resources/bm-agent-service-account-credentials.json'

# The representative type that all messages are sent as.
BOT_REPRESENTATIVE = BusinessMessagesRepresentative(
    representativeType=BusinessMessagesRepresentative.RepresentativeTypeValueValuesEnum.BOT)
