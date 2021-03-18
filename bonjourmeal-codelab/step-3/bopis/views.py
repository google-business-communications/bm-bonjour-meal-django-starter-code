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
"""The view layer of logic for our Bonjour Meal sample.

The logic here defines the behavior of the webhook when messages are received
from users messaging through Business Messages.
"""
import json
import uuid

from businessmessages import businessmessages_v1_client as bm_client
from businessmessages.businessmessages_v1_messages import (
    BusinessMessagesCarouselCard, BusinessMessagesCardContent,
    BusinessMessagesContentInfo, BusinessMessagesDialAction,
    BusinessmessagesConversationsMessagesCreateRequest,
    BusinessMessagesOpenUrlAction, BusinessMessagesMedia,
    BusinessMessagesMessage, BusinessMessagesRepresentative,
    BusinessMessagesRichCard, BusinessMessagesStandaloneCard,
    BusinessMessagesSuggestion, BusinessMessagesSuggestedAction,
    BusinessMessagesSuggestedReply)

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from google.cloud import datastore
from google.oauth2 import service_account
from oauth2client.service_account import ServiceAccountCredentials

# The location of the service account credentials
SERVICE_ACCOUNT_LOCATION = 'resources/bm-agent-service-account-credentials.json'
INVENTORY_FILE = 'resources/inventory.json'

# Set of commands the bot understands
CMD_RICH_CARD = 'card'
CMD_CAROUSEL_CARD = 'carousel'
CMD_SUGGESTIONS = 'chips'
CMD_BUSINESS_HOURS_INQUIRY = 'business-hours-inquiry'
CMD_ONLINE_SHOPPING_INQUIRY = 'online-shopping-inquiry'
CMD_SHOW_PRODUCT_CATALOG = 'show-product-catalog'
CMD_ADD_ITEM = 'add-item'
CMD_DEL_ITEM = 'del-item'
CMD_SHOW_CART = 'show-cart'
CMD_GET_CART_PRICE = 'show-cart-price'

# Images used in cards and carousel examples
SAMPLE_IMAGES = [
    'https://storage.googleapis.com/kitchen-sink-sample-images/cute-dog.jpg',
    'https://storage.googleapis.com/kitchen-sink-sample-images/elephant.jpg',
    'https://storage.googleapis.com/kitchen-sink-sample-images/adventure-cliff.jpg',
    'https://storage.googleapis.com/kitchen-sink-sample-images/sheep.jpg',
    'https://storage.googleapis.com/kitchen-sink-sample-images/golden-gate-bridge.jpg',
]

# The representative type that all messages are sent as
BOT_REPRESENTATIVE = BusinessMessagesRepresentative(
    representativeType=BusinessMessagesRepresentative
    .RepresentativeTypeValueValuesEnum.BOT,
    displayName='Bonjour Meal Bot',
    avatarImage='https://storage.googleapis.com/sample-avatars-for-bm/bot-avatar.jpg'
)


@csrf_exempt
def callback(request):
  """Callback URL. Processes messages sent from user.

  Args:
      request (HttpRequest): The request object that django passes to the
        function

  Returns:
      An :HttpResponse: containing browser renderable HTML.
  """
  if request.method == 'POST':
    request_data = request.body.decode('utf8').replace("'", '"')
    request_body = json.loads(request_data)

    print('request_body: %s', request_body)

    # Extract the conversation id and message text
    conversation_id = request_body.get('conversationId')
    print('conversation_id: %s', conversation_id)

    # Check if we've seen this conversation before, if not create it.

    # Check that the message and text body exist

    if 'message' in request_body and 'text' in request_body['message']:
      message = request_body['message']['text']

      print('message: %s', message)
      route_message(message, conversation_id)
    elif 'suggestionResponse' in request_body:
      message = request_body['suggestionResponse']['postbackData']

      print('message: %s', message)
      route_message(message, conversation_id)
    elif 'userStatus' in request_body:
      if 'isTyping' in request_body['userStatus']:
        print('User is typing')
      elif 'requestedLiveAgent' in request_body['userStatus']:
        print('User requested transfer to live agent')

    return HttpResponse('Response.')

  return HttpResponse('This webhook expects a POST request.')


def route_message(message, conversation_id):
  """Routes the message received from the user to create a response.

  Args:
    message (str): The message text received from the user.
    conversation_id (str): The unique id for this user and agent.
  """
  normalized_message = message.lower()

  if normalized_message == CMD_RICH_CARD:
    send_rich_card(conversation_id)
  elif normalized_message == CMD_CAROUSEL_CARD:
    send_carousel(conversation_id)
  elif normalized_message == CMD_SUGGESTIONS:
    send_message_with_suggestions(conversation_id)
  elif normalized_message == CMD_BUSINESS_HOURS_INQUIRY:
    send_message_with_business_hours(conversation_id)
  elif normalized_message == CMD_ONLINE_SHOPPING_INQUIRY:
    send_online_shopping_info_message(conversation_id)
  elif normalized_message == CMD_SHOW_PRODUCT_CATALOG:
    send_product_catalog(conversation_id)
  elif CMD_ADD_ITEM in normalized_message or CMD_DEL_ITEM in normalized_message:
    update_shopping_cart(conversation_id, normalized_message)
  elif normalized_message == CMD_SHOW_CART:
    send_shopping_cart(conversation_id)
  elif normalized_message == CMD_GET_CART_PRICE:
    send_shopping_cart_total_price(conversation_id)
  else:
    echo_message(message, conversation_id)


def send_message_with_business_hours(conversation_id):
  """Sends a message containing hours of operation for the business.

  Args:
    conversation_id (str): The unique id for this user and agent.
  """

  message = """Thanks for contacting us! The hours for the store are:\n
    MON 8am - 8pm\n
    TUE 8am - 8pm\n
    WED 8am - 8pm\n
    THU 8am - 8pm\n
    FRI 8am - 8pm\n
    SAT 8am - 8pm\n
    SUN 8am - 8pm
    """

  message_obj = BusinessMessagesMessage(
      messageId=str(uuid.uuid4().int),
      representative=BOT_REPRESENTATIVE,
      text=message)

  send_message(message_obj, conversation_id)

  message_obj = BusinessMessagesMessage(
      messageId=str(uuid.uuid4().int),
      representative=BOT_REPRESENTATIVE,
      text='Let us know how else we can help you:',
      fallback='Please let us know how else we can help you.',
      suggestions=[
          BusinessMessagesSuggestion(
              reply=BusinessMessagesSuggestedReply(
                  text='Can I purchase online?',
                  postbackData='online-shopping-inquiry')),
      ])

  send_message(message_obj, conversation_id)


def send_online_shopping_info_message(conversation_id):
  """Sends a rich card with online shopping info to the user.

  Args:
    conversation_id (str): The unique id for this user and agent.
  """
  fallback_text = ('Online shopping will be available soon!')

  rich_card = BusinessMessagesRichCard(
      standaloneCard=BusinessMessagesStandaloneCard(
          cardContent=BusinessMessagesCardContent(
              title='Online shopping info!',
              description='Thanks for your business, we are located in SF near the Golden Gate Bridge. Online shopping is not yet available, please check back with us in a few days.',
              suggestions=[],
              media=BusinessMessagesMedia(
                  height=BusinessMessagesMedia.HeightValueValuesEnum.MEDIUM,
                  contentInfo=BusinessMessagesContentInfo(
                      fileUrl=SAMPLE_IMAGES[4], forceRefresh=False)))))

  message_obj = BusinessMessagesMessage(
      messageId=str(uuid.uuid4().int),
      representative=BOT_REPRESENTATIVE,
      richCard=rich_card,
      fallback=fallback_text)

  send_message(message_obj, conversation_id)

  message_obj = BusinessMessagesMessage(
      messageId=str(uuid.uuid4().int),
      representative=BOT_REPRESENTATIVE,
      text='Let us know how else we can help you:',
      fallback='Please let us know how else we can help you.',
      suggestions=[
          BusinessMessagesSuggestion(
              reply=BusinessMessagesSuggestedReply(
                  text='Business hours',
                  postbackData='business-hours-inquiry')),
      ])

  send_message(message_obj, conversation_id)


def send_rich_card(conversation_id):
  """Sends a sample rich card to the user.

  Args:
    conversation_id (str): The unique id for this user and agent.
  """
  fallback_text = ('Business Messages!!!\n\n' +
                   'This is an example rich card\n\n' + SAMPLE_IMAGES[0])

  rich_card = BusinessMessagesRichCard(
      standaloneCard=BusinessMessagesStandaloneCard(
          cardContent=BusinessMessagesCardContent(
              title='Business Messages!!!',
              description='This is an example rich card',
              suggestions=get_sample_suggestions(),
              media=BusinessMessagesMedia(
                  height=BusinessMessagesMedia.HeightValueValuesEnum.MEDIUM,
                  contentInfo=BusinessMessagesContentInfo(
                      fileUrl=SAMPLE_IMAGES[0], forceRefresh=False)))))

  message_obj = BusinessMessagesMessage(
      messageId=str(uuid.uuid4().int),
      representative=BOT_REPRESENTATIVE,
      richCard=rich_card,
      fallback=fallback_text)

  send_message(message_obj, conversation_id)


def send_carousel(conversation_id):
  """Sends a sample rich card to the user.

  Args:
    conversation_id (str): The unique id for this user and agent.
  """
  rich_card = BusinessMessagesRichCard(carouselCard=get_sample_carousel())

  fallback_text = ''

  # Construct a fallback text for devices that do not support carousels
  for card_content in rich_card.carouselCard.cardContents:
    fallback_text += (
        card_content.title + '\n\n' + card_content.description + '\n\n' +
        card_content.media.contentInfo.fileUrl +
        '\n---------------------------------------------\n\n')

  message_obj = BusinessMessagesMessage(
      messageId=str(uuid.uuid4().int),
      representative=BOT_REPRESENTATIVE,
      richCard=rich_card,
      fallback=fallback_text)

  send_message(message_obj, conversation_id)


def send_message_with_suggestions(conversation_id):
  """Sends a message with a suggested replies.

  Args:
    conversation_id (str): The unique id for this user and agent.
  """
  message_obj = BusinessMessagesMessage(
      messageId=str(uuid.uuid4().int),
      representative=BOT_REPRESENTATIVE,
      text='Message with suggestions',
      fallback='Your device does not support suggestions',
      suggestions=get_sample_suggestions())

  send_message(message_obj, conversation_id)


def echo_message(message, conversation_id):
  """Sends the message received from the user back to the user.

  Args:
    message (str): The message text received from the user.
    conversation_id (str): The unique id for this user and agent.
  """
  message_obj = BusinessMessagesMessage(
      messageId=str(uuid.uuid4().int),
      representative=BOT_REPRESENTATIVE,
      text=message)

  send_message(message_obj, conversation_id)


def get_cart_price(conversation_id):
  """Retrieves the current price of the cart against the inventory database.

  Args:
    conversation_id (str): The unique id for this user and agent.

  Returns:
    total_price :float: cart price
  """
  # Pull the data from Google Datastore
  credentials = service_account.Credentials.from_service_account_file(
      SERVICE_ACCOUNT_LOCATION)
  client = datastore.Client(credentials=credentials)
  key = client.key('ShoppingCart', conversation_id)
  result = client.get(key)

  # Retrieve the inventory data
  inventory = get_inventory_data()

  # Start off with a total of 0 before adding up the total
  total_price = 0

  if len(result.items()) != 0:
    for product_name, quantity in result.items():
      total_price = total_price + float(
          inventory['food'][get_id_by_product_name(product_name)]['price']) * int(quantity)

  return total_price


def send_shopping_cart_total_price(conversation_id):
  """Sends shopping cart price to user through Business Messages.

  Args:
    conversation_id (str): The unique id for this user and agent.
  """
  cart_price = get_cart_price(conversation_id)

  message_obj = BusinessMessagesMessage(
      messageId=str(uuid.uuid4().int),
      representative=BOT_REPRESENTATIVE,
      text=f'Your cart\'s total price is ${cart_price}.')

  send_message(message_obj, conversation_id)


def get_inventory_data():
  """Retrieves data from inventory.json

  Returns:
    inventory (dict): returns data from inventory.json as dictionary
  """
  f = open(INVENTORY_FILE)
  inventory = json.load(f)
  return inventory

def get_id_by_product_name(product_name):
  """Returns product ID by name

  Args:
    product_name (str): The name of a product

  Returns:
    product_id (int): The id of the product found in inventory.json
  """
  inventory = get_inventory_data()
  for item in inventory['food']:
    if item['name'] == product_name:
      return int(item['id'])
  return False

def get_menu_carousel():
  """Creates a sample carousel rich card.

  Returns:
      A :obj: A BusinessMessagesCarouselCard object with three cards.
  """

  inventory = get_inventory_data()

  card_content = []

  for item in inventory['food']:
    card_content.append(
        BusinessMessagesCardContent(
            title=item['name'],
            description=item['price'],
            suggestions=[
                BusinessMessagesSuggestion(
                    reply=BusinessMessagesSuggestedReply(
                        text='Add item',
                        postbackData=f'{CMD_ADD_ITEM}-{item["id"]}'))
            ],
            media=BusinessMessagesMedia(
                height=BusinessMessagesMedia.HeightValueValuesEnum.MEDIUM,
                contentInfo=BusinessMessagesContentInfo(
                    fileUrl=item['image_url'], forceRefresh=False))))

  return BusinessMessagesCarouselCard(
      cardContents=card_content,
      cardWidth=BusinessMessagesCarouselCard.CardWidthValueValuesEnum.MEDIUM)


def send_product_catalog(conversation_id):
  """Sends the product catalog to the conversation_id.

  Args:
    conversation_id (str): The unique id for this user and agent.
  """
  rich_card = BusinessMessagesRichCard(carouselCard=get_menu_carousel())

  fallback_text = ''

  # Construct a fallback text for devices that do not support carousels
  for card_content in rich_card.carouselCard.cardContents:
    fallback_text += (
        card_content.title + '\n\n' + card_content.description + '\n\n' +
        card_content.media.contentInfo.fileUrl +
        '\n---------------------------------------------\n\n')

  message_obj = BusinessMessagesMessage(
      messageId=str(uuid.uuid4().int),
      representative=BOT_REPRESENTATIVE,
      richCard=rich_card,
      fallback=fallback_text,
      suggestions=[
          BusinessMessagesSuggestion(
              reply=BusinessMessagesSuggestedReply(
                  text='See my cart', postbackData=CMD_SHOW_CART)),
          BusinessMessagesSuggestion(
              reply=BusinessMessagesSuggestedReply(
                  text='See the menu', postbackData=CMD_SHOW_PRODUCT_CATALOG)),
      ])

  send_message(message_obj, conversation_id)


def update_shopping_cart(conversation_id, message):
  """Updates the shopping cart stored in Google Datastore.

  Args:
    conversation_id (str): The unique id for this user and agent.
    message (str): The message containing whether to add or delete an item.
  """
  credentials = service_account.Credentials.from_service_account_file(
      SERVICE_ACCOUNT_LOCATION)

  inventory = get_inventory_data()

  cart_request = message.split('-')
  cart_cmd = cart_request[0]
  cart_item = cart_request[2]

  item_name = inventory['food'][int(cart_item)]['name']

  client = datastore.Client(credentials=credentials)
  key = client.key('ShoppingCart', conversation_id)
  entity = datastore.Entity(key=key)
  result = client.get(key)

  if result is None:
    if cart_cmd == 'add':
      entity.update({item_name: 1})
    elif cart_cmd == 'del':
      # The user is trying to delete an item from an empty cart. Pass and skip
      pass
  else:
    if cart_cmd == 'add':
      if result.get(item_name) is None:
        result[item_name] = 1
      else:
        result[item_name] = result[item_name] + 1

    elif cart_cmd == 'del':
      if result.get(item_name) is None:
        # The user is trying to remove an item that's no in the shopping cart.
        # Pass and skip
        pass
      elif result[item_name] - 1 > 0:
        result[item_name] = result[item_name] - 1
      else:
        del result[item_name]

    entity.update(result)
  client.put(entity)

  if cart_cmd == 'add':
    message = 'Great! You\'ve added an item to the cart.'
  else:
    message = 'You\'ve removed an item from the cart.'

  message_obj = BusinessMessagesMessage(
      messageId=str(uuid.uuid4().int),
      representative=BOT_REPRESENTATIVE,
      text=message,
      suggestions=[
          BusinessMessagesSuggestion(
              reply=BusinessMessagesSuggestedReply(
                  text='Review shopping cart', postbackData=CMD_SHOW_CART)),
          BusinessMessagesSuggestion(
              reply=BusinessMessagesSuggestedReply(
                  text='See menu again',
                  postbackData=CMD_SHOW_PRODUCT_CATALOG)),
      ])

  send_message(message_obj, conversation_id)


def send_shopping_cart(conversation_id):
  """Sends a shopping cart to the user as a rich card carousel.

  Args:
    conversation_id (str): The unique id for this user and agent.
  """
  credentials = service_account.Credentials.from_service_account_file(
      SERVICE_ACCOUNT_LOCATION)

  # Retrieve the inventory data
  inventory = get_inventory_data()

  # Pull the data from Google Datastore
  client = datastore.Client(credentials=credentials)
  key = client.key('ShoppingCart', conversation_id)
  result = client.get(key)

  shopping_cart_suggestions = [
      BusinessMessagesSuggestion(
          reply=BusinessMessagesSuggestedReply(
              text='See total price', postbackData='show-cart-price')),
      BusinessMessagesSuggestion(
          reply=BusinessMessagesSuggestedReply(
              text='Empty the cart', postbackData='empty-cart')),
      BusinessMessagesSuggestion(
          reply=BusinessMessagesSuggestedReply(
              text='See the menu', postbackData=CMD_SHOW_PRODUCT_CATALOG)),
  ]

  if len(result.items()) == 0:
    message_obj = BusinessMessagesMessage(
        messageId=str(uuid.uuid4().int),
        representative=BOT_REPRESENTATIVE,
        text='There are no items in your shopping cart.',
        suggestions=shopping_cart_suggestions)

    send_message(message_obj, conversation_id)
  elif len(result.items()) == 1:

    for product_name, quantity in result.items():
      product_id = get_id_by_product_name(product_name)

      fallback_text = ('You have one type of item in the shopping cart')

      rich_card = BusinessMessagesRichCard(
          standaloneCard=BusinessMessagesStandaloneCard(
              cardContent=BusinessMessagesCardContent(
                  title=product_name,
                  description=f'{quantity} in cart.',
                  suggestions=[
                      BusinessMessagesSuggestion(
                          reply=BusinessMessagesSuggestedReply(
                              text='Remove one',
                              postbackData=f'{CMD_DEL_ITEM}-{product_id}'))
                  ],
                  media=BusinessMessagesMedia(
                      height=BusinessMessagesMedia.HeightValueValuesEnum.MEDIUM,
                      contentInfo=BusinessMessagesContentInfo(
                          fileUrl=inventory['food'][product_id]
                          ['image_url'],
                          forceRefresh=False)))))

      message_obj = BusinessMessagesMessage(
          messageId=str(uuid.uuid4().int),
          representative=BOT_REPRESENTATIVE,
          richCard=rich_card,
          suggestions=shopping_cart_suggestions,
          fallback=fallback_text)

      send_message(message_obj, conversation_id)
  else:
    cart_carousel_items = []

    # Iterate through the cart and generate a carousel of items
    for product_name, quantity in result.items():
      product_id = get_id_by_product_name(product_name)

      cart_carousel_items.append(
          BusinessMessagesCardContent(
              title=product_name,
              description=f'{quantity} in cart.',
              suggestions=[
                  BusinessMessagesSuggestion(
                      reply=BusinessMessagesSuggestedReply(
                          text='Remove one',
                          postbackData=f'{CMD_DEL_ITEM}-{product_id}'))
              ],
              media=BusinessMessagesMedia(
                  height=BusinessMessagesMedia.HeightValueValuesEnum.MEDIUM,
                  contentInfo=BusinessMessagesContentInfo(
                      fileUrl=inventory['food'][product_id]
                      ['image_url'],
                      forceRefresh=False))))

    rich_card = BusinessMessagesRichCard(
        carouselCard=BusinessMessagesCarouselCard(
            cardContents=cart_carousel_items,
            cardWidth=BusinessMessagesCarouselCard.CardWidthValueValuesEnum
            .MEDIUM))

    fallback_text = ''

    # Construct a fallback text for devices that do not support carousels
    for card_content in rich_card.carouselCard.cardContents:
      fallback_text += (
          card_content.title + '\n\n' + card_content.description + '\n\n' +
          card_content.media.contentInfo.fileUrl +
          '\n---------------------------------------------\n\n')

    message_obj = BusinessMessagesMessage(
        messageId=str(uuid.uuid4().int),
        representative=BOT_REPRESENTATIVE,
        richCard=rich_card,
        suggestions=shopping_cart_suggestions,
        fallback=fallback_text,
    )

    send_message(message_obj, conversation_id)


def send_message(message, conversation_id):
  """Sends a message to the user over Business Messages.

  Posts a message to the Business Messages API, first sending
  a typing indicator event and sending a stop typing event after
  the message has been sent.

  Args:
    message (obj): The message object payload to send to the user.
    conversation_id (str): The unique id for this user and agent.
  """
  credentials = ServiceAccountCredentials.from_json_keyfile_name(
      SERVICE_ACCOUNT_LOCATION,
      scopes=['https://www.googleapis.com/auth/businessmessages'])

  client = bm_client.BusinessmessagesV1(credentials=credentials)

  # Create the message request
  create_request = BusinessmessagesConversationsMessagesCreateRequest(
      businessMessagesMessage=message,
      parent='conversations/' + conversation_id)

  bm_client.BusinessmessagesV1.ConversationsMessagesService(
      client=client).Create(request=create_request)


def get_sample_carousel():
  """Creates a sample carousel rich card.

  Returns:
    A :obj: A BusinessMessagesCarouselCard object with three cards.
  """
  card_content = []

  for i, sample_image in enumerate(SAMPLE_IMAGES):
    card_content.append(
        BusinessMessagesCardContent(
            title='Card #' + str(i),
            description='This is a sample card',
            suggestions=get_sample_suggestions(),
            media=BusinessMessagesMedia(
                height=BusinessMessagesMedia.HeightValueValuesEnum.MEDIUM,
                contentInfo=BusinessMessagesContentInfo(
                    fileUrl=sample_image, forceRefresh=False))))

  return BusinessMessagesCarouselCard(
      cardContents=card_content,
      cardWidth=BusinessMessagesCarouselCard.CardWidthValueValuesEnum.MEDIUM)


def get_shopping_suggestions():
  """Creates a list of shopping cart suggestions.

  Returns:
    A :list: A list of sample BusinessMessagesSuggestions.
  """
  return [
      BusinessMessagesSuggestion(
          reply=BusinessMessagesSuggestedReply(
              text='See my cart', postbackData='show_cart')),
      BusinessMessagesSuggestion(
          reply=BusinessMessagesSuggestedReply(
              text='See the menu', postbackData=CMD_SHOW_PRODUCT_CATALOG)),
  ]


def get_sample_suggestions():
  """Creates a list of sample suggestions that includes a suggested reply.

  Returns:
      A :list: A list of sample BusinessMessagesSuggestions.
  """
  return [
      BusinessMessagesSuggestion(
          reply=BusinessMessagesSuggestedReply(
              text='Sample Chip', postbackData='sample_chip')),
      BusinessMessagesSuggestion(
          action=BusinessMessagesSuggestedAction(
              text='URL Action',
              postbackData='url_action',
              openUrlAction=BusinessMessagesOpenUrlAction(
                  url='https://www.google.com'))),
      BusinessMessagesSuggestion(
          action=BusinessMessagesSuggestedAction(
              text='Dial Action',
              postbackData='dial_action',
              dialAction=BusinessMessagesDialAction(
                  phoneNumber='+12223334444'))),
  ]


def landing_placeholder(request):
  """Creates an HttpResponse for a user browsing to the root of the site.

  Args:
      request (HttpRequest): The request object that django passes to the
        function

  Returns:
      An :HttpResponse: containing browser renderable HTML.
  """

  return HttpResponse("""
  <h1>Welcome to the Bonjour Meal Codelab</h1>
  <br/><br/>
  To message your Bonjour Meal agent, go to the Developer Console and retrieve
    the Test URLs for the agent you have created as described in the codelab
    <a href='#'>here</a>.
  """)
