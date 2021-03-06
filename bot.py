# -*- coding: utf-8 -*-
###
# AUTHORS: CHRISTIAN GIBSON,
# PROJECT: /r/MechMarket Bot
# UPDATED: SEPTEMBER 11, 2015
# USAGE:   python bot.py [-h / --help] [-is / --interactive-shell]
# EXPECTS: python 3.4.0
#          beautifulsoup4 4.4.0
#          praw 3.2.1
#          regex 2015.06.24
###

import argparse
import bs4
import cmd
import collections
import configparser
import copy
import errno
import inspect
import logging
import math
import multiprocessing
import os
import platform
import praw
import random
import regex
import shelve
import shutil
import threading
import time
import traceback
import urllib
import uuid


__AUTHORS__ = ['/u/NotMelNoGuitars']
__VERSION__ = 0.1
__CMD_STR__ = '>>> '
__INFO__ = 'MechKB0t-v%s on "%s" with << %s v%s >> at %s %s' % (
    __VERSION__,
    platform.platform(),
    platform.python_implementation(),
    platform.python_version(),
    time.ctime(),
    time.localtime().tm_zone)


def coerce_reddit_handles(handles=__AUTHORS__):
    clean = regex.compile(r'[^A-Z0-9_/-]', regex.UNICODE + regex.IGNORECASE)
    authors = []
    for author in handles:
        author = clean.sub('', str(author))
        if ((author.startswith('/u/') or author.startswith('/r/'))
                and len(author.split('/')) == 3):
            authors.append(author)
        else:
            authors.append('/u/' + max(author.split('/'), key=len))
    return authors


class config_generator():
    # c = bot.config_generator()(bot.bot.CONFIG_DEFAULTS)() ; print(c.func_code)
    _FUNC_CODE_ = """class config_handler(configparser.RawConfigParser):

    def __init__(self, conf_file=None):
        super(self.__class__, self).__init__()

        self.true_values = frozenset(['true', 't', '1', 'y', 'yes', 'aye', 'on',
                                      'use', 'active', 'activate'])
        self.heatware_regex = None

        if conf_file:
            self.conf_file = os.path.abspath(conf_file)
        else:
            try:
                self.conf_file = (os.path.dirname(os.path.abspath(
                    inspect.getsourcefile(lambda: None))) + os.sep + 'config.cfg')
            except:
                self.conf_file = None

        if self.conf_file:
            try:
                self.read(self.conf_file)
                if not self.sections():
                    self.generate_defaults()
                    self.status = errno.ENOENT
                else:
                    self.status = 0
            except:
                traceback.print_exc()
                self.status = errno.EIO
        else:
            self.status = errno.EBADF
    
    def store(self):
        with open(self.conf_file, 'w') as conf_handle:
            self.write(conf_handle)

    def protected_pull(self, section, option, cast=None, default=None):
        if self.status:
            raise EnvironmentError(self.status,
                                   ('Current status #%d <%s> "%s".' %
                                    (self.status,
                                     errno.errorcode[self.status],
                                     os.strerror(self.status))),
                                   self.conf_file)
        try:
            if cast:
                return cast(self.get(section, option))
            else:
                return self.get(section, option)
        except:
            if default:
                return default
            else:
                raise

    def protected_pullboolean(self, section, option):
        boolean = self.protected_pull(section, option).lower()
        if boolean in self.true_values:
            return True
        return False

    def protected_push(self, section, option, value):
        if self.status:
            raise EnvironmentError(self.status,
                                   ('Current status #%d <%s> "%s".' %
                                    (self.status,
                                     errno.errorcode[self.status],
                                     os.strerror(self.status))),
                                   self.conf_file)
        try:
            self.set(section, option, value)
            self.store()
            return True
        except:
            return False

    def protected_pushboolean(self, section, option, value):
        if value is True or value in self.true_values:
            return self.protected_push(section, option, 'true')
        return self.protected_push(section, option, 'false')

"""

    def __init__(self):
        pass

    def __call__(self, sections, ignore_description=False):
        if all(all('desc' in detail for _, detail in options.items())
               for _, options in sections.items()) or ignore_description:
            pass
        else:
            raise TypeError('Provided configuration does not provide a "desc" '
                            'field for each section option. As such, the %s '
                            'cannot create an interactive_initialization() '
                            'method. To create the constructor without the '
                            'interactive_initialization() method, set '
                            '"ignore_description" to True when calling %s.'
                            % (self.__class__, self.__class__))

        added_methods = {attr_or_func: None
                         for attr_or_func in dir(configparser.RawConfigParser)}
        added_methods['conf_file'] = None
        added_methods['func_code'] = None
        added_methods['heatware_regex'] = None
        added_methods['protected_pull'] = None
        added_methods['protected_pullboolean'] = None
        added_methods['protected_push'] = None
        added_methods['protected_pushboolean'] = None
        added_methods['status'] = None
        added_methods['store'] = None
        added_methods['true_values'] = None
        if ignore_description:
            added_methods['generate_defaults'] = None
        else:
            added_methods['generate_defaults'] = None
            added_methods['interactive_initialization'] = None
            init_initials = ["    def interactive_initialization(self):",
                             "        to_initialize = ["]
        init_defaults = ["    def generate_defaults(self):"]

        for section, options in sections.items():
            init_defaults.append("        self.add_section('%s')" % section)
            for option, detail in options.items():
                if 'boolean' in detail:
                    pulltype = 'protected_pullboolean'
                    pushtype = 'protected_pushboolean'
                else:
                    pulltype = 'protected_pull'
                    pushtype = 'protected_push'

                if 'get' in detail:
                    if detail['get']:
                        get_method = detail['get']
                    else:
                        get_method = None
                else:
                    get_method = 'get_%s_%s' % (section, option)
                if get_method in added_methods:
                    raise SyntaxError('Attempted to add get method %s to new '
                                      'config_handler object, but it was '
                                      'already defined.' % get_method)
                if get_method:
                    added_methods[get_method] = (
                        "    def %s(self):\n"
                        "        return self.%s('%s', '%s')\n"
                        % (get_method, pulltype, section, option))

                if 'set' in detail:
                    if detail['set']:
                        set_method = detail['set']
                    else:
                        set_method = None
                else:
                    set_method = 'set_%s_%s' % (section, option)
                if set_method in added_methods:
                    raise SyntaxError('Attempted to add set method %s to new '
                                      'config_handler object, but it was '
                                      'already defined.' % set_method)
                if set_method:
                    added_methods[set_method] = (
                        "    def %s(self, value):\n"
                        "        return self.%s('%s', '%s', value)\n"
                        % (set_method, pushtype, section, option))

                if 'def' in detail:
                    init_defaults.append(
                        "        self.set('%s', '%s', '%s')" %
                        (section, option, detail['def']))
                else:
                    init_defaults.append(
                        "        self.set('%s', '%s', '%s')" %
                        (section, option, ""))

                if not ignore_description:
                    if 'def' in detail:
                        init_initials.append(
                            "            ('%s', '%s', '%s', '%s', '%s')," %
                            (self.sanify(detail['desc']),
                             self.sanify(detail['def']),
                             pushtype, section, option))
                    else:
                        init_initials.append(
                            "            ('%s', None, '%s', '%s', '%s')," %
                            (self.sanify(detail['desc']),
                             pushtype, section, option))

        added_methods['generate_defaults'] = ('\n'.join(init_defaults) + '\n' +
                                              '        self.store()\n')
        if not ignore_description:
            init_initials.extend([
                "        ]",
                "",
                "        for desc, def_, fxn, sec, opt in to_initialize:",
                "            value_set = False",
                "            while not value_set:",
                "                try:",
                "                    print('Now setting [%s].[%s]:' % (sec, opt))",
                "                    print('Description: %s' % desc)",
                "                    if def_:",
                "                        print('Leave blank to use default '",
                "                              'value \"%s\".' % def_)",
                "                    val = input('Set [%s].[%s]: ' % (sec, opt))",
                "                    if val:",
                "                        getattr(self, fxn)(sec, opt, val)",
                "                        value_set = True",
                "                    elif def_:",
                "                        getattr(self, fxn)(sec, opt, def_)",
                "                        value_set = True",
                "                    else:",
                "                        print('(!!!) Invalid value provided, '",
                "                              'or no value provided with no '",
                "                              'default available.\\n')",
                "                    if value_set:",
                "                        rec = self.get(sec, opt)",
                "                        print('Value set as \"%s\".' % rec,",
                "                              end=' ')",
                "                        chk = input('Is that correct? (y/n) ')",
                "                        if chk.lower().strip().startswith('y'):",
                "                            print('Input accepted and stored.'",
                "                                  '\\f\\n\\r')",
                "                        else:",
                "                            print('Interpreted response as '",
                "                                  '\"no\". Will recapture '",
                "                                  'input.\\n')",
                "                            value_set = False",
                "                except KeyboardInterrupt:",
                "                    raise",
                "                except:",
                "                    print('(!!!) Error encountered when '",
                "                          'attempting to set value.\\n')",
                "        self.store()"
            ])
            added_methods['interactive_initialization'] = (
                '\n'.join(init_initials) + '\n')
        _func_code_ = (self._FUNC_CODE_ +
                       '\n'.join(filter(lambda x: isinstance(x, str),
                                        added_methods.values())))
        exec(compile(_func_code_, '<string>', 'exec'))
        config = eval('config_handler')
        config.func_code = _func_code_
        return config

    def sanify(self, text):
        return text.encode('unicode-escape').decode().replace("'", "\\'")

_BS4_PARSER = 'html.parser'
_GET_CONFIG = config_generator()
logger = logging.getLogger()
logger.setLevel(logging.INFO)


class bot_prompt(cmd.Cmd):
    # errno.ENOTTY

    def __init__(self):
        super(self.__class__, self).__init__()
        self.prompt = __CMD_STR__
        self.size = shutil.get_terminal_size()
        self.height, self.width = self.size.lines, self.size.columns


class bot(praw.Reddit, threading.Thread):

    CONFIG_DEFAULTS = collections.OrderedDict([
        ('crawl', collections.OrderedDict([
            ('file', {'def': 'data.record',
                      'desc': ('This is the name of the flatfile that will be '
                               'used to store all collected data on a user-by-'
                               'user basis.')}),
            ('hold', {'def': '10',
                      'desc': ('This is the number of seconds the bot will '
                               'spend in each state as a minimum.\nAs an '
                               'example, the bot has three states by default:\n'
                               ' 1. Crawl /new of the target subreddit.\n'
                               ' 2. Respond to user PMs.\n'
                               ' 3. Crawl the trade thread of the target '
                               'subreddit.')}),
            ('sleep', {'def': '100',
                       'desc': ('This is the number of seconds the bot will '
                                'spend doing nothing after completing each set '
                                'of states.')})
        ])),
        ('reddit', collections.OrderedDict([
            ('user_agent', {'def': ('%s-%s:%s:MechKB0t-v%s (by %s)' %
                                    (platform.system(), platform.processor(),
                                     uuid.uuid5(uuid.NAMESPACE_OID, __INFO__),
                                     __VERSION__,
                                     ', '.join(coerce_reddit_handles()))),
                            'desc': ('This is the plaintext string that will '
                                     'be used by the admins at reddit to '
                                     'identify this bot. It is recommended '
                                     'that bots follow the format:\n'
                                     '  <platform>:<app ID>:<version string> '
                                     '(by /u/<reddit username>)\n'
                                     'Full rules and restrictions can be '
                                     'found here: http://github.com/reddit/'
                                     'reddit/wiki/API.')}),
            ('client_id', {'desc': ('This is the OAuth2 client_id created '
                                    'for your reddit app instance. More '
                                    'information can be found here: http://'
                                    'github.com/reddit/reddit/wiki/OAuth2.')}),
            ('client_secret', {'desc': ('This is the OAuth2 client_secret '
                                        'created for your reddit app instance. '
                                        'More information can be found here: '
                                        'http://github.com/reddit/reddit/wiki'
                                        '/OAuth2.')}),
            ('redirect_url', {'desc': ('This is the OAuth2 redirect_url created '
                                       'for your reddit app instance. More '
                                       'information can be found here: http://'
                                       'github.com/reddit/reddit/wiki/OAuth2.')}),
            ('subreddit', {'desc': 'The subreddit targeted by this bot.'}),
            ('multiprocess', {'def': 'false',
                              'get': 'is_multiprocessed',
                              'set': None,
                              'desc': 'Currently not implemented. Ignore.',
                              'boolean': True}),
            ('verbose', {'def': 'true',
                         'get': 'is_verbose',
                         'set': 'set_verbose',
                         'desc': ('Sets whether the bot will display its '
                                  'actions during runtime, or simply log them.'),
                         'boolean': True})
        ])),
        ('monitor', collections.OrderedDict([
            ('log', {'def': 'event.log',
                     'desc': ('This is the flatfile that will be used to log '
                              'all actions taken by the bot.')}),
            ('posts', {'def': 'true',
                       'desc': ('Whether or not the bot will log basic '
                                'information concerning all posts observed '
                                'during its runtime.'),
                       'boolean': True}),
            ('users', {'def': 'true',
                       'desc': ('Whether or not the bot will record basic '
                                'infromation concerning all users observed '
                                'during its runtime.'),
                       'boolean': True}),
            ('format', {'def': '%(created)f -- %(levelname)s -> %(message)s',
                        'desc': ('This is the format string that will be used '
                                 'in creating each entry in the log file. '
                                 'Formatting options include:\n'
                                 ' %(asctime)s: Human-readable time when a '
                                 'logged event was created.\n'
                                 ' %(created)f: Seconds since epoch when a '
                                 'logged event was created.\n'
                                 ' %(filename)s: Source file that created a '
                                 'logged event.\n'
                                 ' %(funcName)s: Function used that created a '
                                 'logged event.\n'
                                 ' %(levelname)s: Severity of logged event as '
                                 'an English string.\n'
                                 ' %(levelno)s: Severity of logged event as a '
                                 'numeric value.\n'
                                 ' %(lineno)d: Line number of the source file '
                                 'where a logged event was created.\n'
                                 ' %(module)s: Module that created a logged '
                                 'event.\n'
                                 ' %(msecs)d: Millisecond portion of system '
                                 'time when an event was logged.\n'
                                 ' %(message)s: Message provided when an event '
                                 'was logged.\n'
                                 ' %(name)s: Name of the logger used to create '
                                 'the logged event.\n'
                                 ' %(pathname)s: Full pathname of the source '
                                 'file that created the logged event.\n'
                                 ' %(process)d: Process ID that created the '
                                 'logged event.\n'
                                 ' %(processName)s: Process name that created '
                                 'the logged event.\n'
                                 ' %(relativeCreated)d: Milliseconds after the '
                                 'logging module was initially loaded that an '
                                 'event was logged.\n'
                                 ' %(thread)d: Thread ID that created the '
                                 'logged event.\n'
                                 ' %(threadName)s: Thread name that created '
                                 'the logged event.\n'
                                 'Further information can be found at: '
                                 'http://docs.python.org/3.4/library/logging.'
                                 'html#logging.LogRecord')},
             ('respond', {'def': 'true',
                          'desc': ('Whether or not the bot should make a post '
                                   'on each new trade thread.'),
                          'boolean': True}),
             ('response', {'desc': ('The text template used when commenting on '
                                    'a new trade thread. Formatting options '
                                    'include:\n')})),
        ])),
        ('sidebar', collections.OrderedDict([
            ('add_button', {'def': 'false',
                            'get': 'should_add_button',
                            'desc': ('Whether the bot should add a button for '
                                     'the current trade thread on the target '
                                     'subreddit\'s sidebar.'),
                            'boolean': True}),
            ('button_text', {'desc': 'The text used for the created button.'}),
            ('button_start', {'desc': ('A specialized tag, included in the '
                                       'sidebar\'s text, which determines '
                                       'where the button starts.')}),
            ('button_end', {'desc': ('A specialized tag, included in the '
                                     'sidebar\'s text, which determines where '
                                     'the button ends.')})
        ])),
        ('class', collections.OrderedDict([
            ('use', {'def': 'true',
                     'desc': 'If the bot should monitor and update user flair.',
                     'boolean': True}),
            ('start', {'desc': 'Flair given to users never seen before.'}),
            ('limit', {'desc': ('Maximum integer indicating how many times '
                                'a user\'s flair can be incremented.')}),
            ('ignore', {'desc': ('A whitespace-separated list of flairs which '
                                 'should be ignored if encountered by the bot.')}),
            ('pattern', {'desc': ('The pattern used to generate new user '
                                  'flair following an increment. %i is used '
                                  'to indicate where the integer value of the '
                                  'flair should go. As a example, a flair '
                                  'pattern of "u-%i" would take on the values '
                                  '"u-1" for a user with a flair value of 1, '
                                  '"u-2" for a user with a flair value of 2, '
                                  '"u-3" for a user with a flair value of 3, '
                                  'etc.')}),
            ('increment', {'def': '1',
                           'desc': ('The integer value that a user\'s flair '
                                    'value will be incremented by with each '
                                    'flair increment. Given a default value '
                                    'of "1", a user with a flair value of 3 '
                                    'would advance to a flair value of 4 after '
                                    'completing a trade.')})
        ])),
        ('trade', collections.OrderedDict([
            ('method', {'def': 'post',
                        'desc': ('The method used by the bot to confirm user '
                                 'trades. Three options are available, "pm", '
                                 '"post", or "both". If "pm" is specified, '
                                 'trades will be confirmed via private '
                                 'message; with the sender in a trade sending '
                                 'a private message to the bot containing the '
                                 'reddit handle of the recipient. The bot then '
                                 'contacts the other party, who confirms the '
                                 'trade. If "post" is specified, a public '
                                 'thread is used. Within the thread, the '
                                 'sender creates a top-level comment, which '
                                 'the recipient replies to with a comment '
                                 'containing the phrase "confirmed". In the '
                                 'case that "both" is specified, either option '
                                 'can be used to confirm a trade.')}),
            ('post_id', {'desc': ('The id used by the trading thread within '
                                  'the target subreddit. If left blank, the '
                                  'bot will create its own trading thread. In '
                                  'the case that "pm" is used as a method, '
                                  'this value is ignored.')}),
            ('post_text', {'desc': ('The text template used when creating a '
                                    'new trade thread. Supports formatting '
                                    'arguments as found in Python\'s strftime '
                                    'command. For more information, see: '
                                    'https://docs.python.org/2/library/time.html'
                                    '#time.strftime.')}),
            ('post_rate', {'def': 'monthly',
                           'desc': ('The rate at which the bot will create '
                                    'new trading posts on the target subreddit.'
                                    ' Provided options include "daily", '
                                    '"weekly", "monthly", "yearly", and "never"'
                                    '. If "never" is selected, the post_id will'
                                    ' have to be updated manually by the user.')}),
            ('post_title', {'desc': ('The title template used when creating a '
                                     'new trade thread\'s title. Supports '
                                     'formatting arguments as found in Python\'s'
                                     'strftime command. For more information, '
                                     'see: https://docs.python.org/2/library/'
                                     'time.html#time.strftime.')}),
            ('post_sticky', {'def': 'false',
                             'desc': ('If the bot makes the trade thread sticky'
                                      ' or not.')}),
            ('post_response', {'desc': ('The text template used when replying '
                                        'to a confirmed trade comment on a '
                                        'trade post. Supports formatting '
                                        'arguments as found in Python\'s '
                                        'strftime command. For more information'
                                        ', see: https://docs.python.org/2/'
                                        'library/time.html#time.strftime.')}),
            ('message_text', {'desc': ('The text template used when sending a '
                                       'private message to both users following'
                                       ' a confirmed trade. Supports formatting'
                                       ' arguments as found in Python\'s '
                                       'strftime command. For more information,'
                                       ' see: https://docs.python.org/2/library'
                                       '/time.html#time.strftime.')}),
            ('message_title', {'desc': ('The title template used when sending a '
                                        'private message to both users '
                                        'following a confirmed trade. Supports '
                                        'formatting arguments as found in '
                                        'Python\'s strftime command. For more '
                                        'information, see: https://docs.python.'
                                        'org/2/library/time.html#time.strftime.')}),
            ('respond', {'def': 'true',
                         'desc': ('If the bot should respond following a '
                                  'confirmed trade or not.'),
                         'boolean': True}),
            ('age_msg', {'desc': ('Message used to reply when a user attempts '
                                  'to confirm a trade when their account is '
                                  'younger than the provided age limit.')}),
            ('age_type', {'def': 'days',
                          'desc': ('Units used in determining if a user\'s '
                                   'account is too young to confirm a trade. '
                                   'Options are "seconds", "minutes", "hours", '
                                   '"days", "months".')}),
            ('age_limit', {'def': '30',
                           'desc': ('Numerical measurement used in determining '
                                    'if a user\'s account is too young to '
                                    'confirm a trade.')}),
            ('same_msg', {'desc': ('Message used to reply when a user attempts '
                                   'to confirm a trade with themselves.')}),
            ('karma_msg', {'desc': ('Message used to reply when a user attempts'
                                    ' to confirm a trade when their account\'s '
                                    'karma is below the provided karma limit.')}),
            ('karma_type', {'def': 'both',
                            'desc': ('Units used in determining if a user\'s '
                                     'account has sufficient karma to confirm '
                                     'a trade. Options are "comment", "link", '
                                     'or "both".')}),
            ('karma_limit', {'def': '100',
                             'desc': ('Numerical measurement used in '
                                      'determining if a user\'s account has '
                                      'sufficient karma to confirm a trade.')})
        ])),
        ('heatware', collections.OrderedDict([
            ('method', {'def': 'pm',
                        'desc': ('The method by which the bot will collect a '
                                 'user\'s heatware URL. Three options are '
                                 'available, "pm", "post", and "both". If "pm" '
                                 'is specified, users can submit heatware URLs '
                                 'by means of private message to the bot. If '
                                 '"post" is specified, users can submit their '
                                 'heatware URLs by means of commenting in a '
                                 'specified post. If "both" is specified, '
                                 'either method can be used.')}),
            ('post_id', {'desc': ('The id used by the heatware thread in the '
                                  'target subreddit.')}),
            ('post_text', {'desc': ('The text template used when creating a '
                                    'new heatware thread. Supports formatting '
                                    'arguments as found in Python\'s strftime '
                                    'command. For more information, see: '
                                    'https://docs.python.org/2/library/time.html'
                                    '#time.strftime.')}),
            ('post_rate', {'def': 'yearly',
                           'desc': ('The rate at which the bot will create '
                                    'new heatware posts on the target subreddit.'
                                    ' Provided options include "daily", '
                                    '"weekly", "monthly", "yearly", and "never"'
                                    '. If "never" is selected, the post_id will'
                                    ' have to be updated manually by the user.')}),
            ('post_title', {'desc': ('The title template used when creating a '
                                     'new heatware thread\'s title. Supports '
                                     'formatting arguments as found in Python\'s'
                                     'strftime command. For more information, '
                                     'see: https://docs.python.org/2/library/'
                                     'time.html#time.strftime.')}),
            ('post_sticky', {'desc': ('If the bot makes the heatware thread '
                                      'sticky or not.')}),
            ('post_response', {'desc': ('The text template used when replying '
                                        'to an accepted heatware comment on a '
                                        'heatware post. Supports formatting '
                                        'arguments as found in Python\'s '
                                        'strftime command. For more information'
                                        ', see: https://docs.python.org/2/'
                                        'library/time.html#time.strftime.')}),
            ('message_text', {'desc': ('The text template used when sending a '
                                       'private message to a user following'
                                       ' an accepted heatware profile. Supports '
                                       'formatting arguments as found in Python\'s'
                                       ' strftime command. For more information,'
                                       ' see: https://docs.python.org/2/library'
                                       '/time.html#time.strftime.')}),
            ('message_title', {'desc': ('The title template used when sending a '
                                        'private message to a user following '
                                        'an accepted heatware profile. Supports '
                                        'formatting arguments as found in '
                                        'Python\'s strftime command. For more '
                                        'information, see: https://docs.python.'
                                        'org/2/library/time.html#time.strftime.')}),
            ('regex', {'def': '(?:.*)(http(?:s?)://www\.heatware\.com/eval\.php\?id=[0-9]+)(?:.*)',
                       'set': None,
                       'desc': ('The regular expression used to _extract '
                                'heatware URLs from plaintext comments.')}),
            ('group', {'def': '1',
                       'set': None,
                       'desc': ('The group within the regular expression that '
                                'actually contained the captured heatware URL. '
                                'If left blank, the parser will accept the '
                                'entire match resulting from the regular '
                                'expression.')}),
            ('respond', {'def': 'true',
                         'desc': ('If a bot should respond to an accepted '
                                  'heatware profile URL or not.'),
                         'boolean': True})
        ]))
    ])

    def __init__(self, conf_file='config.cfg'):
        config_constructor = _GET_CONFIG(self.CONFIG_DEFAULTS)
        self.config_handler = config_constructor(conf_file)
        if self.config_handler.status:
            raise EnvironmentError(self.config_handler.status,
                                   ('Current status #%d <%s> "%s".' %
                                    (self.config_handler.status,
                                     errno.errorcode[
                                         self.config_handler.status],
                                     os.strerror(self.config_handler.status))),
                                   conf_file)
        log = logging.StreamHandler(self.config_handler.get_monitor_log())
        fmt = logging.Formatter(self.config_handler.get_monitor_format())
        log.setLevel(logging.DEBUG)
        log.setFormatter(fmt)
        logger.addHandler(log)
        self.data_store = database_handler(
            self.config_handler.get_crawl_file())
        self.heat_parse = heatware_crawler()
        self.run_states = {
            state[6:].lstrip('_'): getattr(self, state)
            for state in set(dir(self)).difference(dir(super()))
            if (state.startswith('_state')
                and hasattr(getattr(self, state), '__call__'))}
        super().__init__(self.config_handler.get_reddit_user_agent())
        self.set_oauth_app_info(self.config_handler.get_reddit_client_id(),
                                self.config_handler.get_reddit_client_secret(),
                                self.config_handler.get_reddit_redirect_url())
        threading.Thread.__init__(self, daemon=True)

    def run(self):
        while True:
            state_time = {state: max(1, self.config_handler.get_crawl_hold())
                          for state in self.run_states}
            while any(t > 0 for t in state_time.values()):
                for state, function in self.run_states.items():
                    if state_time[state] > 0:
                        self.state = state
                        state_start = time.time()
                        try:
                            function()
                        except:
                            pass
                        state_elaps = time.time() - state_start
                        if state_elaps > 0:
                            state_time[state] -= state_elaps
                        else:
                            state_time[state] = 0
            time.sleep(self.config_handler.get_crawl_sleep())
        self.shutdown()

    def _state_trade(self):
        """
        Performs processing necessary for the verification and updating
          of user's css class following a successful trade.

        Will need to call the following methods from self.config_handler:
          get_trade_method()
          if get_trade_method() in ['post', 'both']:
            get_trade_post_id()
            get_trade_post_text()
            get_trade_post_rate()
            get_trade_post_title()
            get_trade_post_sticky()
            get_trade_post_response()
            should_add_button()
            get_sidebar_button_text()
            get_sidebar_button_start()
            get_sidebar_button_end()
          if get_trade_method() in ['pm', 'both']:
            get_trade_message_text()
            get_trade_message_title()
          get_trade_respond()
          get_trade_age_msg()
          get_trade_age_type() -> ['seconds', 'minutes', 'hours', 'days', 'months']
          get_trade_same_msg()
          get_trade_karma_msg()
          get_trade_karma_type() -> ['comment', 'link', 'both']
          get_trade_karma_limit()

          get_class_use()
          get_class_start()
          get_class_limit()
          get_class_ignore()
          get_class_pattern()
          get_class_increment()

        In addition, will need to log results to logger, and store updated
          user information in self.data_store if get_monitor_users() is True.
        """
        if self.config_handler.get_trade_method() in ['pm', 'both']:
            pass
        if self.config_handler.get_trade_method() in ['post', 'both']:
            pass

    def _state_posts(self):
        """
        Monitors and replies to previously unseen posts on the target
          subreddit's /new page.

        Will need to call the following methods from self.config_handler:
          get_monitor_posts()
          get_monitor_users()
          get_monitor_format()
          get_monitor_respond()
          get_monitor_response()
        """
        pass

    def _state_flair(self):
        """
        Responsible for verifying and setting user flair with regards to their
          accounts on http://www.HeatWare.com.

        Will need to call the following methods from self.config_handler:
          get_heatware_method()
          if get_heatware_method() in ['post', 'both']:
            get_heatware_post_id()
            get_heatware_post_text()
            get_heatware_post_rate()
            get_heatware_post_title()
            get_heatware_post_sticky()
            get_heatware_post_response()
          if get_heatware_method() in ['pm', 'both']:
            get_heatware_message_text()
            get_heatware_message_title()
          get_heatware_regex()
          get_heatware_group()
          get_heatware_respond()

        Recall:
          >>> import time, pprint
          >>> self.heat_parse.parse('2')
          >>> while len(self.heat_parse) < 1: time.sleep(1)
          >>> results = {id_: info for id_, info in self.heat_parse}
          >>> pprint.pprint(results['2'])
          {'aliases': {'amdmb': {'heat23': None},
                       'anandtech bbs': {'heat23': 'http://forum.anandtech.com'},
                       'arstechnica': {'heat23': None},
                       'geekhack': {'heatware': None},
                       'techpowerup!': {'heatware': None},
                       'webhostingtalk': {'heat23': None}},
           'evaluations': {334221: {'comments': 'Great transaction, he sent money '
                                                'via paypal and I shipped upon '
                                                'payment.',
                                    'date': '06-30-2005',
                                    'forum': 'anandtech bbs',
                                    'user': 'floben'},
                           344973: {'comments': 'What can I say about the owner of '
                                                'heatware besides the fact that it '
                                                'was an awesome transaction. I had '
                                                'no worries about shipping first, '
                                                'and his great communication '
                                                'throughout the transaction put me '
                                                'at ease.',
                                    'date': '08-17-2005',
                                    'forum': 'anandtech bbs',
                                    'user': 'jackson18249'},
                           345198: {'comments': 'Quick payment & good communication. '
                                                'You cannot ask for a smoother '
                                                'transaction!',
                                    'date': '08-23-2005',
                                    'forum': 'anandtech bbs',
                                    'user': 'hkklife'},
                           356225: {'comments': 'Super-fast payment, prompt response '
                                                'to PMs. There was a delivery delay '
                                                '(because of Katrina) but buyer was '
                                                'very patient and kept in touch. '
                                                'Thanks!',
                                    'date': '09-27-2005',
                                    'forum': 'anandtech bbs',
                                    'user': 'fornax'},
                           423266: {'comments': 'This was simply one of the best '
                                                'transactions I have experienced on '
                                                'Anandtech. I sent Heat23 a paypal '
                                                'e-check (expecting for funds to '
                                                'clear first) but he crosshipped '
                                                'minutes later on a Saturday. Got '
                                                'the package Monday morning in the '
                                                'office. Awesome.',
                                    'date': '08-14-2006',
                                    'forum': 'anandtech bbs',
                                    'user': 'jloor'},
                           425040: {'comments': 'Fast payment, smooth transaction... '
                                                'Good guy to deal with! Thanks!',
                                    'date': '08-23-2006',
                                    'forum': 'anandtech bbs',
                                    'user': 'Doctor Feelgood'},
                           425650: {'comments': 'Heat23 threw in a couple of '
                                                'freebies and shipped everything out '
                                                'lightspeed. Thanks Man!',
                                    'date': '08-26-2006',
                                    'forum': 'anandtech bbs',
                                    'user': 'ScottyWH'},
                           425699: {'comments': 'This was a very smooth transaction. '
                                                'Heat sent me payment and I sent him '
                                                'the camera. I would gladly sell to '
                                                'him again. Thanks!',
                                    'date': '08-20-2006',
                                    'forum': 'anandtech bbs',
                                    'user': 'dak125'},
                           426236: {'comments': 'The transaction went great, seller '
                                                'was the easy to deal with and the '
                                                'shipping was fast. (Freebie '
                                                'included)...Love to deal again in '
                                                'the future...',
                                    'date': '08-29-2006',
                                    'forum': 'anandtech bbs',
                                    'user': 'mackle'},
                           487916: {'comments': 'Good communication, paid via '
                                                "Paypal, smooth deal. If you can\\'t "
                                                'trust heat23, who can you trust?;)',
                                    'date': '08-23-2007',
                                    'forum': 'anandtech bbs',
                                    'user': 'Tates'},
                           496656: {'comments': 'Nice guy to work with. His '
                                                'contribution to the trading '
                                                'community is definitely '
                                                'appreicated!!! Thanks again heat. :)',
                                    'date': '11-08-2007',
                                    'forum': 'anandtech bbs',
                                    'user': 'ELopes580'},
                           527657: {'comments': 'Though took a bit to get the deal '
                                                'done, he was courteous, kept in '
                                                'touch, and made the whole '
                                                'experience awesome! Thanks for the '
                                                "phone, it\\'s awesome!",
                                    'date': '08-04-2008',
                                    'forum': 'anandtech bbs',
                                    'user': 'proxops-pete'},
                           621980: {'comments': 'Donation acknowledgement and thanks '
                                                'received. Thanks for spending your '
                                                'time building something to do good.',
                                    'date': '07-11-2011',
                                    'forum': 'heatware',
                                    'user': 'AmboBartok'},
                           690634: {'comments': 'Got payment quickly, great '
                                                'comunication. Would deal with again '
                                                'anytime. A++++',
                                    'date': '07-23-2014',
                                    'forum': 'anandtech bbs',
                                    'user': 'Sniper82'},
                           699942: {'comments': 'Receiver was packed very well, in '
                                                'what appeared to be the original '
                                                'box. This receiver was shipped from '
                                                'CA to NY and was in beautiful '
                                                'condition when it arrived. Heat23 '
                                                'even included a couple HDMI cables. '
                                                'The item was as described, shipped '
                                                'promptly, packed very well, and is '
                                                'working well as I type this. This '
                                                'transaction could not have gone '
                                                "better, and I\\'d definitely deal "
                                                'with Heat23 again.',
                                    'date': '03-03-2015',
                                    'forum': 'anandtech bbs',
                                    'user': 'NicePants42'}},
           'location': 'Austin, TX',
           'rating': {'negative': 0, 'neutral': 0, 'positive': 188}}
        """
        if self.config_handler.get_heatware_method() in ['pm', 'both']:
            pass
        if self.config_handler.get_heatware_method() in ['post', 'both']:
            pass

    def shutdown(self):
        self.heat_parse.kill()

    def __repr__(self):
        # This section is a carbon copy of the vanilla codebase.
        # ( See:  threading.Thread.__repr__ )
        thread_status = 'initial'
        if self._started.is_set():
            thread_status = 'started'
        self.is_alive()
        if self._is_stopped:
            thread_status = 'stopped'
        if self._daemonic:
            thread_status += ' daemon'
        if self._ident is not None:
            thread_status += ' %s' % self._ident

        reddit_status = 'logged'
        if self.is_logged_in():
            reddit_status += '-in'
        else:
            reddit_status += '-out'
        if self.is_oauth_session():
            reddit_status += ' oauth2'
        return "<%s.%s {'thread': (%s, %s), 'reddit': (%s, %s)} at %s>" % (
            self.__class__.__module__, self.__class__.__name__,
            self.name, thread_status, self.user, reddit_status, hex(id(self)))


class database_handler(shelve.DbfilenameShelf):

    def __init__(self, data_file):
        super(self.__class__, self).__init__(filename=data_file)

    def get(self, key):
        try:
            return self[key.lower()]
        except:
            return {}

    def set(self, key, val):
        try:
            assert(isinstance(val, dict))
            cur = self.get(key.lower())
            val = self.update(val, cur)
            self[key.lower()] = val
            return True
        except:
            return False

    def remove(self, key):
        try:
            del self[key.lower()]
            return True
        except:
            return False

    def update(self, new_, orig):
        for key, val in orig.items():
            if isinstance(val, dict):
                new_[key] = self.update(new_.get(key, {}), val)
            else:
                new_[key] = orig[key]
        return new_

    def terminate(self):
        self.sync()
        self.close()


class heatware_crawler(multiprocessing.Process):

    def __init__(self, page_wait=0, deep_parse=False, rand_wait=False):
        # TODO: See if heat is okay with maximum one request per sixty seconds.
        # STATUS: Reached out to heat as of Aug 29; no response as of yet.
        #         The site's robots.txt (http://heatware.com/robots.txt) seems
        #           to allow any sort of automated crawling, but I won't
        #           implement the ability to perform a 'deep_parse' until I
        #           get confirmation from the man himself.
        self._state = multiprocessing.Value('c', 0)
        self.page_wait = max(60, page_wait)
        self.sqrt_wait = math.sqrt(self.page_wait)
        # TODO: See if heat is okay with deep crawling of his site.
        self.deep_parse = False  # deep_parse
        if rand_wait:
            self.rand_wait = lambda: random.uniform(self.sqrt_wait / 2.0,
                                                    self.sqrt_wait * 2.0)
        else:
            self.rand_wait = lambda: 0
        self.next_time = time.time()
        self.get_next_time = lambda: (
            time.time() + self.page_wait + self.rand_wait())
        self.get_page = urllib.request.urlopen
        self.root_page = 'http://www.heatware.com/eval.php?id='
        self.page_ext = '&pagenum=%i'
        self.eval_ext = '&num_days=%i'
        self.info_dict = {
            # 'deep_parse': self.deep_parse,
            'rating': {'positive': 0,
                       'neutral': 0,
                       'negative': 0},
            'aliases': {},
            'location': None,
            'evaluations': []
        }
        self.subhead_map = {
            'Evaluation Summary': {'function': self._summary,
                                   'key': 'rating'},
            'User Information': {'function': self._information,
                                 'key': 'location'},
            'Aliases': {'function': self._aliases,
                        'key': 'aliases'},
            'Evaluations': {'function': self._evaluations,
                            'key': 'evaluations'}
        }
        self.text_clean = regex.compile(r'\s+', regex.UNICODE)
        self.date_clean = regex.compile(r'\d{2}-\d{2}-\d{4}', regex.UNICODE)
        self.info_queue = multiprocessing.Queue()
        self.user_queue = multiprocessing.JoinableQueue()
        super().__init__()
        self.daemon = True
        self.start()

    def run(self):
        while True:
            self._state.value = b'i'
            heatware_id = self.user_queue.get()
            if heatware_id is Ellipsis:
                break
            else:
                self._state.value = b'b'
                information = self._parse(heatware_id)
                self.info_queue.put((heatware_id, information))
                self.user_queue.task_done()
        self._state.value = b'd'

    def parse(self, id_):
        self.user_queue.put(id_)

    def kill(self):
        self.user_queue.put(Ellipsis)

    def state(self):
        if self._state.value == b'i':
            return 'idle'
        if self._state.value == b'b':
            return 'busy'
        if self._state.value == b'd':
            return 'dead'
        return 'none'

    def is_idle(self):
        return self._state.value == b'i'

    def is_busy(self):
        return self._state.value == b'b'

    def is_dead(self):
        return self._state.value == b'd'

    def remaining_jobs(self):
        # Not exact.
        return self.user_queue.qsize()

    def __nonzero__(self):
        # Not reliable.
        return self.info_queue.empty()

    def __len__(self):
        # Not exact.
        return self.info_queue.qsize()

    def __iter__(self):
        try:
            while True:
                yield self.info_queue.get_nowait()
        except:
            raise StopIteration

    def _parse(self, id_):
        return self._extract(self.root_page + str(id_))

    def _extract(self, url):
        time.sleep(max(0, self.next_time - time.time()))
        info = copy.deepcopy(self.info_dict)
        page = self.get_page(url)
        html = str(page.read())
        self.next_time = self.get_next_time()
        soup = bs4.BeautifulSoup(html, _BS4_PARSER)
        for subhead in soup.find_all(class_='subhead'):
            if subhead.text in self.subhead_map:
                try:
                    info[self.subhead_map[subhead.text]['key']] = (
                        self.subhead_map[subhead.text]['function'](subhead,
                                                                   soup))
                except:
                    info[self.subhead_map[subhead.text]['key']] = (copy.deepcopy(
                        self.info_dict[self.subhead_map[subhead.text]['key']]))
        return info

    def _summary(self, spoonful, soup):
        root = spoonful.parent
        scores = root.find_all(class_='num')
        summary = {}
        for idx, item in enumerate(['positive', 'neutral', 'negative']):
            try:
                summary[item] = int(scores[idx].text)
            except:
                summary[item] = None
        return summary

    def _information(self, spoonful, soup):
        root = spoonful.parent
        info = root.find_all('div')
        for idx in range(len(info) - 1):
            prior, label = info[idx], info[idx + 1]
            if label.text == 'Location':
                return prior.text
        return None

    def _aliases(self, spoonful, soup):
        root = spoonful.parent
        links = {}
        for alias in root.find_all('div'):
            link = alias.find('a', href=True)
            try:
                alias, site = alias.text.split(' on ', 1)
                alias = alias.lower()
                if link:
                    links.setdefault(link.text.lower(), {}
                                     ).setdefault(alias, link.get('href'))
                else:
                    links.setdefault(site.lower(), {}).setdefault(alias, None)
            except:
                pass
        return links

    def _evaluations(self, spoonful, soup):
        root = spoonful.parent
        evals = {}
        for evalu in root.find_all(id=regex.compile(r'rp_[0-9]+')):
            id_ = int(evalu.get('id').strip('rp_'))
            info = {}

            try:
                info['user'] = self._clean(evalu.find('td').text)
            except:
                info['user'] = None

            try:
                info_string = soup.find(id=('row_%i' % id_)).text
                date_match = self.date_clean.search(info_string)
                info['date'] = self._clean(date_match.group(0))
                date_span = date_match.span(0)
            except:
                info['date'] = None
                date_span = None

            if date_span:
                try:
                    info['forum'] = self._clean(info_string[date_span[1]:]
                                                ).lower()
                except:
                    info['forum'] = None
            else:
                info['forum'] = None

            try:
                for inner in evalu.find_all('strong'):
                    if 'Comments' in inner.text:
                        info['comments'] = self._clean(
                            inner.parent.text.split(None, 1)[1])
            except:
                info['comments'] = None

            evals[id_] = info
        return evals

    def _clean(self, text):
        _text = text.replace('\\t', '\t'
                             ).replace('\\r', '\r'
                                       ).replace('\\n', '\n')
        return self.text_clean.sub(' ', _text)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=('Automates flair monitoring '
                                                  "for reddit's trading "
                                                  'subreddits.'),
                                     epilog=('Currently maintained by ' +
                                             ', '.join(coerce_reddit_handles()) +
                                             '.'))
    parser.add_argument('-is', '--interactive-shell', action='store_true',
                        help='run the bot with an interactive shell')
    args = parser.parse_args()
    if args.interactive_shell:
        bot_prompt().cmdloop()
    else:
        bot()
