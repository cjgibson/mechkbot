from ConfigParser import SafeConfigParser
from time import sleep
import logging
import os
import praw
import re
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
link_id = cfg_file.get('heatware', 'link_id')
regex = cfg_file.get('heatware', 'regex')
group = int(cfg_file.get('heatware', 'group'))
respond = cfg_file.get('heatware', 'respond')
added_msg = cfg_file.get('heatware', 'added_msg')

# Configure logging
logging.basicConfig(level=logging.INFO, filename='actions.log')
requests_log = logging.getLogger("requests")
requests_log.setLevel(logging.WARNING)


def main():
    while True:
        try:
            logging.info('Logging in as /u/' + username)
            if multiprocess == 'true':
                from praw.handlers import MultiprocessHandler
                handler = MultiprocessHandler()
                r = praw.Reddit(user_agent=username, handler=handler)
            else:
                r = praw.Reddit(user_agent=username)
            r.login(username, password)
            flaircount = 0

            # Get the submission and the comments
            submission = r.get_submission(submission_id=link_id)
            for comment in submission.comments:
                if not hasattr(comment, 'author'):
                    continue
                if comment.is_root == True:
                    logging.info('Parsing comment from /u/%s.' % comment.author)
                    heatware = re.search(regex, comment.body)
                    if heatware:
                        url = heatware.group(group)
                        if not comment.author_flair_text:
                            flaircount = flaircount + 1
                            if comment.author_flair_css_class:
                                comment.subreddit.set_flair(comment.author, url, comment.author_flair_css_class)
                            else:
                                comment.subreddit.set_flair(comment.author, url, 'i-none')
                        if respond == 'true':
                            comment.reply(added_msg)
            if flaircount > 0:
                logging.info('Set flair for ' + str(flaircount) + ' user(s)!')

        except Exception as e:
            logging.error(e)
            break

        sleep(600)

if __name__ == '__main__':
    main()
