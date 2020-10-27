# Bonjour Meal - Full sample using CloudSQL for storage of inventory

This is the Bonjour Meal sample code shown in the video screencast. It uses
CloudSQL to store inventory items, conversationsIds, their associated
shopping carts, and everything else that is persisted.

To use this sample, you'll need to create a GCP project, you'll need to do all
the standard set up involved in the regular codelab as well as enable CloudSQL,
set it up with MySQL, create a database titled "bonjour_meal" with a user named
"bmdbuser" and password set to "bmdbpassword". You can also set your own
credentials, just update them in bmcodelab/settings.py.

At this point, CloudSQL will give you a hostname for the CloudSQL instance.
Take this hostname and update the string "Place/your/CloudSQL/hostname/here" in
bmcodelab/settings.py to be the hostname associated with your CloudSQL instance.

Then you can deploy this project to App Engine. The agent you created for this
codelab should then exhibit the same behavior seen in the screencast.