# -*- coding: utf-8 -*-
"""
notifier.py A Willie module for sending notifications to people when their
nicks are mentioned.

This module maintains a Table in the Willie user settings database with the 
following columns:

pkey | nick | service | parameter

where nick is the nick to listen for, service is the service to use to notify 
the user and parameter is the place to send the notification.

Currently both pushover and email are supported notifcation types, so parameter
is the user token or email address respectively.

This module can be adminsitered by a Willie admin the following commands are 
avalible:

* list_notifications: Print out the notification table
* add_notification <nick> <service> <parameter>: Add a entry to the table
* remove_notification <nick> <service> <parameter>: Delete an entry from the table.

The following configuration settings need to be added:
[notify]
table_name = <>

The following can be added to enable the services:
pushover_app_api = <>
email_address = <>
email_server = <>
email_port = <>
email_username = <>
email_password = <>
"""

import itertools

import willie

try:
    import pushover
    PUSHOVER = True
except ImportError:
    PUSHOVER = False
    
import smtplib
from email.mime.text import MIMEText
EMAIL = True

#==============================================================================
# Module Setup
#==============================================================================
def setup(bot):
    global PUSHOVER, SMTP
    table_name = bot.config.notify.table_name
    #ToDO: Check that we have a service to notify
    if PUSHOVER:
        app_api = bot.config.notify.pushover_app_api
        if app_api and app_api is not 'none':
            pushover.init(app_api)
        else:
            PUSHOVER = False
    
    if EMAIL:
        email_address = bot.config.notify.email_address
        email_server = bot.config.notify.email_server
        email_port = bot.config.notify.email_port
        email_username = bot.config.notify.email_username
        email_password = bot.config.notify.email_password
        
        SMTP = smtplib.SMTP(email_server, email_port)
        if email_username and email_password:
            SMTP.login(email_username, email_password)
    
    columns = ['pkey', 'nick', 'service', 'parameter']
    pkey = columns[0]

    willie_db = willie.db.WillieDB(bot.config)
    connect = willie_db.connect()
    
    if not willie_db.check_table(table_name, columns, pkey):
        connect.execute("CREATE TABLE notifydb (pkey integer NOT NULL, nick string, service string, parameter string, PRIMARY KEY (pkey));")

    connect.commit()
    connect.close()

def configure(config):
    if not config.option('Configure nickname mention notification module'):
        return

    config.add_section('notify')
    config.interactive_add('notify', 'table_name', 'User database table name', default='notifydb')
    
    if config.option('Do you wish to configure Pushover notifications', True):
        config.interactive_add('notify', 'pushover_app_api', 'Pushover application token')

    if config.option('Do you wish to configure email notifications'):
        config.interactive_add('notify', 'email_address', 'Email address to send from')
        config.interactive_add('notify', 'email_server', 'SMTP server to send mail from')
        config.interactive_add('notify', 'email_port', 'SMTP server port')
        if config.option('Does your email server require authentication', True):
            config.interactive_add('notify', 'email_username', 'SMTP Username')
            config.interactive_add('notify', 'email_password', 'SMTP password')

#==============================================================================
# Notification Functions
#==============================================================================
def notify_pushover(bot, row, message):
    if pushover:
        client = pushover.Client(row[3])
        client.send_message(message)
    else:
        raise ValueError("Pushover service is not avalible")

def notify_email(bot, row, message):
    global SMTP
    
    email_address = bot.config.notify.email_address
    
    #Build Email
    msg = MIMEText(message)
    msg['Subject'] = '[{}] '.format(bot.config.core.nick) + message[:20] + '...'
    msg['From'] = email_address
    msg['To'] = row[3]
    
    #Send email
    SMTP.sendmail(email_address, [row[3]], msg.as_string())

SERVICES = {'pushover': notify_pushover,
            'email': notify_email}

#==============================================================================
# Database Functions
#==============================================================================
def get_notifydb(bot):
    willie_db = willie.db.WillieDB(bot.config)
    table_name = bot.config.notify.table_name
    return willie.db.Table(willie_db, table_name, ['pkey', 'nick', 'service', 'parameter'], 'pkey')

def get_new_pkey(notifydb):
    pkeys = [ent[0] for ent in notifydb.keys(key='pkey')]
    if not pkeys:
        return 1
    else:
        return max(pkeys)+1

def add_new_notify(connect, table_name, pkey, nick, service, parameter):
    connect.execute("INSERT INTO {} VALUES ({},'{}','{}','{}')".format(table_name, pkey, nick, service, parameter))
    connect.commit()

#==============================================================================
# Willie Commands
#==============================================================================
@willie.module.example(".add_notifcation Cadair pushover apitoken")
@willie.module.commands("add_notification")
def add_notification(bot, trigger):
    """
    Add an entry into the notification list.
    
    Specify nickname, service, and parameter
    """
    # Can only be done in privmsg by an admin
    if trigger.sender.startswith('#'):
        return
    if not trigger.admin:
        return
    notifydb = get_notifydb(bot)
    nick, service, parameter = trigger.group(2).split(' ')
    willie_db = willie.db.WillieDB(bot.config)
    add_new_notify(willie_db.connect(), bot.config.notify.table_name, get_new_pkey(notifydb), nick, service, parameter)
    bot.reply("We will now notify '{}' using '{}' with '{}'".format(nick, service, parameter))

@willie.module.example(".remove_notification Cadair pushover apitoken")
@willie.module.commands("remove_notification")
def remove_notification(bot, trigger):
    """
    Remove an entry into the notification list.
    
    Specify nickname, service, and parameter
    """
    # Can only be done in privmsg by an admin
    if trigger.sender.startswith('#'):
        return
    if not trigger.admin:
        return
        
    nick, service, parameter = trigger.group(2).split(' ')
    willie_db = willie.db.WillieDB(bot.config)
    connect = willie_db.connect()
    table_name = bot.config.notify.table_name
    cursor = connect.execute("SELECT * FROM {} WHERE nick='{}' AND service='{}' AND parameter='{}'".format(table_name, nick, service, parameter))
    for row in cursor:
        bot.reply("Removing {}".format(' | '.join(itertools.imap(str, row))))
        connect.execute("DELETE FROM {} WHERE pkey={}".format(table_name, row[0]))
    connect.commit()

@willie.module.example(".list_notifications")
@willie.module.commands("list_notifications")
def list_notifications(bot, trigger):
    """
    List all entries in the notifcation table
    """
    # Can only be done in privmsg by an admin
    if trigger.sender.startswith('#'):
        return
    if not trigger.admin:
        return
        
    willie_db = willie.db.WillieDB(bot.config)
    connect = willie_db.connect()
    table_name = bot.config.notify.table_name
    cursor = connect.execute("SELECT * FROM {}".format(table_name))
    for row in cursor:
        bot.say("{}".format(' | '.join(itertools.imap(str, row))))

#==============================================================================
# Listener and notication dispatcher
#==============================================================================
@willie.module.rule(r".*")
@willie.module.unblockable
def nick_detect(bot, message):
    table_name = bot.config.notify.table_name
    
    willie_db = willie.db.WillieDB(bot.config)
    notifydb = get_notifydb(bot)
    connect = willie_db.connect()
    
    nicks = [ent[0] for ent in notifydb.keys(key='nick')]
    for nick in nicks:
        if nick.lower() in message.lower():
            for row in connect.execute("SELECT * FROM {} WHERE nick='{}'".format(table_name, nick)):
                
                func = SERVICES.get(row[2], None)
                if func:
                    func(bot, row, message)
                