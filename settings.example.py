"""This is an ezlist configuration file.

You may use Python code to set values for the various options. Each option will
be accompanied by a short description.
"""


# how often should the mail server be polled for new mails in seconds
POLLING_INTERVAL = 30


# storage persists subscribers to disk
storage = SQLiteStorage(
    path='data.sqlite'  # Path to the SQLite database
)


# inbox is used to load new mail
inbox = IMAPInbox(
    host='imap.gmail.com',  # IMAP host (e.g. imap.gmail.com)
    port=993,               # port of the IMAP service
    username='test',        # IMAP username
    password='test',        # IMAP password
    inbox='INBOX',          # name of the inbox folder (e.g. INBOX)
    ssl=True,               # use SSL/TLS?
    startssl=False          # use STARTSSL? (if ssl=True, this will be ignored)
)


# outgoing mails are sent via the sender class
sender = SMTPSender(
    host='smtp.gmail.com',  # SMTP host (e.g. smtp.gmail.com)
    port=465,               # port of the SMTP service
    domain='gmail.com',     # domain of address (gmail.com for test@gmail.com)
    username='test',        # SMTP username
    password='test',        # SMTP password
    ssl=True,               # use SSL/TLS?
    startssl=False          # use STARTSSL? (if ssl=True, this will be ignored)
)


# a manager implements the core functionality of the mailing list
MANAGER = Manager(
    mail_addr='test@gmail.com',  # the address of the mailing list
    inbox=inbox,
    sender=sender,
    storage=storage,
    subject_prefix='[List]',     # how to prefix all mails on the list
    skip_sender=True,            # should a sender get his own email forwarded?
    manage_subscriptions=True,    # subscriptions/unsubscriptions allowed?
    default_language='tr'        # default language for automated emails
)


# control how messages are printed, if and how they are written to a logfile
# refer to https://docs.python.org/3/library/logging.config.html
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '[%(levelname)s]%(asctime)s: %(message)s',
            'datefmt': '%d.%m.%Y/%H:%S',
        },
    },
    'handlers': {
        'default': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'standard'
        },
        # this probably is what you'd want in a daemonized setting:
        # 'file': {
        #     'level': 'INFO',
        #     'class': 'logging.FileHandler',
        #     'filename': 'storage/bot.log',
        #     'formatter': 'standard'
        # }
    },
    'loggers': {
        '': {
            'handlers': ['default'],
            'level': 'DEBUG',
            'propagate': True
        }
    }
}
