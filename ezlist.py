#!/usr/bin/env python3
"""ezlist - A minimal mailing list manager which is easy to set up.

Written by qll (github.com/qll), distributed under the MIT license.
"""
import argparse
import base64
import contextlib
import email
import email.mime.text
import imaplib
import logging
import logging.config
import os
import re
import smtplib
import sqlite3
import time


class IMAPInbox:
    def __init__(self, host, port, username, password, inbox='INBOX',
                 ssl=False, startssl=False):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.inbox = inbox
        self.ssl = ssl
        self.startssl = startssl
        self.imap = None

    def __enter__(self):
        """Connect to the IMAP server."""
        if self.ssl:
            self.imap = imaplib.IMAP4_SSL(self.host, self.port)
        elif self.startssl:
            self.imap = imaplib.IMAP4(self.host, self.port)
            self.imap.starttls()
        else:
            self.imap = imaplib.IMAP4(self.host, self.port)
        self.imap.login(self.username, self.password)
        self.imap.select(mailbox=self.inbox)
        return self

    def __exit__(self, type, value, traceback):
        """Disconnect from the IMAP server."""
        # remove deleted messages from mailbox
        self.imap.close()
        # be nice and say BYE to the server
        self.imap.logout()

    def fetch_all(self):
        """Fetch all mail from the inbox."""
        _, data = self.imap.search(None, 'ALL')
        for mail_id in data[0].decode().split(' '):
            if mail_id:
                _, data = self.imap.fetch(mail_id, '(RFC822)')
                yield mail_id, email.message_from_bytes(data[0][1])

    def delete(self, mail_id):
        """Mark a mail as deleted."""
        self.imap.store(mail_id, '+FLAGS', '\\Deleted')


class SMTPSender:
    def __init__(self, host, port, domain, username, password, ssl=False,
                 startssl=False):
        self.host = host
        self.port = port
        self.domain = domain
        self.username = username
        self.password = password
        self.ssl = ssl
        self.startssl = startssl
        self.smtp = None

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        try:
            if self.smtp is not None:
                self.smtp.quit()
        except smtplib.SMTPServerDisconnected:
            pass

    def _connect(self):
        """Connect to the SMTP server."""
        if self.smtp is None:
            if self.ssl:
                self.smtp = smtplib.SMTP_SSL(self.host, self.port, self.domain)
            elif self.startssl:
                self.smtp = smtplib.SMTP(self.host, self.port, self.domain)
                self.smtp.starttls()
            else:
                self.smtp = smtplib.SMTP(self.host, self.port, self.domain)
            self.smtp.login(self.username, self.password)

    def send(self, from_, to, mail):
        """Send mail. Connect lazily if required."""
        self._connect()
        try:
            self.smtp.sendmail(from_, to, mail.as_string())
        except smtplib.SMTPServerDisconnected:
            self.smtp = None
            self.send(from_, to, mail)


class SQLiteStorage:
    INITIAL_SQL = '''CREATE TABLE subscribers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT,
        deletion_key TEXT
    );
    CREATE TABLE unverified (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT,
        activation_key TEXT
    )
    '''

    def __init__(self, path):
        db_existed = os.path.isfile(path)
        self._db = sqlite3.connect(path)
        if not db_existed:
            for statement in self.INITIAL_SQL.split(';'):
                self._db.execute(statement)

    def _query(self, sql, params=[]):
        if isinstance(params, str):
            params = (params,)
        with contextlib.closing(self._db.cursor()) as cursor:
            cursor.execute(sql, params)
            result = cursor.fetchall()
            self._db.commit()
            return result

    def is_unverified(self, addr, activation_key):
        return self._query('SELECT id FROM unverified WHERE email=? AND '
                           'activation_key=?', (addr, activation_key))

    def add_unverified(self, addr, activation_key):
        self._query('INSERT INTO unverified (email, activation_key) VALUES '
                    '(?, ?)', (addr, activation_key))

    def delete_unverified(self, addr):
        self._query('DELETE FROM unverified WHERE email=?', addr)

    def is_subscribed(self, addr, deletion_key=''):
        sql = 'SELECT id FROM subscribers WHERE email=?'
        params = [addr]
        if deletion_key:
            sql += ' AND deletion_key=?'
            params.append(deletion_key)
        return self._query(sql, params)

    def add_subscriber(self, addr, deletion_key):
        self._query('INSERT INTO subscribers (email, deletion_key) VALUES '
                    '(?, ?)', (addr, deletion_key))

    def get_deletion_key(self, addr):
        return self._query('SELECT deletion_key FROM subscribers WHERE '
                           'email=?', addr)[0][0]

    def delete_subscriber(self, addr):
        self._query('DELETE FROM subscribers WHERE email=?', addr)

    def get_subscribers(self):
        return (i[0] for i in self._query('SELECT email FROM subscribers'))


class UserError(Exception):
    pass


def assert_managing_subscriptions(func):
    """Assert that manage_subscriptions has been enabled."""
    def wrapper(self, *args, **kwargs):
        if not self.manage_subscriptions:
            printable_args = [(self._desc_mail(obj)
                               if isinstance(obj, email.message.Message) else
                               obj)
                              for obj in args]
            raise UserError('Blocked %s %s %s: Subscription managment disabled'
                            % (func.__name__, printable_args, kwargs))
        return func(self, *args, **kwargs)
    return wrapper


def assert_is_subscriber(func):
    """Assert that first arg is a valid subscriber."""
    def wrapper(self, addr, *args, **kwargs):
        if not self.storage.is_subscribed(addr):
            printable_args = [(self._desc_mail(obj)
                               if isinstance(obj, email.message.Message) else
                               obj)
                              for obj in args]
            raise UserError('Blocked %s %s %s: E-Mail is not a subscriber'
                            % (func.__name__, printable_args, kwargs))
        return func(self, addr, *args, **kwargs)
    return wrapper


class Manager:
    VERIFY_REGEX = re.compile(r'verify <([A-Za-z0-9+=/]+?)>')
    UNSUBSCRIBE_REGEX = re.compile(r'unsubscribe <([A-Za-z0-9+=/]+?)>')
    CLEAN_SUBJECT_REGEX = re.compile(r'^(?:\w{2,3}:\s*)*(.*)$')

    def __init__(self, mail_addr, inbox, sender, storage,
                 subject_prefix='[List]', skip_sender=True,
                 manage_subscriptions=True, default_language='en'):
        self.mail_addr = mail_addr
        self.inbox = inbox
        self.sender = sender
        self.storage = storage
        self.subject_prefix = subject_prefix
        self.skip_sender = skip_sender
        self.manage_subscriptions = manage_subscriptions
        self.default_language = default_language

        # automated mail list response emails
        self.SUBSCRIPTION_MAIL_TEXT = open("./i18n/{0}/subscription_mail.txt".format(self.default_language), 'r').read()
        self.VERIFICATION_MAIL_TEXT = open("./i18n/{0}/verification_mail.txt".format(self.default_language), 'r').read()
        self.UNSUBSCRIBE_MAIL_TEXT = open("./i18n/{0}/unsubscribe_mail.txt".format(self.default_language), 'r').read()
        self.DELETION_KEY_MAIL_TEXT = open("./i18n/{0}/deletion_key_mail.txt".format(self.default_language), 'r').read()

    def _extract_mail_addrs(self, header_value):
        if header_value is None:
            return []
        # let's not allow too fancy mail addresses
        return re.findall(r'[\w.%+-]+@[\w.%+-]+', header_value)

    def _get_sender(self, mail):
        """Get sender from an email message."""
        addrs = self._extract_mail_addrs(mail.get('From', ''))
        return addrs[0] if len(addrs) > 0 else 'unknown'

    def _desc_mail(self, mail):
        """Describe a mail in a sufficiently recognizable manner."""
        sender = self._get_sender(mail)
        return '<{}, subject "{}">'.format(sender, mail.get('Subject', ''))

    def _clean_mail(self, mail):
        """Delete unknown header fields but do not destroy the message"""
        whitelist = ('From', 'To', 'Subject', 'Date', 'Reply-To',
                     'Content-Type', 'Content-Transfer-Encoding',
                     'In-Reply-To', 'References', 'Message-ID')
        for header in mail.keys():
            if header not in whitelist:
                del mail[header]

    def _create_mail(self, from_, to, subject, text):
        mail = email.mime.text.MIMEText(text)
        mail['Subject'] = '{} {}'.format(self.subject_prefix, subject)
        mail['From'] = from_
        mail['To'] = to
        return mail

    def _create_unique_key(self):
        return base64.b64encode(os.urandom(16)).decode()

    def is_directed_at_list(self, mail):
        addrs = (self._extract_mail_addrs(mail.get('To')) +
                 self._extract_mail_addrs(mail.get('Cc', '')) +
                 self._extract_mail_addrs(mail.get('Bcc', '')))
        return any(self.mail_addr == addr
                   for addr in addrs)

    @assert_managing_subscriptions
    def subscribe(self, addr):
        if self.storage.is_subscribed(addr):
            raise UserError('Subscription attempt from %s, although already '
                            'subscribed' % addr)
        logging.info('%s is now unverified', addr)
        activation_key = self._create_unique_key()
        logging.debug('%s has activation_key %s', addr, activation_key)
        self.storage.add_unverified(addr, activation_key)
        self._send_subscription_mail(addr, activation_key)
        return activation_key

    def _send_subscription_mail(self, addr, activation_key):
        mail_text = self.SUBSCRIPTION_MAIL_TEXT.format(list=self.mail_addr)
        mail_subj = 'verify <{}>'.format(activation_key)
        mail = self._create_mail(self.mail_addr, addr, mail_subj, mail_text)
        self.sender.send(self.mail_addr, addr, mail)

    @assert_managing_subscriptions
    def verify(self, addr, activation_key):
        if self.storage.is_subscribed(addr):
            raise UserError('Verification attempt from %s, although already '
                            'verified' % addr)
        if not self.storage.is_unverified(addr, activation_key):
            raise UserError('Verification for %s failed because of wrong '
                            'activation_key (%s)' % (addr, activation_key))
        deletion_key = self._create_unique_key()
        self.storage.add_subscriber(addr, deletion_key)
        logging.info('%s is now a subscriber', addr)
        self.storage.delete_unverified(addr)
        self._send_verification_mail(addr, deletion_key)
        return deletion_key

    def _send_verification_mail(self, addr, deletion_key):
        mail_text = self.VERIFICATION_MAIL_TEXT.format(list=self.mail_addr,
                                                       key=deletion_key)
        mail_subj = 'You have successfully joined the mailing list'
        mail = self._create_mail(self.mail_addr, addr, mail_subj, mail_text)
        self.sender.send(self.mail_addr, addr, mail)

    @assert_is_subscriber
    @assert_managing_subscriptions
    def send_deletion_key(self, addr):
        deletion_key = self.storage.get_deletion_key(addr)
        mail_text = self.DELETION_KEY_MAIL_TEXT.format(list=self.mail_addr)
        mail_subj = 'unsubscribe <{}>'.format(deletion_key)
        mail = self._create_mail(self.mail_addr, addr, mail_subj, mail_text)
        self.sender.send(self.mail_addr, addr, mail)

    @assert_is_subscriber
    @assert_managing_subscriptions
    def unsubscribe(self, addr, deletion_key):
        if not self.storage.is_subscribed(addr, deletion_key):
            raise UserError('Unsubscription for %s failed because of wrong '
                            'deletion_key (%s)' % (addr, deletion_key))
        self.storage.delete_subscriber(addr)
        logging.info('Unsubscribing %s', addr)
        self._send_unsubscribe_mail(addr)

    def _send_unsubscribe_mail(self, addr):
        mail_text = self.UNSUBSCRIBE_MAIL_TEXT.format(list=self.mail_addr)
        mail_subj = 'You have successfully unsubscribed from this list'
        mail = self._create_mail(self.mail_addr, addr, mail_subj, mail_text)
        self.sender.send(self.mail_addr, addr, mail)

    @assert_is_subscriber
    def forward(self, addr, mail, exclude=set()):
        logging.info('Forward %s', self._desc_mail(mail))
        self._clean_mail(mail)
        mail.add_header('List-Post', '<mailto:%s>' % self.mail_addr)
        subject = mail.get('Subject')
        if subject is None:
            mail.add_header('Subject', '%s (empty subject)'
                                        % self.subject_prefix)
        else:
            subject_match = self.CLEAN_SUBJECT_REGEX.search(subject)
            if subject_match:
                clean_subject = subject_match.group(1)
                if not clean_subject.strip().startswith(self.subject_prefix):
                    mail.replace_header('Subject', '%s %s'
                                        % (self.subject_prefix, clean_subject))
        for subscriber in self.storage.get_subscribers():
            if subscriber not in exclude:
                self.sender.send(self.mail_addr, subscriber, mail)

    def process(self):
        with self.inbox, self.sender:
            for mail_id, mail in self.inbox.fetch_all():
                try:
                    sender = self._get_sender(mail)
                    subject = mail.get('Subject', '').strip()
                    if not self.is_directed_at_list(mail):
                        pass
                    elif subject.lower() == 'subscribe':
                        self.subscribe(sender)
                    elif subject.lower() == 'unsubscribe':
                        self.send_deletion_key(sender)
                    elif self.VERIFY_REGEX.search(subject):
                        match = self.VERIFY_REGEX.search(subject)
                        self.verify(sender, match.group(1))
                    elif self.UNSUBSCRIBE_REGEX.search(subject):
                        match = self.UNSUBSCRIBE_REGEX.search(subject)
                        self.unsubscribe(sender, match.group(1))
                    else:
                        exclude = [sender] if self.skip_sender else []
                        self.forward(sender, mail, exclude=exclude)
                    self.inbox.delete(mail_id)
                except UserError as error:
                    logging.warning(str(error))
                    self.inbox.delete(mail_id)
                except:
                    logging.exception('Exception while processing %s',
                                      self._desc_mail(mail))


def main(interval, manager):
    try:
        logging.debug('Starting...')
        while True:
            manager.process()
            time.sleep(interval)
    except KeyboardInterrupt:
        pass


def _parse_cmdline():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-s', '--settings', default='settings.py',
                        help='path to the settings file')
    return parser.parse_args()


def _load_settings(settings_path):
    defaults = {
        'POLLING_INTERVAL': 30,
        'LOGGING': {
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
            },
            'loggers': {
                '': {
                    'handlers': ['default'],
                    'level': 'DEBUG',
                    'propagate': True
                }
            }
        }
    }
    user_settings = {}
    with open(settings_path) as settings_file:
        # associate settings file name with exec'd code
        code = compile(settings_file.read(), settings_path, 'exec')
        # exec since import requires sys.path hacks
        exec(code, globals(), user_settings)
    defaults.update(user_settings)
    return defaults


if __name__ == '__main__':
    args = _parse_cmdline()
    settings = _load_settings(args.settings)
    logging.config.dictConfig(settings['LOGGING'])
    main(settings['POLLING_INTERVAL'], settings['MANAGER'])
