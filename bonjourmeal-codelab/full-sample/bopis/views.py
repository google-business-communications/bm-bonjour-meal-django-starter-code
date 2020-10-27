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
View layer logic. Includes logic that manages the webhook to receive messages
from Business Messages infrastructure when a user sends a message to the agent.
'''

import json
import uuid
import stripe
from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from businessmessages.businessmessages_v1_messages import (
    BusinessMessagesMessage, BusinessMessagesSuggestion,
    BusinessMessagesSuggestedReply)

from .models import Item, Conversation, ShoppedItem

from .view_constants import (CMD_DRINK_MENU, CMD_FOOD_MENU, CMD_SHOW_HOURS,
    CMD_PURCHASE_CART, CMD_CART_BREAKDOWN, CMD_SHOW_CART, CMD_ABANDON_CART,
    CMD_ADD_TO_CART, CMD_SET_PICKUP_DATE, CMD_SET_PICKUP_TIME,
    CMD_CONF_PICKUP_DETAILS, CMD_RESCHEDULE_ORDER, CMD_RESET_PICKUP_DETAILS,
    CMD_CHECK_ORDER_STATUS, MSG_CODELAB_NAME, MSG_CART_NOW_EMPTY,
    MSG_RESCHEDULE_ORDER, MSG_CHECK_ORDER_STATUS, MSG_COULD_NOT_PROCESS,
    MSG_TRY_AGAIN, BOT_REPRESENTATIVE)

from .view_utils import (send_food_menu, send_drink_menu,
    send_business_hours_message, add_item_to_cart, send_item_added_to_cart,
    send_cart_breakdown_message, send_shopping_cart,
    send_abandoned_cart_message, send_pickup_date_request_message,
    send_pickup_time_request_message, send_message,
    send_get_pickup_detail_confirmation_message,
    send_proceed_to_payment_message)

@csrf_exempt
def callback(request):
    '''
    Callback URL. Processes messages sent from a user.

    Args:
        request (HttpRequest): The request object that django passes to the function
    Returns:
        An :HttpResponse: with status code to inform Business Messages of receipt.
    '''
    if request.method == 'POST':
        request_data = request.body.decode('utf8').replace("'", '"')
        request_body = json.loads(request_data)

        print('request_body: %s', request_body)

        # Extract the conversation id and message text.
        conversation_id = request_body.get('conversationId')
        print('conversation_id: %s', conversation_id)

        # Check if we've seen this conversation before, if not create it.
        conv = Conversation.objects.filter(id = conversation_id)
        if len(conv) == 0:
            conv = Conversation(id=conversation_id)
            conv.save()
        else:
            conv = conv[0]

        # Check that the message and text body exist.
        if 'message' in request_body and 'text' in request_body['message']:
            message = request_body['message']['text']

            print('message: %s', message)
            route_message(message, conv)
        elif 'suggestionResponse' in request_body:
            message = request_body['suggestionResponse']['postbackData']

            print('message: %s', message)
            route_message(message, conv)
        elif 'userStatus' in request_body:
            if 'isTyping' in request_body['userStatus']:
                print('User is typing')
            elif 'requestedLiveAgent' in request_body['userStatus']:
                print('User requested transfer to live agent')

        return HttpResponse('Response.')

    return HttpResponse('This webhook expects a POST request.')

def route_message(message, conv):
    '''
    Routes the message received from the user to create a response.

    Args:
        message (str): The message text received from the user.
        conv (Conversation): The unique conversation object for this user and agent.
    '''

    normalized_message = message.lower()

    if CMD_FOOD_MENU in normalized_message:
        send_food_menu(conv.id)
    elif CMD_DRINK_MENU in normalized_message:
        send_drink_menu(conv)
    elif CMD_SHOW_HOURS in normalized_message:
        send_business_hours_message(conv)
    elif CMD_ADD_TO_CART in message:
        item_id = message.split('-')[-1]
        item = Item.objects.get(id = item_id)
        add_item_to_cart(conv, item)
        send_item_added_to_cart(conv, item)
    elif CMD_CART_BREAKDOWN in message:
        send_cart_breakdown_message(conv)
    elif CMD_SHOW_CART in message:
        send_shopping_cart(conv)
    elif CMD_ABANDON_CART in message:
        conv.create_new_cart()
        send_abandoned_cart_message(conv)
    elif CMD_PURCHASE_CART in message:
        send_pickup_date_request_message(conv)
    elif CMD_SET_PICKUP_DATE in message:
        send_pickup_time_request_message(conv, message)
    elif CMD_SET_PICKUP_TIME in message:
        send_get_pickup_detail_confirmation_message(conv, message)
    elif CMD_CONF_PICKUP_DETAILS in message:
        send_proceed_to_payment_message(conv)


def landing_placeholder(request):
    '''
    Creates an HttpResponse for a user browsing to the root of the deployed project.

    Args:
        request (HttpRequest): The request object that django passes to the function
    Returns:
        An :HttpResponse: containing browser renderable HTML.
    '''

    return HttpResponse(f'''
    <h1>Welcome to the {MSG_CODELAB_NAME}</h1><br/><br/>
    To message your Bonjour Meal agent, go to the Developer Console and retrieve
     the Test URLs for the agent you have created as described in the codelab
     <a href='#'>here</a>. <br/><br/>
    The domain receiving this request is: {request.build_absolute_uri()}.
     ''')


@csrf_exempt
def create_checkout_session(request):
    '''
    Creates a checkout session tied to a payment page hosted by Stripe payment
    integration API.

    Args:
        request (HttpRequest): The request object that django passes to the function
    Returns:
        An :HttpResponse: containing browser renderable HTML.
    '''

    full_url = request.build_absolute_uri()
    domain = full_url.split('/bopis/create-checkout-session')[0]
    conv_id = request.GET.get('conversation_id')
    conv = Conversation.objects.get(id=conv_id)
    current_cart = conv.shopping_cart
    shopped_items = ShoppedItem.objects.filter(cart=current_cart)

    shopping_cart_dict = {}
    if len(shopped_items) == 0:
        cart_breakdown = MSG_CART_NOW_EMPTY
    else:
        cart_breakdown = "Here's your cart breakdown:\n\n"
        total_price = 0

        for shopped_item in shopped_items:
            shopping_cart_dict[shopped_item] = shopped_item.quantity
            total_price = total_price + shopped_item.item.price * shopped_item.quantity
            cart_breakdown = cart_breakdown + f'''{shopped_item.item.name}\n
                Quantity: {shopped_item.quantity}\n
                Price: ${shopped_item.item.price * shopped_item.quantity}\n\n'''

        cart_breakdown = cart_breakdown + f'-----\nTotal Price: ${total_price}'
        total_price = round(float(total_price) + float(total_price)*0.09025, 2)

    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
            'currency': 'usd',
            'product_data': {
                'name': 'Bonjour Meal Purchase',
            },
            'unit_amount': int(total_price*100),
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=domain+'/bopis/checkout_success?conversation_id='+conv_id,
        cancel_url=domain+'/bopis/checkout_failure?conversation_id='+conv_id,
    )
    return HttpResponse('{"id":"' + session.id + '"}')

def show_cart_to_checkout(request, conversation_id):
    '''
    Displays the users cart in a webpage before sending them off to payment
    integration with Stripe.

    Args:
        request (HttpRequest): The request object that django passes to the function
    Returns:
        Returns a template filled with contextual data to the request
    '''

    conv = Conversation.objects.get(id=conversation_id)
    current_cart = conv.shopping_cart
    shopped_items = ShoppedItem.objects.filter(cart=current_cart)
    shopping_cart_dict = {}

    if len(shopped_items) == 0:
        cart_breakdown = MSG_CART_NOW_EMPTY
    else:
        cart_breakdown = "Here's your cart breakdown:\n\n"
        total_price = 0

        for shopped_item in shopped_items:
            shopping_cart_dict[shopped_item] = shopped_item.quantity
            total_price = total_price + shopped_item.item.price * shopped_item.quantity
            cart_breakdown = cart_breakdown + f'''{shopped_item.item.name}\n
                Quantity: {shopped_item.quantity}\n
                Price: ${shopped_item.item.price * shopped_item.quantity}\n\n'''

        cart_breakdown = cart_breakdown + f"-----\nTotal Price: ${total_price}"

        context = {"subtotal": total_price,
            "items": shopping_cart_dict,
            "tax": round(float(total_price)*0.09025, 2),
            "total": round(float(total_price) + float(total_price)*0.09025, 2)
            }

    return render(request, 'bopis/checkout.html', context)

def checkout_success(request):
    '''
    User has succeeded to checkout and the Stripe callback sends the user to a
    notice.

    Args:
        request (HttpRequest): The request object that django passes to the function
    Returns:
        Returns a template filled with contextual data to the request
    '''

    conversation_id = request.GET.get("conversation_id")

    message_obj = BusinessMessagesMessage(
        messageId=str(uuid.uuid4().int),
        representative=BOT_REPRESENTATIVE,
        text='''Your payment has been completed and your order is being
            processed. We'll let you know that we've prepared your order and it
            is ready for pickup near your scheduled time.''',
        suggestions=[
            BusinessMessagesSuggestion(
                reply=BusinessMessagesSuggestedReply(
                    text=MSG_RESCHEDULE_ORDER,
                    postbackData=CMD_RESCHEDULE_ORDER)
                ),
            BusinessMessagesSuggestion(
                reply=BusinessMessagesSuggestedReply(
                    text=MSG_CHECK_ORDER_STATUS,
                    postbackData=CMD_CHECK_ORDER_STATUS)
                ),
            ]
        )
    send_message(message_obj, conversation_id)
    return render(request, 'bopis/complete.html')

def checkout_failure(request):
    '''
    User has failed to checkout and the Stripe callback sends the user to a
    notice.

    Args:
        request (HttpRequest): The request object that django passes to the function
    Returns:
        Returns a template filled with contextual data to the request
    '''

    conversation_id = request.GET.get("conversation_id")
    message_obj = BusinessMessagesMessage(
        messageId=str(uuid.uuid4().int),
        representative=BOT_REPRESENTATIVE,
        text=MSG_COULD_NOT_PROCESS,
        suggestions=[
            BusinessMessagesSuggestion(
                reply=BusinessMessagesSuggestedReply(
                    text=MSG_TRY_AGAIN,
                    postbackData=CMD_RESET_PICKUP_DETAILS)
                ),
            ]
        )
    send_message(message_obj, conversation_id)
    return render(request, 'bopis/complete.html')
