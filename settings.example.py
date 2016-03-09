POLLING_INTERVAL = 20


MANAGER_CLASS = 'Manager'
MANAGER_ARGS = {
    'mail_addr': 'mailinglist@anything.com',
    'manage_subscriptions': True,
    'skip_sender': True,
    'subject_prefix': '[List]',
}


STORAGE_CLASS = 'SQLiteStorage'
STORAGE_ARGS = {
    'path': 'data.sqlite',
}


INBOX_CLASS = 'IMAPInbox'
INBOX_ARGS = {
    'host': 'anything.com',
    'port': 143,
    'username': 'mailinglist',
    'password': 'something',
    'inbox': 'INBOX',
    'ssl': False,
    'startssl': False,
}


SENDER_CLASS = 'SMTPSender'
SENDER_ARGS = {
    'host': 'anything.com',
    'port': 25,
    'domain': 'anything.com',
    'username': 'mailinglist',
    'password': 'something',
    'ssl': False,
    'startssl': False,
}


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
            'level': 'INFO',
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
            'level': 'INFO',
            'propagate': True
        }
    }
}
