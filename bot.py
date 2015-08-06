###
# AUTHORS: CHRISTIAN GIBSON,
# PROJECT: /r/MechMarket Bot
# UPDATED: AUGUST 05, 2015
# USAGE:   python bot.py
# EXPECTS: python 2.7.8
###

import ConfigParser
import cmd
import datetime
import errno
import praw
import regex
import shelve


class bot_prompt(cmd.Cmd):
        pass

class bot(praw.Reddit):
    def __init__(self, conf_file='config.cfg'):
        self.config_handler = config_handler(conf_file)
        super(self.__class__, self).__init__(
                                self.config_handler.get_user_agent())
        self.set_oauth_app_info(self.config_handler.get_client_id(),
                                self.config_handler.get_client_secret(),
                                self.config_handler.get_redirect_url())

class config_handler(ConfigParser.SafeConfigParser):
    def __init__(self, conf_file):
        ConfigParser.SafeConfigParser.__init__(self)
        self.conf_file = conf_file
        self.true_values = frozenset(['t', 'true', '1'])
        self.heatware_regex = None
        self.read(self.conf_file)
        if not self.sections():
            self.generate_defaults()
            self.status = errno.ENOENT
        else:
            self.status = 0
        if self.status:
            self.first_run()
    
    def protected_pull(self, section, option, cast=None, default=None):
        if self.status:
            raise EnvironmentError(self.status,
                                   ('Current status %s.' % 
                                    errno.errorcode[self.status]),
                                   self.conf_file)
        try:
            if cast:
                return cast(self.get(section, option))
            else:
                return self.get(section, option)
        except:
            return default
    
    def protected_pullboolean(self, section, option):
        boolean = self.protected_pull(section, option).lower()
        if boolean in self.true_values:
            return True
        return False
    
    def first_run(self):
        pass
    
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
        self.set('post', 'title',
                 'YOUR_POST_TITLE_HERE-SUPPORTS_STRFTIME_ARGUMENTS')
        self.set('post', 'sticky', 'false')
        self.set('post', 'msg_title', 'MESSAGE_SENT_UPON_POST_CREATION_TO_MODS')
        self.set('post', 'msg_text', 'CONTENTS_OF_MESSAGE_SENT_TO_MODS')
        
        self.add_section('flair')
        self.set('flair', 'use', 'false')
        self.set('flair', 'start', 'DEFAULT_FLAIR_VALUE_HERE')
        self.set('flair', 'limit', 'GREATEST_FLAIR_VALUE_HERE')
        self.set('flair', 'pattern',
                 'FLAIR_PATTERN_HERE_SUPPORTS_%%i_FOR_INTEGER')
        self.set('flair', 'increment',
                 'STEP_SIZE_USED_BY_FLAIR_AS_AN_INTEGER')
        
        self.add_section('crawl')
        self.set('crawl', 'file', 'DATABASE_FILE_NAME')
        self.set('crawl', 'sleep', 'TIME_TO_WAIT_BETWEEN_CRAWLS_IN_SECONDS')
        
        self.add_section('trade')
        self.set('trade', 'id', '')
        self.set('trade', 'respond',
                 'IF_THE_BOT_RESPONDS_AFTER_CONFIRMING_A_TRADE')
        self.set('trade', 'response', 'HOW_THE_BOT_RESPONDS')
        self.set('trade', 'age_msg', 'MESSAGE_USED_IF_AN_ACCOUNT_IS_TOO_YOUNG')
        self.set('trade', 'age_type',
                 'UNIT_FOR_LIMIT-seconds/minutes/hours/days')
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
    def get_user_agent(self):
        return self.protected_pull('reddit', 'user_agent')
    
    def get_client_id(self):
        return self.protected_pull('reddit', 'client_id')
    
    def get_client_secret(self):
        return self.protected_pull('reddit', 'client_secret')
    
    def get_redirect_url(self):
        return self.protected_pull('reddit', 'redirect_url')
    
    def get_subreddit(self):
        return self.protected_pull('reddit', 'subreddit')
    
    def get_multiprocess(self):
        return self.protected_pullboolean('reddit', 'multiprocess')
    
    def get_verbose(self):
        return self.protected_pullboolean('reddit', 'verbose')
    
    ''' Configuration details for the sidebar '''
    def add_button(self):
        return self.protected_pullboolean('sidebar', 'add_button')
    
    def get_button_text(self):
        return self.protected_pull('sidebar', 'button_text')
    
    def get_button_limits(self):
        return (self.protected_pull('sidebar', 'button_start'),
                self.protected_pull('sidebar', 'button_end'))
    
    ''' Configuration details for posts made by the bot '''
    def sticky_post(self):
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
            return datetime.datetime(now.year + 1, 1, 1)
    
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
        if self.heatware_regex:
            return self.heatware_regex(text)
        else:
            pattern = regex.compile(self.protected_pull('heatware', 'regex'),
                                    regex.UNICODE)
            group = self.protected_pull('heatware', 'group', int, None)
            if group:
                self.heatware_regex = lambda x : pattern.search(
                                                            text).group(group)
            else:
                self.heatware_regex = lambda x : pattern.findall(text)[0]
    
    def respond_to_heatware_request(self):
        return self.protected_pullboolean('heatware', 'respond')
    
    def get_heatware_response(self):
        return self.protected_pull('heatware', 'response')

class database_handler(shelve.DbfilenameShelf):
    def __init__(self, data_file):
        super(self.__class__, self).__init__(filename=data_file)

class heatware_crawler():
    pass

if __name__ == '__main__':
    bot_prompt().cmdloop()