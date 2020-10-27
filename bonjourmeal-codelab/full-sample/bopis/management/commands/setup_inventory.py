# Generated by Django 3.0.8 on 2020-10-14 03:39

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
Django management command to populate data in CloudSQL database.
'''

from django.core.management.base import BaseCommand, CommandError
from bopis.models import *

import json

class Command(BaseCommand):
    help = 'Setups up the inventory with Bonjour Meal Food & Drink Items'

    def handle(self, *args, **options):

        items = Item.objects.all()
        for i in items:
            i.delete()

        with open('bopis/management/commands/inventory_items.json') as json_file:
            data = json.load(json_file)
            for item in data['inventory']:
                print(item['name'])
                new_item = Item(
                    name=item['name'],
                    image_url=item['image_url'],
                    price=item['price'],
                    currency="USD"
                )
                new_item.save()