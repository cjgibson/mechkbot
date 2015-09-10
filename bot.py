# -*- coding: utf-8 -*-
###
# AUTHORS: CHRISTIAN GIBSON,
# PROJECT: /r/MechMarket Bot
# UPDATED: SEPTEMBER 5, 2015
# USAGE:   python bot.py [-h / --help] [-is / --interactive-shell]
# EXPECTS: python 3.4.0
#          beautifulsoup4 4.4.0
#          regex 2015.06.24
###

import argparse
import bs4
import cmd
import collections
import configparser
import copy
import datetime
import errno
import inspect
import logging
import math
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
__INFO__ = 'MechKBot-v%s on "%s" with << %s v%s >> at %s %s' % (
    __VERSION__,
    platform.platform(),
    platform.python_implementation(),
    platform.python_version(),
    time.ctime(),
    time.localtime().tm_zone)


def coerce_reddit_handles():
    clean = regex.compile(r'[^A-Z0-9_/-]',
                          regex.UNICODE + regex.IGNORECASE)
    authors = []
    for author in __AUTHORS__:
        author = clean.sub('', str(author))
        if author.startswith('/u/') or author.startswith('/r/'):
            authors.append(author)
        else:
            authors.append('/u/' + max(author.split('/'), key=len))
    return authors


class config_generator():
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

    def __call__(self, sections):
        added_methods = {'generate_defaults': None}
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
                    raise TypeError
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
                    raise TypeError
                if set_method:
                    added_methods[set_method] = (
                        "    def %s(self, value):\n"
                        "        return self.%s('%s', '%s', value)\n"
                        % (set_method, pushtype, section, option))

                try:
                    if 'def' in detail:
                        init_defaults.append("        self.set('%s', '%s', '%s')"
                                             % (section, option, detail['def']))
                    else:
                        init_defaults.append("        self.set('%s', '%s', '%s')"
                                             % (section, option, ""))
                except:
                    raise TypeError

        added_methods['generate_defaults'] = ('\n'.join(init_defaults) + '\n' +
                                              '        self.store()\n')
        _func_code_ = self._FUNC_CODE_ + '\n'.join(added_methods.values())
        exec(compile(_func_code_, '<string>', 'exec'))
        config = eval('config_handler')
        config.func_code = _func_code_
        return config

_BS4_PARSER = 'html.parser'
_GET_CONFIG = config_generator()
logger = logging.getLogger()
logger.setLevel(logging.INFO)


class bot_prompt(cmd.Cmd):
    # errno.ENOTTY

    def __init__(self):
        super(self.__class__, self).__init__()
        self.prompt = '>>> '
        self.size = shutil.get_terminal_size()
        self.height, self.width = self.size.lines, self.size.columns


class bot(praw.Reddit):

    CONFIG_DEFAULTS = {
        'crawl': collections.OrderedDict([
            ('file', {'def': 'data.record',
                      'desc': ('This is the name of the flatfile that will be '
                               'used to store all collected data on a user-by-'
                               'user basis.')}),
            ('hold', {'def': '10',
                      'desc': ('This is the number of seconds the bot will '
                               'spend in each state as a minimum.\nAs an '
                               'example, the bot has three states by default:\n'
                               ' 1. Crawling /new of the target subreddit.\n'
                               ' 2. Responding to user PMs.\n'
                               ' 3. Crawling the trade thread of the target '
                               'subreddit.')}),
            ('sleep', {'def': '100',
                       'desc': ('This is the number of seconds the bot will '
                                'spend doing nothing after completing each set '
                                'of states.')})
        ]),
        'reddit': collections.OrderedDict([
            ('user_agent', {'def': ('%s-%s:%s:MechKBot-v%s (by %s)' %
                                    (platform.system(), platform.processor(),
                                     uuid.uuid5(uuid.NAMESPACE_OID, __INFO__),
                                     __VERSION__,
                                     ', '.join(coerce_reddit_handles()))),
                            'desc': ('This is the plaintext string that will '
                                     'be used by the admin\'s at reddit to '
                                     'identify this bot. It is recommended '
                                     'that bots follow the format:\n'
                                     '  <platform>:<app ID>:<version string> '
                                     '(by /u/<reddit username>)\n'
                                     'Full rules and restrictions can be '
                                     'found here: https://github.com/reddit/'
                                     'reddit/wiki/API.')}),
            ('client_id', {'desc': ('This is the OAuth2 client_id created '
                                    'for your reddit app instance.')}),
            ('client_secret', {'desc': ('This is the OAuth2 client_secret '
                                        'created for your reddit app instance.')}),
            ('redirect_url', {'desc': ('This is the OAuth2 redirect_url created '
                                       'for your reddit app instance.')}),
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
        ]),
        'monitor': collections.OrderedDict([
            ('log', {'def': 'event.log',
                     'desc': ('This is the flatfile that will be used to log '
                              'all actions taken by the bot.')}),
            ('posts', {'def': 'true',
                       'desc': ('Whether or not the bot will log basic '
                                'information concerning all posts observed '
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
                                 'time when event was logged.\n'
                                 ' %(message)s: Message provided when event was'
                                 ' logged.\n'
                                 ' %(name)s: Name of the logger used to create '
                                 'the logged event.\n'
                                 ' %(pathname)s: Full pathname of the source '
                                 'file that created the logged event.\n'
                                 ' %(process)d: Process ID that created the '
                                 'logged event.\n'
                                 ' %(processName)s: Process Name that created '
                                 'the logged event.\n'
                                 ' %(relativeCreated)d: Milliseconds after the '
                                 'logging module was initially loaded that an '
                                 'event was logged.\n'
                                 ' %(thread)d: Thread ID that created the '
                                 'logged event.\n'
                                 ' %(threadName)s: Thread Name that created '
                                 'the logged event.\n'
                                 'Further information can be found at-- '
                                 'https://docs.python.org/3.4/library/logging.'
                                 'html#logging.LogRecord\n')}),
        ]),
        'sidebar': collections.OrderedDict([
            ('add_button', {'def': 'false',
                            'get': 'should_add_button',
                            'boolean': True}),
            ('button_text', {}),
            ('button_start', {}),
            ('button_end', {})
        ]),
        'flair': collections.OrderedDict([
            ('use', {'def': 'true',
                     'boolean': True}),
            ('start', {}),
            ('limit', {}),
            ('ignore', {}),
            ('pattern', {}),
            ('increment', {})
        ]),
        'trade': collections.OrderedDict([
            ('method', {'def': 'post'}),
            ('post_id', {}),
            ('post_text', {}),
            ('post_rate', {'def': 'monthly'}),
            ('post_title', {}),
            ('post_sticky', {'def': 'false'}),
            ('message_text', {}),
            ('message_title', {}),
            ('respond', {'def': 'false',
                         'boolean': True}),
            ('response', {}),
            ('age_msg', {}),
            ('age_type', {'def': 'days'}),
            ('age_limit', {'def': '30'}),
            ('same_msg', {}),
            ('karma_msg', {}),
            ('karma_type', {'def': 'comment'}),
            ('karma_limit', {'def': '100'})
        ]),
        'heatware': collections.OrderedDict([
            ('method', {'def': 'pm'}),
            ('post_id', {}),
            ('post_text', {}),
            ('post_rate', {'def': 'yearly'}),
            ('post_title', {}),
            ('post_sticky', {}),
            ('message_text', {}),
            ('message_title', {}),
            ('regex', {'def': '(?:.*)(http(?:s?)://www\.heatware\.com/eval\.php\?id=[0-9]+)(?:.*)',
                       'set': None}),
            ('group', {'def': '1',
                       'set': None}),
            ('respond', {'def': 'true',
                         'boolean': True}),
            ('response', {})
        ])
    }

    def __init__(self, conf_file=None):
        config_constructor = _GET_CONFIG(self.CONFIG_DEFAULTS)
        self.config_handler = config_constructor(conf_file)
        if self.config_handler.status:
            print("Configuration file is in invalid state.")
            print("Run bot with --interactive-shell option to rectify.")
            raise EnvironmentError(self.status,
                                   ('Current status #%d <%s> "%s".' %
                                    (self.status,
                                     errno.errorcode[self.status],
                                     os.strerror(self.status))),
                                   conf_file)
        log = logging.StreamHandler(self.config_handler.get_monitor_log())
        fmt = logging.Formatter(self.config_handler.get_monitor_format())
        log.setLevel(logging.DEBUG)
        log.setFormatter(fmt)
        logger.addHandler(log)
        self.data_store = database_handler(
            self.config_handler.get_crawl_file())
        super(self.__class__, self).__init__(
            self.config_handler.get_reddit_user_agent())
        self.set_oauth_app_info(self.config_handler.get_reddit_client_id(),
                                self.config_handler.get_reddit_client_secret(),
                                self.config_handler.get_reddit_redirect_url())


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
            cur = self.get(key)
            _ = self.update(val, cur)
            self[key.lower()] = val
            return True
        except:
            return False

    def remove(self, key):
        try:
            del self[key]
            return True
        except:
            return False

    def update(self, new_, orig):
        for key, val in orig.items():
            if isinstance(val, collections.Mapping):
                new_[key] = self.update(new_.get(key, {}), val)
            else:
                new_[key] = orig[key]
        return new_

    def terminate(self):
        self.sync()
        self.close()


class heatware_crawler():

    def __init__(self, page_wait=0, deep_parse=False, rand_wait=False):
        # TODO: See if heat is okay with maximum one request per sixty seconds.
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

    def parse(self, url):
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

    def parse_id(self, id_):
        return self.parse(self.root_page + str(id_))

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
                info_string = soup.find(id=('row_%i' % info['id'])).text
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
