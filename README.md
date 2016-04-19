# ezlist #
Looking for a dead simple mailing list manager? No GUI, no website and working
out-of-the-box with a standard IMAP/SMTP mailbox? Look no more, this is it.

Here is what it does for you:

- Manage subscriptions/unsubscriptions (or not if you tell it to)
- Forward subscriber emails to list (aka the core functionality)
- Work from a single mail address (could be yourstupidlist@gmail.com)

Here are a few things it does *not* do for you:

- Moderation of list
- Fancy web interface
- Deleting "dead" subscribers on bounce (or VERP if you're super pro)

Any of those features have to be written by yourself. This makes this software
only useful in small and controlled environments where you don't shy away from
writing a script yourself. Many parts can be easily replaced via configuration
and I will soon add examples of how to do so.


## Installation ##
You need to have Python 3 and that's it. Simply clone this repository, change
the configuration to your liking and start the mailing list.

```sh
# either look for a settings.py in the same dir
./ezlist.py
# or
./ezlist.py -s somewhere/are/the/settings.py
```
