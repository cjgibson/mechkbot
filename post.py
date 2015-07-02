import sys, os
import praw
import time
import re
import logging
import HTMLParser
from ConfigParser import SafeConfigParser

# load config file
containing_dir = os.path.abspath(os.path.dirname(sys.argv[0]))
cfg_file = SafeConfigParser()
path_to_cfg = os.path.join(containing_dir, 'config.cfg')
cfg_file.read(path_to_cfg)
username = cfg_file.get('reddit', 'username')
password = cfg_file.get('reddit', 'password')
subreddit = cfg_file.get('reddit', 'subreddit')
multiprocess = cfg_file.get('reddit', 'multiprocess')
start = cfg_file.get('post', 'start')
end = cfg_file.get('post', 'end')
text = cfg_file.get('post', 'text')
name = cfg_file.get('post', 'name')
msg_title = cfg_file.get('post', 'msg_title')
message = cfg_file.get('post', 'message')

# Configure logging
logging.basicConfig(level=logging.INFO, filename='post.log')
requests_log = logging.getLogger("requests")
requests_log.setLevel(logging.WARNING)

def main():
	month = time.strftime('%B')
	title = month + ' Confirmed Trade Thread'
	
	logging.info('Logging in as /u/'+username)
	if multiprocess == 'true':
		handler = MultiprocessHandler()
		r = praw.Reddit(user_agent=username, handler=handler)
	else:
		r = praw.Reddit(user_agent=username)
	r.login(username, password)

	sub = r.get_subreddit(subreddit)
	submission = r.submit(subreddit, title, text=text)
	
	# Get Sidebar Content and Sanitize it
	current_sidebar = sub.get_settings()['description']
	current_sidebar = HTMLParser.HTMLParser().unescape(current_sidebar)

	# Regex work
	replace_pattern = re.compile('%s.*?%s' % (re.escape(start), re.escape(end)), re.IGNORECASE|re.DOTALL|re.UNICODE)
	new_sidebar = re.sub(replace_pattern,
						'%s\n%s\n%s' % (start, name+'http://redd.it/'+submission.id+')', end),
						current_sidebar)
	
	# Update the Sidebar
	sub.update_settings(description=new_sidebar)

	# Update link ID in config for flair script
	cfg_file.set('trade', 'link_id', submission.id)
	cfg_file.write(open(path_to_cfg, 'w'))

	# Notify Moderators
	r.send_message('/r/'+subreddit, msg_title, message)

if __name__ == '__main__':
	main()