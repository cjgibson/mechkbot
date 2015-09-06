###
# AUTHORS: CHRISTIAN GIBSON,
# PROJECT: /r/MechMarket Bot
# UPDATED: SEPTEMBER 5, 2015
# USAGE:   python bot.py [-h / --help] [-ns / --no-shell]
# EXPECTS: python 3.4.0
#          beautifulsoup4 4.4.0
#          regex 2015.06.24
###

import argparse
import bs4
import cmd
import configparser
import copy
import datetime
import errno
import inspect
import logging
import os
import praw
import random
import regex
import shelve
import shutil
import time
import urllib


class config_generator():
    _FUNC_CODE_ = """class config_handler(configparser.ConfigParser):

    def __init__(self, conf_file=None):
        super(self.__class__, self).__init__()

        self.true_values = frozenset(['true', 't', '1', 'y', 'yes', 'aye'])
        self.heatware_regex = None

        if conf_file:
            try:
                self.conf_file = os.path.abspath(conf_file)
            except:
                pass
        else:
            try:
                self.conf_file = (os.path.dirname(os.path.abspath(
                    inspect.getsourcefile(lambda _: None))) + '/config.cfg')
            except:
                self.status = errno.EBADFD
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
                self.status = errno.EIO

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

        added_methods['generate_defaults'] = '\n'.join(init_defaults) + '\n'
        _func_code_ = self._FUNC_CODE_ + '\n'.join(added_methods.values())
        exec(compile(_func_code_, '<string>', 'exec'))
        return eval('config_handler')

__AUTHORS__ = ['/u/NotMelNoGuitars']
__VERSION__ = 0.1
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
        'crawl': {'file': {'def': 'data.record'},
                  'sleep': {'def': '300'}},
        'reddit': {'user_agent': {},
                   'client_id': {},
                   'client_secret': {},
                   'redirect_url': {},
                   'subreddit': {},
                   'multiprocess': {'def': 'false',
                                    'get': 'is_multiprocessed',
                                    'set': None},
                   'verbose': {'def': 'true',
                               'get': 'is_verbose',
                               'set': 'set_verbose'}},
        'monitor': {'log': {'def': 'run.log'},
                    'new': {'def': 'true'},
                    'record': {'def': 'true'},
                    'format': {'def': '%(created)d -- %(levelname)s \t-> %(message)s'},
                    'summary': {'def': 'false'},
                    'respond': {'def': 'true'},
                    'heatware': {'def': 'true'}},
        'sidebar': {'add_button': {'def': 'false',
                                   'get': 'should_add_button'},
                    'button_text': {},
                    'button_start': {},
                    'button_end': {}},
        'flair': {'method': {'def': 'pm'},
                  'post_id': {},
                  'post_text': {},
                  'post_rate': {'def': 'yearly'},
                  'post_title': {},
                  'post_sticky': {'def': 'false'},
                  'message_text': {},
                  'message_title': {},
                  'use': {'def': 'true'},
                  'start': {},
                  'limit': {},
                  'pattern': {},
                  'increment': {}},
        'trade': {'method': {'def': 'pm'},
                  'post_id': {},
                  'post_text': {},
                  'post_rate': {'def': 'monthly'},
                  'post_title': {},
                  'post_sticky': {'def': 'false'},
                  'message_text': {},
                  'message_title': {},
                  'respond': {'def': 'false'},
                  'response': {},
                  'age_msg': {},
                  'age_type': {'def': 'days'},
                  'age_limit': {'def': '30'},
                  'same_msg': {},
                  'karma_msg': {},
                  'karma_type': {'def': 'comment'},
                  'karma_limit': {'def': '100'}},
        'heatware': {'method': {'def': 'pm'},
                     'post_id': {},
                     'post_text': {},
                     'post_rate': {'def': 'yearly'},
                     'post_title': {},
                     'post_sticky': {},
                     'message_text': {},
                     'message_title': {},
                     'regex': {'def': '(?:.*)(http(?:s?)://www\.heatware\.com/eval\.php\?id=[0-9]+)(?:.*)'},
                     'group': {'def': '1'},
                     'respond': {},
                     'response': {}}}

    def __init__(self, conf_file='config.cfg', log_file='record.log'):
        config_constructor = _GET_CONFIG(self.CONFIG_DEFAULTS)
        self.config_handler = config_constructor(conf_file)
        if log_file:
            log = logging.StreamHandler(log_file)
            fmt = logging.Formatter(self.config_handler.get_log_format())
            log.setLevel(logging.DEBUG)
            log.setFormatter(fmt)
            logger.addHandler(log)
        super(self.__class__, self).__init__(
            self.config_handler.get_user_agent())
        self.set_oauth_app_info(self.config_handler.get_client_id(),
                                self.config_handler.get_client_secret(),
                                self.config_handler.get_redirect_url())


class config_handler(configparser.SafeConfigParser):

    def __init__(self, conf_file=None):
        super(self.__class__, self).__init__()

        self.true_values = frozenset(['true', 't', '1', 'y', 'yes', 'aye'])
        self.heatware_regex = None

        if conf_file:
            self.conf_file = conf_file
        else:
            try:
                self.conf_file = (os.path.dirname(os.path.abspath(
                    inspect.getsourcefile(lambda _: None))) + 'config.cfg')
            except:
                self.status = errno.EBADFD
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
                self.status = errno.EIO

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
            return True
        except:
            return False

    def protected_pushboolean(self, section, option, value):
        if value is True or value in self.true_values:
            return self.protected_push(section, option, 'true')
        return self.protected_push(section, option, 'false')

    def generate_defaults(self):
        self.add_section('reddit')
        self.set('reddit', 'user_agent', 'YOUR_USER_AGENT_HERE')
        self.set('reddit', 'client_id', 'YOUR_APPLICATION_ID_HERE')
        self.set('reddit', 'client_secret', 'YOUR_APPLICATION_SECRET_HERE')
        self.set('reddit', 'redirect_url', 'YOUR_APPLICATION_REDIRECT_HERE')
        self.set('reddit', 'subreddit', 'YOUR_TARGET_SUBREDDIT_HERE')
        self.set('reddit', 'multiprocess', 'false')
        self.set('reddit', 'verbose', 'true')

        self.add_section('sidebar')
        self.set('sidebar', 'add_button', 'false')
        self.set('sidebar', 'button_text', 'YOUR_BUTTON_TEXT_HERE')
        self.set('sidebar', 'button_start', 'TAG_INDICATING_START_OF_BUTTON')
        self.set('sidebar', 'button_end', 'TAG_INDICATING_END_OF_BUTTON')

        self.add_section('post')
        self.set('post', 'id', '')
        self.set('post', 'text', 'YOUR_POST_TEXT_HERE')
        self.set('post', 'rate', 'YOUR_POST_RATE_HERE-daily/monthly/yearly')
        self.set('post', 'title', 'YOUR_POST_TITLE_HERE-SUPPORTS_STRFTIME')
        self.set('post', 'sticky', 'false')
        self.set('post', 'msg_title', 'MESSAGE_SENT_TO_MODS_WHEN_POST_CREATED')
        self.set('post', 'msg_text', 'CONTENTS_OF_MESSAGE_SENT_TO_MODS')

        self.add_section('flair')
        self.set('flair', 'use', 'false')
        self.set('flair', 'start', 'DEFAULT_FLAIR_VALUE_HERE')
        self.set('flair', 'limit', 'GREATEST_FLAIR_VALUE_HERE')
        self.set('flair', 'pattern', 'FLAIR_PATTERN_HERE_SUPPORTS_%%i_FOR_INT')
        self.set('flair', 'increment', 'STEP_SIZE_USED_BY_FLAIR_AS_INTEGER')

        self.add_section('crawl')
        self.set('crawl', 'file', 'DATABASE_FILE_NAME')
        self.set('crawl', 'sleep', 'TIME_TO_WAIT_BETWEEN_CRAWLS_IN_SECONDS')

        self.add_section('monitor')
        self.set('monitor', 'log', 'PATH_FOR_LOG_FILE_HERE')
        self.set('monitor', 'new', 'MONITOR_NEW_USER_POSTS-true_false')
        self.set('monitor', 'crawl', 'RECORD_USER_HEATWARE_HISTORY-true_false')
        self.set('monitor', 'record', 'RECORD_USER_TRADE_HISTORY-true_false')
        self.set('monitor', 'format', ('%(created)d -- %(levelname)s '
                                       '\t-> %(message)s'))
        self.set('monitor', 'summary', 'PROVIDE_USER_HISTORY-true_false')
        self.set('monitor', 'respond', 'PROVIDE_HISTORY_THROUGH_PM-true_false')

        self.add_section('trade')
        self.set('trade', 'id', '')
        self.set('trade', 'respond', 'IF_THE_BOT_RESPONDS_AFTER_TRADE_CONFIRM')
        self.set('trade', 'response', 'HOW_THE_BOT_RESPONDS')
        self.set('trade', 'age_msg', 'MESSAGE_USED_IF_AN_ACCOUNT_IS_TOO_YOUNG')
        self.set('trade', 'age_type', 'LIMIT_UNIT-seconds/minutes/hours/days')
        self.set('trade', 'age_limit', 'NUMERICAL_LIMIT_FOR_USER_AGE')
        self.set('trade', 'same_msg',
                 'MESSAGE_USED_IF_AN_ACCOUNT_TRADES_WITH_ITSELF')
        self.set('trade', 'karma_msg',
                 'MESSAGE_USED_IF_AN_ACCOUNT_HAS_TOO_LITTLE_KARMA')
        self.set('trade', 'karma_type',
                 'WHAT_KARMA_TO_CONSIDER-comment/link/both')
        self.set('trade', 'karma_limit', 'NUMERICAL_LIMIT_FOR_USER_KARMA')

        self.add_section('heatware')
        self.set('heatware', 'post_id', '')
        self.set('heatware', 'post_text', 'YOUR_POST_TEXT_HERE')
        self.set('heatware', 'post_rate', 'YOUR_POST_RATE_HERE-yearly/maximum')
        self.set('heatware', 'post_title', 'YOUR_POST_TITLE_HERE')
        self.set('heatware', 'post_sticky', 'false')
        self.set('heatware', 'regex',
                 '(?:.*)(http(?:s?)://www\.heatware\.com/eval\.php\?id=[0-9]+)(?:.*)')
        self.set('heatware', 'group', '1')
        self.set('heatware', 'respond',
                 'IF_THE_BOT_RESPONDS_AFTER_RECORDING_HEATWARE')
        self.set('heatware', 'response', 'HOW_THE_BOT_RESPONDS')

    ''' Core reddit configuration details '''

    def set_user_agent(self, user_agent):
        return self.protected_push('reddit', 'user_agent', user_agent)

    def get_user_agent(self):
        return self.protected_pull('reddit', 'user_agent')

    def set_client_id(self, client_id):
        return self.protected_push('reddit', 'client_id', client_id)

    def get_client_id(self):
        return self.protected_pull('reddit', 'client_id')

    def set_client_secret(self, client_secret):
        return self.protected_push('reddit', 'client_secret', client_secret)

    def get_client_secret(self):
        return self.protected_pull('reddit', 'client_secret')

    def set_redirect_url(self, redirect_url):
        return self.protected_push('reddit', 'redirect_url', redirect_url)

    def get_redirect_url(self):
        return self.protected_pull('reddit', 'redirect_url')

    def set_subreddit(self, subreddit):
        return self.protected_push('reddit', 'subreddit', subreddit)

    def get_subreddit(self):
        return self.protected_pull('reddit', 'subreddit')

    def is_multiprocess(self):
        return self.protected_pullboolean('reddit', 'multiprocess')

    def is_verbose(self):
        return self.protected_pullboolean('reddit', 'verbose')

    ''' Configuration details for the sidebar '''

    def add_button(self):
        return self.protected_pullboolean('sidebar', 'add_button')

    def set_button_text(self, button_text):
        return self.protected_push('sidebar', 'button_text', button_text)

    def get_button_text(self):
        return self.protected_pull('sidebar', 'button_text')

    def get_button_limits(self):
        return (self.protected_pull('sidebar', 'button_start'),
                self.protected_pull('sidebar', 'button_end'))

    ''' Configuration details for posts made by the bot '''

    def make_sticky_post(self):
        return self.protected_pullboolean('post', 'sticky')

    def get_post_title(self):
        return datetime.datetime.now().strftime(
            self.protected_pull('post', 'title'))

    def get_post_rate(self):
        now = datetime.datetime.now()
        rate = self.protected_pull('post', 'rate')
        if 'da' in rate:
            return datetime.datetime(now.year, now.month, now.day + 1)
        elif 'month' in rate:
            return datetime.datetime(now.year, now.month + 1, 1)
        elif 'year' in rate:
            return datetime.datetime(now.year + 1, now.month, 1)

    def get_post_text(self):
        return self.protected_pull('post', 'text')

    def get_post_id(self):
        return self.protected_pull('post', 'id')

    def get_message_content(self):
        return (self.protected_pull('post', 'msg_title'),
                self.protected_pull('post', 'msg_text'))

    ''' Configuration details for updating a user's flair '''

    def use_flair(self):
        return self.protected_pullboolean('flair', 'use')

    def get_flair_start(self):
        return self.protected_pull('flair', 'start')

    def get_flair_limit(self):
        return self.protected_pull('flair', 'limit')

    def get_flair_pattern(self):
        return self.protected_pull('flair', 'pattern')

    def get_flair_increment(self):
        return self.protected_pull('flair', 'increment', int)

    ''' Configuration details for crawling reddit '''

    def get_data_file(self):
        return self.protected_pull('crawl', 'file')

    def get_sleep_interval(self):
        return self.protected_pull('crawl', 'sleep', float)

    ''' Configuration details for handling user history '''

    def get_log_file_path(self):
        return self.protected_pull('monitor', 'log')

    def monitor_new_posts(self):
        return self.protected_pullboolean('monitor', 'new')

    def monitor_external(self):
        return self.protected_pullboolean('monitor', 'crawl')

    def get_log_format(self):
        return self.protected_pull('monitor', 'format')

    def record_history(self):
        return self.protected_pullboolean('monitor', 'record')

    def post_summary(self):
        return self.protected_pullboolean('monitor', 'summary')

    def reply_summary(self):
        return self.protected_pullboolean('monitor', 'respond')

    ''' Configuration details for analyzing trade threads '''

    def get_trade_thread_id(self):
        return self.protected_pull('trade', 'id')

    def respond_to_trade(self):
        return self.protected_pullboolean('trade', 'respond')

    def get_trade_response(self):
        return self.protected_pull('trade', 'response')

    def get_age_limitation(self):
        age_type = self.protected_pull('trade', 'age_type').lower()
        if 'day' in age_type:
            age_type = 24 * 60 * 60
        elif 'hour' in age_type:
            age_type = 60 * 60
        elif 'minute' in age_type:
            age_type = 60
        elif 'second' in age_type:
            age_type = 1
        else:
            raise ValueError
        return age_type * self.protected_pull('trade', 'age_limit', float)

    def get_age_message(self):
        return self.protected_pull('trade', 'age_msg')

    def get_karma_limitation(self):
        return self.protected_pull('trade', 'karma_limit', int)

    def get_karma_limitation_type(self):
        return self.protected_pull('trade', 'karma_type')

    def get_karma_message(self):
        return self.protected_pull('trade', 'karma_msg')

    def get_same_account_message(self):
        return self.protected_pull('trade', 'same_msg')

    ''' Configuration details for analyzing heatware threads '''

    def get_heatware_thread_id(self):
        return self.protected_pull('heatware', 'post_id')

    def get_heatware_thread_text(self):
        return self.protected_pull('heatware', 'post_text')

    def get_heatware_thread_rate(self):
        rate = self.protected_pull('heatware', 'post_rate')
        if 'maximum' in rate:
            return float('inf')
        else:
            return 365 * 24 * 60 * 60

    def get_heatware_thread_title(self):
        return self.protected_pull('heatware', 'post_title')

    def get_heatware_thread_sticky(self):
        return self.protected_pullboolean('heatware', 'post_sticky')

    def filter_heatware_url(self, text):
        if not self.heatware_regex:
            pattern = regex.compile(self.protected_pull('heatware', 'regex'),
                                    regex.UNICODE)
            group = self.protected_pull('heatware', 'group', int, None)
            if group:
                self.heatware_regex = lambda x: pattern.search(x).group(group)
            else:
                self.heatware_regex = lambda x: pattern.findall(x)[0]
        return self.heatware_regex(text)

    def respond_to_heatware_request(self):
        return self.protected_pullboolean('heatware', 'respond')

    def get_heatware_response(self):
        return self.protected_pull('heatware', 'response')


class database_handler(shelve.DbfilenameShelf):

    def __init__(self, data_file):
        super(self.__class__, self).__init__(filename=data_file)


class heatware_crawler():

    def __init__(self, deep_parse=False, page_wait=1 * 60, rand_wait=False):
        self.deep_parse = deep_parse
        self.page_wait = max(60, page_wait)
        self.rand_wait = rand_wait
        self.next_time = time.time()
        self.get_next_time = lambda: (time.time() + self.page_wait +
                                      (random.uniform(5, 10) if self.rand_wait
                                       else 0))
        self.get_page = urllib.request.urlopen
        self.root_page = 'www.heatware.com/eval.php?id='
        self.page_ext = '&pagenum=%i'
        self.eval_ext = '&num_days=%i'
        self.info_dict = {'deep_parse': self.deep_parse,
                          'rating': {'positive': 0,
                                     'neutral': 0,
                                     'negative': 0},
                          'aliases': {},
                          'location': None,
                          'evaluations': []}
        self.subhead_map = {'Evaluation Summary': {'function': self._summary,
                                                   'key': 'rating'},
                            'User Information': {'function': self._information,
                                                 'key': 'location'},
                            'Aliases': {'function': self._aliases,
                                        'key': 'aliases'},
                            'Evaluations': {'function': self._evaluations,
                                            'key': 'evaluations'}}
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
                    links[(alias, link.text.lower())] = link.get('href')
                else:
                    links[(alias, site.lower())] = None
            except:
                pass
        return links

    def _evaluations(self, spoonful, soup):
        root = spoonful.parent
        evals = []
        for evalu in root.find_all(id=regex.compile(r'rp_[0-9]+')):
            info = {'id': int(evalu.get('id').strip('rp_'))}

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

            evals.append(info)
        return evals

    def _clean(self, text):
        _text = text.replace('\\t', '\t'
                             ).replace('\\r', '\r'
                                       ).replace('\\n', '\n')
        return self.text_clean.sub(' ', _text)

if __name__ == '__main__':
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

    parser = argparse.ArgumentParser(description=('Automates flair monitoring '
                                                  "for reddit's trading "
                                                  'subreddits.'),
                                     epilog=('Currently maintained by ' +
                                             ', '.join(coerce_reddit_handles()) +
                                             '.'))
    parser.add_argument('-ns', '--no-shell', action='store_true',
                        help='run the bot without its shell')
    args = parser.parse_args()
    if args.no_shell:
        bot()
    else:
        bot_prompt().cmdloop()
