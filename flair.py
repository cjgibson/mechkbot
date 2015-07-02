from ConfigParser import SafeConfigParser
from datetime import datetime
from time import sleep
import logging
import os
import praw
import string
import sys


# load config file
containing_dir = os.path.abspath(os.path.dirname(sys.argv[0]))
cfg_file = SafeConfigParser()
path_to_cfg = os.path.join(containing_dir, 'config.cfg')
cfg_file.read(path_to_cfg)
username = cfg_file.get('reddit', 'username')
password = cfg_file.get('reddit', 'password')
subreddit = cfg_file.get('reddit', 'subreddit')
multiprocess = cfg_file.get('reddit', 'multiprocess')
verbose = bool(cfg_file.get('reddit', 'verbose'))
link_id = cfg_file.get('trade', 'link_id')
equal_warning = cfg_file.get('trade', 'equal_msg')
age_warning = cfg_file.get('trade', 'age_msg')
age_restriction = float(cfg_file.get('trade', 'age_res'))
karma_warning = cfg_file.get('trade', 'karma_msg')
karma_restriction = float(cfg_file.get('trade', 'karma_res'))
respond = cfg_file.get('trade', 'respond')
added_msg = cfg_file.get('trade', 'added_msg')

# Configure logging
logging.basicConfig(level=logging.INFO,
                    filename='actions.log',
                    format='%(asctime)s - %(message)s')
requests_log = logging.getLogger("requests")
requests_log.setLevel(logging.WARNING)

def main():

    def numeric_flair(item):
        try:
            return int(''.join(
                        [c for c in item.author_flair_css_class
                         if c in string.digits]))
        except:
            return 0

    def conditions(comment):
        if comment.id in completed:
            return False
        if not hasattr(comment.author, 'name'):
            return False
        if 'confirm' not in comment.body.lower():
            return False
        if comment.author.name == username:
            return False
        if comment.is_root == True:
            return False
        return True

    def check_self_reply(comment, parent):
        if comment.author.name == parent.author.name:
            comment.reply(equal_warning)
            comment.report()
            save(comment)
            parent.report()
            save(parent)
            return False
        return True

    def verify(item):
        karma = item.author.link_karma + item.author.comment_karma
        age = (datetime.utcnow() - 
               datetime.utcfromtimestamp(item.author.created_utc)).days

        if numeric_flair(item) < 1:
            if age < age_restriction:
                item.report()
                item.reply(age_warning)
                save()
                return False
            if karma < age_warning:
                item.report()
                item.reply(karma_warning)
                save()
                return False
        return True

    def values(item):
        if not item.author_flair_css_class or 'none' in item.author_flair_css_class:
            item.author_flair_css_class = 'i-1'
        elif (item.author_flair_css_class and
              any(ignore in item.author_flair_css_class
                  for ignore in ['mod', 'bot', 'mookzs', 'vendor'])):
            pass
        else:
            try:
                item.author_flair_css_class = 'i-%d' % (numeric_flair(item) + 1)
            except:
                logging.error('Failed to set flair for user with flair class "%s".'
                              % item.author_flair_css_class)
        if not item.author_flair_text:
            item.author_flair_text = ''

    def flair(item):
        if item.author_flair_css_class != 'i-mod':
            item.subreddit.set_flair(item.author, item.author_flair_text, item.author_flair_css_class)
            logging.info('Set ' + item.author.name + '\'s flair to ' + item.author_flair_css_class)

        for com in flat_comments:
            if hasattr(com.author, 'name'):
                if com.author.name == item.author.name:
                    com.author_flair_css_class = item.author_flair_css_class

    def save(comment):
        with open (link_id + ".log", 'a') as myfile:
                myfile.write('%s\n' % comment.id)

    while True:
        try:
            # Reload cfg file
            cfg_file.read(path_to_cfg)

            # Load old comments
            with open (link_id + ".log", 'a+') as myfile:
                completed = myfile.read()

            # Log in
            logging.info('Logging in as /u/' + username)
            if multiprocess == 'true':
                from praw.handlers import MultiprocessHandler
                handler = MultiprocessHandler()
                r = praw.Reddit(user_agent=username, handler=handler)
            else:
                r = praw.Reddit(user_agent=username)
            if verbose: print 'Logging in as /u/%s.' % username
            r.login(username, password)

            # Get the submission and the comments
            submission = r.get_submission(submission_id=link_id)
            submission.replace_more_comments(limit=None, threshold=0)
            flat_comments = list(praw.helpers.flatten_tree(submission.comments))

            for comment in flat_comments:
                if verbose: print 'Parsing: "%s"' % comment.body

                if not conditions(comment):
                    continue
                parent = [com for com in flat_comments
                          if com.fullname == comment.parent_id][0]
                if not check_self_reply(comment, parent):
                    if verbose: print '/u/%s attempted to trade with themselves.' % comment.author
                    continue

                # Check Account Age and Karma
                if not verify(comment):
                    continue
                if not verify(parent):
                    continue

                # Get Future Values to Flair
                values(comment)
                values(parent)

                # Flairs up in here
                flair(comment)
                flair(parent)
                comment.reply(added_msg)
                save(comment)

        except Exception as e:
            print traceback.format_exc()
            logging.error(e)

        sleep(float(cfg_file.get('trade', 'sleep')))

if __name__ == '__main__':
    main()
