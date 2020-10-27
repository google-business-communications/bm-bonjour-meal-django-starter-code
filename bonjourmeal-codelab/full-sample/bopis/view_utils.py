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
Functions to support views.py, the functions in this utilities file connect with
the Python Business Messages SDK to create messages to send to users.
'''
import uuid
import pytz
from django.conf import settings
from django.utils import timezone

from oauth2client.service_account import ServiceAccountCredentials
from businessmessages import businessmessages_v1_client as bm_client
from businessmessages.businessmessages_v1_messages import BusinessmessagesConversationsMessagesCreateRequest

from businessmessages.businessmessages_v1_messages import (
    BusinessMessagesCarouselCard, BusinessMessagesCardContent, BusinessMessagesContentInfo,
    BusinessMessagesOpenUrlAction, BusinessMessagesMedia, BusinessMessagesMessage,
    BusinessMessagesRichCard, BusinessMessagesStandaloneCard,
    BusinessMessagesSuggestion, BusinessMessagesSuggestedAction, BusinessMessagesSuggestedReply)

from .models import Item, ShoppedItem

from .view_constants import (MSG_SHOW_FOOD_MENU, MSG_SHOW_DRINKS_MENU,
    MSG_PURCHASE_CART, MSG_ABANDON_CART, MSG_PURCHASE, MSG_EMPTY_CART,
    MSG_SEE_CART, MSG_SEE_CART_BREAKDOWN, MSG_CART_NOW_EMPTY,
    MSG_CHECK_PENDING_ORDERS, MSG_ADD_TO_CART, MSG_PENDING_ORDERS,
    MSG_REMOVE_ALL, MSG_SHOW_PAST_PURCHASES, DOMAIN,
    CMD_SHOW_PENDING_PICKUP, CMD_SHOW_PURCHASES, CMD_DRINK_MENU, CMD_FOOD_MENU,
    CMD_PURCHASE_CART, CMD_CART_BREAKDOWN, CMD_SHOW_CART, CMD_ABANDON_CART,
    CMD_ADD_TO_CART, CMD_SET_PICKUP_DATE, CMD_SET_PICKUP_TIME,
    CMD_CONF_PICKUP_DETAILS, CMD_RESET_PICKUP_DETAILS,
    SERVICE_ACCOUNT_LOCATION, BOT_REPRESENTATIVE)

def send_message(message, conversation_id):
    '''
    Posts a message to the Business Messages API, first sending
    a typing indicator event and sending a stop typing event after
    the message has been sent.

    Args:
        message (obj): The message object payload to send to the user.
        conversation_id (str): The unique id for this user and agent.
    '''
    credentials = ServiceAccountCredentials.from_json_keyfile_name(
        SERVICE_ACCOUNT_LOCATION,
        scopes=['https://www.googleapis.com/auth/businessmessages'])

    client = bm_client.BusinessmessagesV1(credentials=credentials)

    # Create the message request.
    create_request = BusinessmessagesConversationsMessagesCreateRequest(
        businessMessagesMessage=message,
        parent='conversations/' + conversation_id)

    bm_client.BusinessmessagesV1.ConversationsMessagesService(
        client=client).Create(request=create_request)

def determine_time_hour_and_meridiem(i):
    '''
    Translates 24-Hour time to 12-Hour time.

    Args:
        time_hour (int): 12 Hour representation of time
        time_meridiem (str): Time meridiem str of the time
    '''
    if i > 12:
        time_hour = i-12
        time_meridiem = 'PM'
    else:
        time_hour = i
        if i == 12:
            time_meridiem = 'PM'
        else:
            time_meridiem = 'AM'

    return time_hour, time_meridiem


def send_business_hours_message(conv):
    '''
    Sends a message to the user with the business hours of the business.

    Args:
        conv (Conversation): The conversation object tied to the user
    '''

    rich_card = BusinessMessagesRichCard(
        standaloneCard=BusinessMessagesStandaloneCard(
        cardContent=BusinessMessagesCardContent(
            title='Business Hours',
            description='''
            Sunday 8:00 AM - 8:00 PM \nMonday 8:00 AM - 8:00 PM
            Tuesday 8:00 AM - 8:00 PM \nWednesday 8:00 AM - 8:00 PM
            Thursday 8:00 AM - 8:00 PM \nFriday 8:00 AM - 8:00 PM
            Saturday 8:00 AM - 8:00 PM
            ''',
        )))
    message_obj = BusinessMessagesMessage(
        messageId=str(uuid.uuid4().int),
        representative=BOT_REPRESENTATIVE,
        richCard=rich_card,
        fallback=('Business Hours...Open daily from 8 AM - 8 PM'))

    send_message(message_obj, conv.id)

    message_obj = BusinessMessagesMessage(
        messageId=str(uuid.uuid4().int),
        representative=BOT_REPRESENTATIVE,
        text='''Thanks for inquiring about our Business Hours.
            Please let us know how else we can help!''',
        suggestions=get_cart_suggestions())

    send_message(message_obj, conv.id)

def send_proceed_to_payment_message(conv):
    '''
    Send an openUrlAction to open the webpage that sends the user to Stripe for
    payment.

    Args:
        conv (Conversation): The conversation object tied to the user
    '''

    message_obj = BusinessMessagesMessage(
        messageId=str(uuid.uuid4().int),
        representative=BOT_REPRESENTATIVE,
        text='''Great! Thanks for confirming. Proceed to checkout and we'll let
            you know when your order is ready for pickup!''',
        suggestions=[
        BusinessMessagesSuggestion(
            action=BusinessMessagesSuggestedAction(
                text=MSG_PURCHASE,
                postbackData=MSG_PURCHASE,
                openUrlAction=BusinessMessagesOpenUrlAction(
                    url=f'{DOMAIN}/bopis/checkout/{conv.id}'))
            ),
            BusinessMessagesSuggestion(
                reply=BusinessMessagesSuggestedReply(
                    text=MSG_ABANDON_CART,
                    postbackData=CMD_ABANDON_CART)
                ),
            ]
        )
    send_message(message_obj, conv.id)

def send_get_pickup_detail_confirmation_message(conv, message):
    '''
    Parses the pickup details and sends a confirmation message to the user.

    Args:
        conv (Conversation): The conversation object tied to the user
        message (String): Message from user about their requested pick up time.

    '''
    current_cart = conv.shopping_cart
    requested_pickup_time = message.split('-')
    requested_pickup_hour = requested_pickup_time[1].split(':')[0]
    requested_pickup_time_meridium = requested_pickup_time[2]

    # Convert current_cart.pickup_datetime to readable time.
    pickup_datetime = timezone.datetime(current_cart.pickup_date.year,
        current_cart.pickup_date.month,
        current_cart.pickup_date.day,
        int(requested_pickup_hour))
    current_cart.pickup_datetime = pickup_datetime
    current_cart.save()
    if timezone.now().day == current_cart.pickup_date.day:
        pickup_date_str = 'today'
    else:
        pickup_date_str = 'tomorrow'

    if int(requested_pickup_hour) > 12:
        requested_pickup_hour = int(requested_pickup_hour) - 12

    message_obj = BusinessMessagesMessage(
        messageId=str(uuid.uuid4().int),
        representative=BOT_REPRESENTATIVE,
        text=f'''Thanks for providing pickup time and date details. Please
confirm that you'll be picking up this order {pickup_date_str} at {requested_pickup_hour} {requested_pickup_time_meridium}. Do I have this
right?''',
        suggestions=[
            BusinessMessagesSuggestion(
                reply=BusinessMessagesSuggestedReply(
                    text='Yes',
                    postbackData=CMD_CONF_PICKUP_DETAILS)
                ),
            BusinessMessagesSuggestion(
                reply=BusinessMessagesSuggestedReply(
                    text='No',
                    postbackData=CMD_RESET_PICKUP_DETAILS)
                ),
            ]
        )
    send_message(message_obj, conv.id)

def send_shopping_cart_empty_message(conv):
    '''
    Inform the user that their shopping cart is empty.

    Args:
        conv (Conversation): The conversation object tied to the user
    '''
    message_obj = BusinessMessagesMessage(
        messageId=str(uuid.uuid4().int),
        representative=BOT_REPRESENTATIVE,
        text=MSG_EMPTY_CART,
        suggestions=[
            BusinessMessagesSuggestion(
                reply=BusinessMessagesSuggestedReply(
                    text=MSG_SHOW_FOOD_MENU,
                    postbackData=CMD_FOOD_MENU)
                ),
            BusinessMessagesSuggestion(
                reply=BusinessMessagesSuggestedReply(
                    text=MSG_SHOW_DRINKS_MENU,
                    postbackData=CMD_DRINK_MENU)
                ),
            BusinessMessagesSuggestion(
                reply=BusinessMessagesSuggestedReply(
                    text=MSG_PENDING_ORDERS,
                    postbackData=CMD_SHOW_PENDING_PICKUP)
                ),
            ]
        )
    send_message(message_obj, conv.id)

def send_pickup_date_request_message(conv):
    '''
    Sends a message to schedule pick up of the order.

    Args:
        conv (Conversation): The conversation object tied to the user
    '''

    current_cart = conv.shopping_cart
    shopped_items = ShoppedItem.objects.filter(cart=current_cart)

    if len(shopped_items) == 0:
        send_shopping_cart_empty_message(conv)
        return

    message_obj = BusinessMessagesMessage(
        messageId=str(uuid.uuid4().int),
        representative=BOT_REPRESENTATIVE,
        text='We currently support pickup today or tomorrow.',
        )

    send_message(message_obj, conv.id)

    message_obj = BusinessMessagesMessage(
        messageId=str(uuid.uuid4().int),
        representative=BOT_REPRESENTATIVE,
        text='When would you like to pick up your order?',
        suggestions=[
            BusinessMessagesSuggestion(
                reply=BusinessMessagesSuggestedReply(
                    text='Today',
                    postbackData=f'{CMD_SET_PICKUP_DATE}-today')
                ),
            BusinessMessagesSuggestion(
                reply=BusinessMessagesSuggestedReply(
                    text='Tomorrow',
                    postbackData=f'{CMD_SET_PICKUP_DATE}-tomorrow')
                ),
            ]
        )
    send_message(message_obj, conv.id)

def send_pickup_time_request_message(conv, message):
    '''
    Requests more detail from the user about when they want to pick up their
    order.

    Args:
        conv (Conversation): The conversation object tied to the user
        message (String): Message regarding when the user will pick up

    '''
    day = message.split('-')[-1]
    current_cart = conv.shopping_cart
    suggestion_array = []

    if day == 'today':
        suggestion_array.append(
            BusinessMessagesSuggestion(
                reply=BusinessMessagesSuggestedReply(
                    text='As soon as possible',
                    postbackData=f'{CMD_SET_PICKUP_TIME}-now'
                )
            )
        )
        current_cart.pickup_date = timezone.now().date()
        local_timezone = pytz.timezone(settings.TIME_ZONE)
        local_datetime = timezone.now().astimezone(local_timezone)
        i = local_datetime.hour + 1

        while i < 20:
            time_hour, time_meridiem = determine_time_hour_and_meridiem(i)

            suggestion_array.append(
                BusinessMessagesSuggestion(
                    reply=BusinessMessagesSuggestedReply(
                    text=f'{time_hour}:00 {time_meridiem}',
                    postbackData=f'{CMD_SET_PICKUP_TIME}-{i}:00-{time_meridiem}')
                )
            )
            i = i + 1

    if day == 'tomorrow':
        current_cart.pickup_date = timezone.now().date() + timezone.timedelta(days=1)
        i = 8
        time_hour = 8

        while i < 20:
            time_hour, time_meridiem = determine_time_hour_and_meridiem(i)

            suggestion_array.append(
                BusinessMessagesSuggestion(
                    reply=BusinessMessagesSuggestedReply(
                    text=f'{time_hour}:00 {time_meridiem}',
                    postbackData=f'{CMD_SET_PICKUP_TIME}-{i}:00-{time_meridiem}')
                )
            )
            i = i + 1
    current_cart.save()

    message_obj = BusinessMessagesMessage(
        messageId=str(uuid.uuid4().int),
        representative=BOT_REPRESENTATIVE,
        text=f'What time would you like to pick up the order {day}?',
        suggestions=suggestion_array
    )
    send_message(message_obj, conv.id)

def add_item_to_cart(conv, item):
    '''
    Add an item to a specific cart.

    Args:
        conv (Conversation): The conversation object tied to the user
        item (Item): The item the user wants to add to their cart
    '''
    if not conv.shopping_cart:
        conv.create_new_cart()
    shopped_item = ShoppedItem.objects.filter(item=item, cart=conv.shopping_cart)
    if len(shopped_item) == 0:
        new_item = ShoppedItem(item=item)
        new_item.place_in(conv.shopping_cart)
        new_item.save()
    else:
        shopped_item[0].quantity = shopped_item[0].quantity + 1
        shopped_item[0].save()


def send_item_added_to_cart(conv, item):
    '''
    Inform the user that they've added an item to the cart.

    Args:
        conv (Conversation): The conversation object tied to the user
        item (Item): The item the user wants to add to their cart
    '''
    message_obj = BusinessMessagesMessage(
        messageId=str(uuid.uuid4().int),
        representative=BOT_REPRESENTATIVE,
        text=f"You've added an item to your cart: {item.name}",
        suggestions=[
            BusinessMessagesSuggestion(
                reply=BusinessMessagesSuggestedReply(
                    text=MSG_SEE_CART,
                    postbackData=CMD_SHOW_CART)
                ),
            BusinessMessagesSuggestion(
                reply=BusinessMessagesSuggestedReply(
                    text=MSG_SEE_CART_BREAKDOWN,
                    postbackData=CMD_CART_BREAKDOWN)
                ),
            BusinessMessagesSuggestion(
                reply=BusinessMessagesSuggestedReply(
                    text=MSG_SHOW_FOOD_MENU,
                    postbackData=CMD_FOOD_MENU)
                ),
            BusinessMessagesSuggestion(
                reply=BusinessMessagesSuggestedReply(
                    text=MSG_SHOW_DRINKS_MENU,
                    postbackData=CMD_DRINK_MENU)
                ),
            ]
        )
    send_message(message_obj, conv.id)

def send_shopping_cart(conv):
    '''
    Send the user their shopping cart.
    '''

    cart_items = ShoppedItem.objects.filter(cart=conv.shopping_cart)
    if not conv.shopping_cart or len(cart_items) == 0:
        message_obj = BusinessMessagesMessage(
            messageId=str(uuid.uuid4().int),
            representative=BOT_REPRESENTATIVE,
            text=MSG_EMPTY_CART,
            suggestions=[
                BusinessMessagesSuggestion(
                    reply=BusinessMessagesSuggestedReply(
                        text=MSG_SHOW_FOOD_MENU,
                        postbackData=CMD_FOOD_MENU)
                    ),
                BusinessMessagesSuggestion(
                    reply=BusinessMessagesSuggestedReply(
                        text=MSG_SHOW_DRINKS_MENU,
                        postbackData=CMD_DRINK_MENU)
                    ),
                BusinessMessagesSuggestion(
                    reply=BusinessMessagesSuggestedReply(
                        text=MSG_PENDING_ORDERS,
                        postbackData=CMD_SHOW_PENDING_PICKUP)
                    ),
                ]
            )
        send_message(message_obj, conv.id)

    elif len(cart_items) == 1:
        fallback_text = (f'Your shopping cart contains a {cart_items[0].item.name}')

        rich_card = BusinessMessagesRichCard(
            standaloneCard=BusinessMessagesStandaloneCard(
                cardContent=BusinessMessagesCardContent(
                    title=cart_items[0].item.name,
                    description=f'Quantity: {cart_items[0].quantity}',
                    suggestions=[],
                    media=BusinessMessagesMedia(
                        height=BusinessMessagesMedia.HeightValueValuesEnum.MEDIUM,
                        contentInfo=BusinessMessagesContentInfo(
                            fileUrl=cart_items[0].item.image_url,
                            forceRefresh=False
                        ))
                    )))
        message_obj = BusinessMessagesMessage(
            messageId=str(uuid.uuid4().int),
            representative=BOT_REPRESENTATIVE,
            richCard=rich_card,
            fallback=fallback_text)

        send_message(message_obj, conv.id)

        message_obj = BusinessMessagesMessage(
            messageId=str(uuid.uuid4().int),
            representative=BOT_REPRESENTATIVE,
            text=f'''The total value of your shopping cart is
                ${cart_items[0].item.price * cart_items[0].quantity}.''',
            suggestions=get_cart_suggestions())

        send_message(message_obj, conv.id)

    else:
        rich_card = BusinessMessagesRichCard(carouselCard=get_cart_carousel(cart_items))

        # Construct a fallback text for devices that do not support carousels.
        fallback_text = ''
        for card_content in rich_card.carouselCard.cardContents:
            fallback_text += (card_content.title + '\n\n' + card_content.description
                            + '\n\n' + card_content.media.contentInfo.fileUrl
                            + '\n---------------------------------------------\n\n')

        message_obj = BusinessMessagesMessage(
            messageId=str(uuid.uuid4().int),
            representative=BOT_REPRESENTATIVE,
            richCard=rich_card,
            fallback=fallback_text)

        send_message(message_obj, conv.id)

        total_price = 0
        for cart_item in cart_items:
            total_price = total_price + cart_item.item.price*cart_item.quantity

        message_obj = BusinessMessagesMessage(
            messageId=str(uuid.uuid4().int),
            representative=BOT_REPRESENTATIVE,
            text=f'The total value of your shopping cart is ${total_price}.',
            suggestions=get_cart_suggestions()
            )

        send_message(message_obj, conv.id)

def send_drink_menu(conv):
    '''
    Sends a sample food menu to the user.

    Args:
        conversation_id (str): The unique id for this user and agent.
    '''
    rich_card = BusinessMessagesRichCard(carouselCard=get_drink_menu_carousel())

    # Construct a fallback text for devices that do not support carousels.
    fallback_text = ''
    for card_content in rich_card.carouselCard.cardContents:
        fallback_text += (card_content.title + '\n\n' + card_content.description
                          + '\n\n' + card_content.media.contentInfo.fileUrl
                          + '\n---------------------------------------------\n\n')

    message_obj = BusinessMessagesMessage(
        messageId=str(uuid.uuid4().int),
        representative=BOT_REPRESENTATIVE,
        richCard=rich_card,
        fallback=fallback_text)
    send_message(message_obj, conv.id)

def send_food_menu(conversation_id):
    '''
    Sends a sample food menu to the user.

    Args:
        conversation_id (str): The unique id for this user and agent.
    '''
    rich_card = BusinessMessagesRichCard(carouselCard=get_food_menu_carousel())

    # Construct a fallback text for devices that do not support carousels.
    fallback_text = ''
    for card_content in rich_card.carouselCard.cardContents:
        fallback_text += (card_content.title + '\n\n' + card_content.description
                          + '\n\n' + card_content.media.contentInfo.fileUrl
                          + '\n---------------------------------------------\n\n')

    message_obj = BusinessMessagesMessage(
        messageId=str(uuid.uuid4().int),
        representative=BOT_REPRESENTATIVE,
        richCard=rich_card,
        fallback=fallback_text)
    send_message(message_obj, conversation_id)

def send_abandoned_cart_message(conv):
    '''
    Sends the message received from the user back to the user.

    Args:
        message (str): The message text received from the user.
        conversation_id (str): The unique id for this user and agent.
    '''
    message_obj = BusinessMessagesMessage(
        messageId=str(uuid.uuid4().int),
        representative=BOT_REPRESENTATIVE,
        text=MSG_CART_NOW_EMPTY,
        suggestions=[
            BusinessMessagesSuggestion(
                reply=BusinessMessagesSuggestedReply(
                    text=MSG_SHOW_FOOD_MENU,
                    postbackData=CMD_FOOD_MENU)
                ),
            BusinessMessagesSuggestion(
                reply=BusinessMessagesSuggestedReply(
                    text=MSG_CHECK_PENDING_ORDERS,
                    postbackData=CMD_SHOW_PENDING_PICKUP)
                ),
            BusinessMessagesSuggestion(
                reply=BusinessMessagesSuggestedReply(
                    text=MSG_SHOW_PAST_PURCHASES,
                    postbackData=CMD_SHOW_PURCHASES)
                ),
            ]
        )
    send_message(message_obj, conv.id)

def send_cart_breakdown_message(conv):
    '''
    This function sends a textual representation
    '''
    cart = conv.shopping_cart
    shopped_items = ShoppedItem.objects.filter(cart=cart)

    if len(shopped_items) == 0:
        cart_breakdown = MSG_CART_NOW_EMPTY
    else:
        cart_breakdown = "Here's your cart breakdown:\n\n"
        total_price = 0

        for shopped_item in shopped_items:
            total_price = total_price + shopped_item.item.price * shopped_item.quantity

            cart_breakdown = cart_breakdown + f'''{shopped_item.item.name}\n
                Quantity: {shopped_item.quantity}\n
                Price: ${shopped_item.item.price * shopped_item.quantity}\n\n'''

        cart_breakdown = cart_breakdown + f'-----\nSubtotal Price: ${total_price}'

    message_obj = BusinessMessagesMessage(
        messageId=str(uuid.uuid4().int),
        representative=BOT_REPRESENTATIVE,
        text=cart_breakdown,
        suggestions=[
            BusinessMessagesSuggestion(
                reply=BusinessMessagesSuggestedReply(
                    text=MSG_PURCHASE_CART,
                    postbackData=CMD_PURCHASE_CART)
                ),
            BusinessMessagesSuggestion(
                reply=BusinessMessagesSuggestedReply(
                    text=MSG_CHECK_PENDING_ORDERS,
                    postbackData=CMD_SHOW_PENDING_PICKUP)
                ),
            BusinessMessagesSuggestion(
                reply=BusinessMessagesSuggestedReply(
                    text=MSG_ABANDON_CART,
                    postbackData=CMD_ABANDON_CART)
                ),
            ]
        )
    send_message(message_obj, conv.id)

def get_cart_suggestions():
    '''
    Creates a list of sample suggestions that includes a
    suggested reply and two actions.

    Returns:
       A :list: A list of sample BusinessMessagesSuggestions.
    '''
    return [
        BusinessMessagesSuggestion(
            reply=BusinessMessagesSuggestedReply(
                text=MSG_SHOW_FOOD_MENU,
                postbackData=CMD_FOOD_MENU)
            ),
        BusinessMessagesSuggestion(
            reply=BusinessMessagesSuggestedReply(
                text=MSG_SHOW_DRINKS_MENU,
                postbackData=CMD_DRINK_MENU)
            ),
        BusinessMessagesSuggestion(
            reply=BusinessMessagesSuggestedReply(
                text=MSG_PURCHASE_CART,
                postbackData=CMD_PURCHASE_CART)
            ),
        BusinessMessagesSuggestion(
            reply=BusinessMessagesSuggestedReply(
                text=MSG_ABANDON_CART,
                postbackData=CMD_ABANDON_CART)
            ),
        ]

def get_cart_carousel(cart_items):
    '''
    A function that returns the items in the shopping cart in a carousel.
    '''
    card_content = []

    for cart_entity in cart_items:
        card_content.append(BusinessMessagesCardContent(
            title=cart_entity.item.name,
            description=f'Quantity: {cart_entity.quantity}' ,
            suggestions=[
                    BusinessMessagesSuggestion(
                        reply=BusinessMessagesSuggestedReply(
                            text='➕',
                            postbackData=f'{CMD_ADD_TO_CART}-{cart_entity.item.id}')
                        ),
                    BusinessMessagesSuggestion(
                        reply=BusinessMessagesSuggestedReply(
                            text='➖',
                            postbackData=f'remove_from_cart-{cart_entity.item.id}')
                        ),
                    BusinessMessagesSuggestion(
                        reply=BusinessMessagesSuggestedReply(
                            text=MSG_REMOVE_ALL,
                            postbackData=f'remove_all_from_cart-{cart_entity.item.id}')
                        ),
                    ],
            media=BusinessMessagesMedia(
                height=BusinessMessagesMedia.HeightValueValuesEnum.MEDIUM,
                contentInfo=BusinessMessagesContentInfo(
                    fileUrl=cart_entity.item.image_url,
                    forceRefresh=False))))

    return BusinessMessagesCarouselCard(
        cardContents=card_content,
        cardWidth=BusinessMessagesCarouselCard.CardWidthValueValuesEnum.MEDIUM
        )

def get_food_menu_carousel():
    '''
    Creates the food menu carousel rich card.

    Returns:
       A :obj: A BusinessMessagesCarouselCard object with three cards.
    '''
    card_content = []
    menu_items = Item.objects.filter(available=True, menu_type='F')

    for item in menu_items:
        card_content.append(BusinessMessagesCardContent(
            title=item.name,
            description=f'${item.price}{item.currency}' ,
            suggestions=get_menu_item_suggestions(item),
            media=BusinessMessagesMedia(
                height=BusinessMessagesMedia.HeightValueValuesEnum.MEDIUM,
                contentInfo=BusinessMessagesContentInfo(
                    fileUrl=item.image_url,
                    forceRefresh=False))))

    return BusinessMessagesCarouselCard(
        cardContents=card_content,
        cardWidth=BusinessMessagesCarouselCard.CardWidthValueValuesEnum.MEDIUM)

def get_drink_menu_carousel():
    '''
    Creates the drink menu carousel rich card.

    Returns:
       A :obj: A BusinessMessagesCarouselCard object with three cards.
    '''
    card_content = []
    menu_items = Item.objects.filter(available=True, menu_type='D')

    for item in menu_items:
        card_content.append(BusinessMessagesCardContent(
            title=item.name,
            description=f'${item.price}{item.currency}' ,
            suggestions=get_menu_item_suggestions(item),
            media=BusinessMessagesMedia(
                height=BusinessMessagesMedia.HeightValueValuesEnum.MEDIUM,
                contentInfo=BusinessMessagesContentInfo(
                    fileUrl=item.image_url,
                    forceRefresh=False))))

    return BusinessMessagesCarouselCard(
        cardContents=card_content,
        cardWidth=BusinessMessagesCarouselCard.CardWidthValueValuesEnum.MEDIUM)

def get_menu_item_suggestions(item):
    '''
    Creates a list of sample suggestions that includes a
    suggested reply and two actions.

    Returns:
       A :list: A list of sample BusinessMessagesSuggestions.
    '''

    return [
        BusinessMessagesSuggestion(
            reply=BusinessMessagesSuggestedReply(
                text=MSG_ADD_TO_CART,
                postbackData=f'{CMD_ADD_TO_CART}-{item.id}')
            ),
        BusinessMessagesSuggestion(
            action=BusinessMessagesSuggestedAction(
                text=MSG_PURCHASE,
                postbackData=MSG_PURCHASE,
                openUrlAction=BusinessMessagesOpenUrlAction(
                    url=f'{DOMAIN}/bopis/purchase/{item.id}'))
            ),
        ]
