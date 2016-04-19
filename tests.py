#!/usr/bin/env python3
import email.mime.text
import ezlist
import unittest
import unittest.mock as mock


def _build_mail(subject='Test Subject', from_='sender@test.com',
                to='recipient@test.com', text='Test Text'):
    mail = email.mime.text.MIMEText(text)
    mail['Subject'] = subject
    mail['From'] = from_
    mail['To'] = to
    return mail


class IMAPInboxTest(unittest.TestCase):
    def build_inbox(self, **kwargs):
        options = {
            'host': 'localhost',
            'port': 7357,
            'username': 'test',
            'password': 'test',
            'inbox': 'INBOX',
            'ssl': False,
            'startssl': False
        }
        options.update(kwargs)
        return ezlist.IMAPInbox(**options)

    @mock.patch('imaplib.IMAP4')
    def test_connect(self, imap):
        inbox = self.build_inbox()
        imap.assert_not_called()
        with inbox:
            imap.assert_called_once_with('localhost', 7357)
        imap.return_value.close.assert_called_once_with()

    @mock.patch('imaplib.IMAP4_SSL')
    def test_connect_ssl(self, imap_ssl):
        inbox = self.build_inbox(ssl=True)
        imap_ssl.assert_not_called()
        with inbox:
            imap_ssl.assert_called_once_with('localhost', 7357)
        imap_ssl.return_value.close.assert_called_once_with()

    @mock.patch('imaplib.IMAP4')
    def test_connect_startssl(self, imap):
        inbox = self.build_inbox(startssl=True)
        imap.assert_not_called()
        with inbox:
            imap.assert_called_once_with('localhost', 7357)
            imap.return_value.starttls.assert_called_once_with()
        imap.return_value.close.assert_called_once_with()

    @mock.patch('imaplib.IMAP4_SSL')
    def test_connect_ssl_over_startssl(self, imap_ssl):
        inbox = self.build_inbox(ssl=True, startssl=True)
        imap_ssl.assert_not_called()
        with inbox:
            imap_ssl.assert_called_once_with('localhost', 7357)
        imap_ssl.return_value.close.assert_called_once_with()


class SMTPInboxTest(unittest.TestCase):
    def build_sender(self, **kwargs):
        options = {
            'host': 'localhost',
            'port': 7357,
            'domain': 'test.de',
            'username': 'test',
            'password': 'test',
            'ssl': False,
            'startssl': False
        }
        options.update(kwargs)
        return ezlist.SMTPSender(**options)

    @mock.patch('smtplib.SMTP')
    def test_connect(self, smtp):
        sender = self.build_sender()
        smtp.assert_not_called()
        with sender:
            smtp.assert_not_called()  # lazy connect
            sender.send('sender@test.com', 'recipient@test.com', _build_mail())
            smtp.assert_called_once_with('localhost', 7357, 'test.de')
        smtp.return_value.quit.assert_called_once_with()

    @mock.patch('smtplib.SMTP_SSL')
    def test_connect_ssl(self, smtp_ssl):
        sender = self.build_sender(ssl=True)
        smtp_ssl.assert_not_called()
        with sender:
            smtp_ssl.assert_not_called()  # lazy connect
            sender.send('sender@test.com', 'recipient@test.com', _build_mail())
            smtp_ssl.assert_called_once_with('localhost', 7357, 'test.de')
        smtp_ssl.return_value.quit.assert_called_once_with()

    @mock.patch('smtplib.SMTP')
    def test_connect_startssl(self, smtp):
        sender = self.build_sender(startssl=True)
        smtp.assert_not_called()
        with sender:
            smtp.assert_not_called()  # lazy connect
            sender.send('sender@test.com', 'recipient@test.com', _build_mail())
            smtp.assert_called_once_with('localhost', 7357, 'test.de')
            smtp.return_value.starttls.assert_called_once_with()
        smtp.return_value.quit.assert_called_once_with()

    @mock.patch('smtplib.SMTP_SSL')
    def test_connect_ssl_over_startssl(self, smtp_ssl):
        sender = self.build_sender(ssl=True, startssl=True)
        smtp_ssl.assert_not_called()
        with sender:
            smtp_ssl.assert_not_called()  # lazy connect
            sender.send('sender@test.com', 'recipient@test.com', _build_mail())
            smtp_ssl.assert_called_once_with('localhost', 7357, 'test.de')
        smtp_ssl.return_value.quit.assert_called_once_with()


class SQLiteStorageTest(unittest.TestCase):
    EMAIL = 'test@test.com'
    KEY = 'key'
    EMAIL2 = 'test2@test.com'
    KEY2 = 'key2'

    def setUp(self):
        self.storage = ezlist.SQLiteStorage(':memory:')

    def test_add_unverified(self):
        self.storage.add_unverified(self.EMAIL, self.KEY)
        self.assertTrue(self.storage.is_unverified(self.EMAIL, self.KEY))
        self.assertFalse(self.storage.is_unverified(self.EMAIL, 'otherkey'))
        self.assertFalse(self.storage.is_unverified('xy@test.com', self.KEY))
        self.assertFalse(self.storage.is_subscribed(self.EMAIL))

    def test_delete_unverified(self):
        self.storage.add_unverified(self.EMAIL, self.KEY)
        self.storage.delete_unverified(self.EMAIL)
        self.assertFalse(self.storage.is_unverified(self.EMAIL, self.KEY))

    def test_add_subscriber(self):
        self.storage.add_subscriber(self.EMAIL, self.KEY)
        self.assertTrue(self.storage.is_subscribed(self.EMAIL))
        self.assertTrue(self.storage.is_subscribed(self.EMAIL, self.KEY))
        self.assertFalse(self.storage.is_subscribed(self.EMAIL, 'otherkey'))
        self.assertFalse(self.storage.is_subscribed('xy@test.com', self.KEY))
        self.assertFalse(self.storage.is_unverified(self.EMAIL, self.KEY))

    def test_delete_subscriber(self):
        self.storage.add_subscriber(self.EMAIL, self.KEY)
        self.storage.delete_subscriber(self.EMAIL)
        self.assertFalse(self.storage.is_subscribed(self.EMAIL))
        self.assertFalse(self.storage.is_subscribed(self.EMAIL, self.KEY))

    def test_get_subscribers(self):
        self.assertEqual([], list(self.storage.get_subscribers()))
        self.storage.add_subscriber(self.EMAIL, self.KEY)
        self.assertEqual([self.EMAIL], list(self.storage.get_subscribers()))
        self.storage.add_subscriber(self.EMAIL2, self.KEY2)
        self.assertEqual([self.EMAIL, self.EMAIL2],
                         list(self.storage.get_subscribers()))
        self.storage.delete_subscriber(self.EMAIL)
        self.assertEqual([self.EMAIL2], list(self.storage.get_subscribers()))


class ManagerTest(unittest.TestCase):
    EMAIL = 'foo@bar.com'
    KEY = 'key'
    EMAIL2 = 'foo2@bar.com'
    KEY2 = 'key2'
    LIST_EMAIL = 'list@test.com'
    SUBJECT_PREFIX = '[TestList]'

    def build_manager(self, **kwargs):
        options = {
            'mail_addr': self.LIST_EMAIL,
            'inbox': mock.MagicMock(),
            'sender': mock.MagicMock(),
            'storage': ezlist.SQLiteStorage(':memory:'),
            'subject_prefix': self.SUBJECT_PREFIX,
            'skip_sender': True,
            'manage_subscriptions': True
        }
        options.update(kwargs)
        return ezlist.Manager(**options)

    def test_is_directed_at_list(self):
        manager = self.build_manager()
        mail = _build_mail(to=self.LIST_EMAIL)
        self.assertTrue(manager.is_directed_at_list(mail))
        mail = _build_mail(to=self.EMAIL)
        self.assertFalse(manager.is_directed_at_list(mail))
        mail = _build_mail(to='Mailinglist <%s>' % self.LIST_EMAIL)
        self.assertTrue(manager.is_directed_at_list(mail))

    def test_subscribe(self):
        manager = self.build_manager()
        key = manager.subscribe(self.EMAIL)
        self.assertTrue(len(key) > 12)
        self.assertTrue(manager.storage.is_unverified(self.EMAIL, key))
        self.assertTrue(manager.sender.send.called)
        mail = manager.sender.send.call_args[0][2]
        self.assertTrue(mail['Subject'].startswith(self.SUBJECT_PREFIX))
        self.assertTrue(key in mail['Subject'])
        self.assertTrue(self.EMAIL in mail['To'])
        self.assertTrue(self.LIST_EMAIL in mail['From'])

    def test_subscribe_already_subscribed(self):
        manager = self.build_manager()
        manager.storage.add_subscriber(self.EMAIL, self.KEY)
        with self.assertRaises(ezlist.UserError):
            manager.subscribe(self.EMAIL)

    def test_subscribe_while_subscription_disabled(self):
        manager = self.build_manager(manage_subscriptions=False)
        with self.assertRaises(ezlist.UserError):
            manager.subscribe(self.EMAIL)

    def test_unsubscribe(self):
        manager = self.build_manager()
        manager.storage.add_subscriber(self.EMAIL, self.KEY)
        manager.unsubscribe(self.EMAIL, self.KEY)
        self.assertFalse(manager.storage.is_subscribed(self.EMAIL))
        self.assertTrue(manager.sender.send.called)

    def test_unsubscribe_not_subscribed(self):
        manager = self.build_manager()
        with self.assertRaises(ezlist.UserError):
            manager.unsubscribe(self.EMAIL, self.KEY)

    def test_unsubscribe_while_subscription_disabled(self):
        manager = self.build_manager(manage_subscriptions=False)
        manager.storage.add_subscriber(self.EMAIL, self.KEY)
        with self.assertRaises(ezlist.UserError):
            manager.unsubscribe(self.EMAIL, self.KEY)

    def test_unsubscribe_wrong_deletion_key(self):
        manager = self.build_manager()
        manager.storage.add_subscriber(self.EMAIL, self.KEY)
        with self.assertRaises(ezlist.UserError):
            manager.unsubscribe(self.EMAIL, 'wrong_key')

    def test_send_deletion_key(self):
        manager = self.build_manager()
        manager.storage.add_subscriber(self.EMAIL, self.KEY)
        manager.send_deletion_key(self.EMAIL)
        self.assertTrue(manager.sender.send.called)
        mail = manager.sender.send.call_args[0][2]
        self.assertTrue(self.KEY in mail['Subject'])

    def test_send_deletion_key_not_subscribed(self):
        manager = self.build_manager()
        with self.assertRaises(ezlist.UserError):
            manager.send_deletion_key(self.EMAIL)

    def test_verify(self):
        manager = self.build_manager()
        manager.storage.add_unverified(self.EMAIL, self.KEY)
        del_key = manager.verify(self.EMAIL, self.KEY)
        self.assertTrue(manager.storage.is_subscribed(self.EMAIL, del_key))
        self.assertTrue(manager.sender.send.called)

    def test_verify_already_subscribed(self):
        manager = self.build_manager()
        manager.storage.add_subscriber(self.EMAIL, self.KEY)
        with self.assertRaises(ezlist.UserError) as ue:
            manager.verify(self.EMAIL, self.KEY)

    def test_verify_not_unverified(self):
        manager = self.build_manager()
        with self.assertRaises(ezlist.UserError):
            manager.verify(self.EMAIL, self.KEY)

    def test_verify_wrong_activation_key(self):
        manager = self.build_manager()
        manager.storage.add_unverified(self.EMAIL, self.KEY)
        with self.assertRaises(ezlist.UserError):
            manager.verify(self.EMAIL, 'wrong_key')

    def test_forward(self):
        manager = self.build_manager()
        manager.storage.add_subscriber(self.EMAIL, self.KEY)
        manager.storage.add_subscriber(self.EMAIL2, self.KEY2)
        mail = _build_mail(to=self.LIST_EMAIL)
        manager.forward(self.EMAIL, mail)
        self.assertEqual(2, manager.sender.send.call_count)
        # have all subscribers been notified?
        addrs = set(call[0][1] for call in manager.sender.send.call_args_list)
        self.assertEqual({self.EMAIL, self.EMAIL2}, addrs)

    def test_forward_headers(self):
        manager = self.build_manager()
        manager.storage.add_subscriber(self.EMAIL, self.KEY)
        mail = _build_mail(to=self.LIST_EMAIL)
        mail.add_header('Date', 'test')
        mail.add_header('Reply-To', self.EMAIL)
        mail.add_header('X-Custom-Header', 'test')
        manager.forward(self.EMAIL, mail)
        mail = manager.sender.send.call_args[0][2]
        self.assertTrue(self.LIST_EMAIL in mail['List-Post'])
        self.assertEqual(self.EMAIL, mail['Reply-To'])
        self.assertEqual('test', mail['Date'])
        self.assertFalse('X-Custom-Header' in mail)

    def test_forward_exclude(self):
        manager = self.build_manager()
        manager.storage.add_subscriber(self.EMAIL, self.KEY)
        manager.storage.add_subscriber(self.EMAIL2, self.KEY2)
        manager.forward(self.EMAIL, _build_mail(to=self.LIST_EMAIL),
                        exclude=[self.EMAIL])
        self.assertEqual(1, manager.sender.send.call_count)
        self.assertEqual(self.EMAIL2, manager.sender.send.call_args[0][1])

    def test_forward_list_prefix(self):
        manager = self.build_manager()
        manager.storage.add_subscriber(self.EMAIL, self.KEY)

        mail = _build_mail(to=self.LIST_EMAIL, subject='Test')
        manager.forward(self.EMAIL, mail)
        mail = manager.sender.send.call_args[0][2]
        self.assertEqual('%s Test' % self.SUBJECT_PREFIX, mail['Subject'])

        subject = 'Test %s' % self.SUBJECT_PREFIX
        mail = _build_mail(to=self.LIST_EMAIL, subject=subject)
        manager.forward(self.EMAIL, mail)
        mail = manager.sender.send.call_args[0][2]
        self.assertEqual('%s %s' % (self.SUBJECT_PREFIX, subject),
                         mail['Subject'])

        subject = 'Re: Aw: Re: %s Test Prefix after Re:' % self.SUBJECT_PREFIX
        mail = _build_mail(to=self.LIST_EMAIL, subject=subject)
        manager.forward(self.EMAIL, mail)
        mail = manager.sender.send.call_args[0][2]
        self.assertEqual(subject, mail['Subject'])

    def test_forward_not_subscribed(self):
        manager = self.build_manager()
        with self.assertRaises(ezlist.UserError):
            manager.forward(self.EMAIL, _build_mail())

    def test_process_subscribe(self):
        manager = self.build_manager()
        manager.inbox.fetch_all.return_value = (
            (1, _build_mail(to='Maillist <%s>' % self.LIST_EMAIL,
                            from_=self.EMAIL, subject='subscribe')),
            (2, _build_mail(to=self.LIST_EMAIL, from_=self.EMAIL2,
                            subject='   subscribe  ')),
        )
        manager.subscribe = mock.MagicMock()
        manager.process()
        self.assertEqual(2, manager.subscribe.call_count)
        manager.subscribe.assert_has_calls([mock.call(self.EMAIL),
                                            mock.call(self.EMAIL2)])
        manager.inbox.delete.assert_has_calls([mock.call(1), mock.call(2)])

    def test_process_unsubscribe_without_key(self):
        manager = self.build_manager()
        manager.inbox.fetch_all.return_value = (
            (1, _build_mail(to=self.LIST_EMAIL, from_=self.EMAIL,
                            subject='unsubscribe')),
            (2, _build_mail(to=self.LIST_EMAIL, from_=self.EMAIL2,
                            subject='   unsubscribe  ')),
        )
        manager.send_deletion_key = mock.MagicMock()
        manager.process()
        self.assertEqual(2, manager.send_deletion_key.call_count)
        manager.send_deletion_key.assert_has_calls([mock.call(self.EMAIL),
                                                    mock.call(self.EMAIL2)])
        manager.inbox.delete.assert_has_calls([mock.call(1), mock.call(2)])

    def test_process_verify(self):
        manager = self.build_manager()
        manager.inbox.fetch_all.return_value = (
            (1, _build_mail(to=self.LIST_EMAIL, from_=self.EMAIL,
                            subject='Re: [Foolist] verify <%s>' % self.KEY)),
        )
        manager.verify = mock.MagicMock()
        manager.process()
        self.assertEqual(1, manager.verify.call_count)
        manager.verify.assert_called_once_with(self.EMAIL, self.KEY)
        manager.inbox.delete.assert_has_calls([mock.call(1)])

    def test_process_unsubscribe(self):
        manager = self.build_manager()
        manager.inbox.fetch_all.return_value = (
            (1, _build_mail(to=self.LIST_EMAIL, from_=self.EMAIL,
                            subject='unsubscribe <%s>' % self.KEY)),
        )
        manager.unsubscribe = mock.MagicMock()
        manager.process()
        self.assertEqual(1, manager.unsubscribe.call_count)
        manager.unsubscribe.assert_called_once_with(self.EMAIL, self.KEY)
        manager.inbox.delete.assert_has_calls([mock.call(1)])

    def test_process_forward_with_skip_sender(self):
        manager = self.build_manager(skip_sender=True)
        mail = _build_mail(from_=self.EMAIL, to=self.LIST_EMAIL,
                           subject='Test something')
        manager.inbox.fetch_all.return_value = ((1, mail),)
        manager.forward = mock.MagicMock()
        manager.process()
        self.assertEqual(1, manager.forward.call_count)
        manager.forward.assert_called_once_with(self.EMAIL, mail,
                                                exclude=[self.EMAIL])
        manager.inbox.delete.assert_has_calls([mock.call(1)])

    def test_process_forward_without_skip_sender(self):
        manager = self.build_manager(skip_sender=False)
        mail = _build_mail(from_=self.EMAIL, to=self.LIST_EMAIL,
                           subject='Test something')
        manager.inbox.fetch_all.return_value = ((1, mail),)
        manager.forward = mock.MagicMock()
        manager.process()
        self.assertEqual(1, manager.forward.call_count)
        manager.forward.assert_called_once_with(self.EMAIL, mail, exclude=[])
        manager.inbox.delete.assert_has_calls([mock.call(1)])

    def test_integration(self):
        manager = self.build_manager()

        # one subscriber is already present on the list
        manager.storage.add_subscriber(self.EMAIL2, self.KEY2)

        # subscription attempt
        mail = _build_mail(from_=self.EMAIL, to=self.LIST_EMAIL,
                           subject='subscribe')
        manager.inbox.fetch_all.return_value = ((1, mail),)
        manager.process()
        self.assertTrue(manager.sender.send.called)

        # verification step (replying to the mail)
        mail = manager.sender.send.call_args[0][2]
        mail.replace_header('Subject', 'Re: %s' % mail['Subject'])
        mail.replace_header('From', self.EMAIL)
        mail.replace_header('To', self.LIST_EMAIL)
        manager.inbox.fetch_all.return_value = ((1, mail),)
        manager.process()
        self.assertEqual(2, manager.sender.send.call_count)
        self.assertTrue(manager.storage.is_subscribed(self.EMAIL))

        # send a mail to the mailing list
        subject = 'Test!'
        mail = _build_mail(from_=self.EMAIL, to=self.LIST_EMAIL,
                           subject=subject)
        manager.inbox.fetch_all.return_value = ((1, mail),)
        manager.process()
        # when skipping the sender, there is one person left to mail
        self.assertEqual(3, manager.sender.send.call_count)
        mail = manager.sender.send.call_args[0][2]
        self.assertEqual('%s %s' % (self.SUBJECT_PREFIX, subject),
                         mail['Subject'])

        # obtain deletion key
        mail = _build_mail(from_=self.EMAIL, to=self.LIST_EMAIL,
                           subject='unsubscribe')
        manager.inbox.fetch_all.return_value = ((1, mail),)
        manager.process()
        self.assertEqual(4, manager.sender.send.call_count)

        # reply to fully unsubscribe
        mail = manager.sender.send.call_args[0][2]
        mail.replace_header('Subject', 'Re: %s' % mail['Subject'])
        mail.replace_header('From', self.EMAIL)
        mail.replace_header('To', self.LIST_EMAIL)
        manager.inbox.fetch_all.return_value = ((1, mail),)
        manager.process()
        self.assertFalse(manager.storage.is_subscribed(self.EMAIL))


if __name__ == '__main__':
    unittest.main()
