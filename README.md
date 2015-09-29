/u/MechKBot
===========

A series of scripts utilized by the mod team of reddit's [/r/mechmarket](https://www.reddit.com/r/mechmarket) to monitor and award trade flair to its userbase.

Lovingly cloned from the source code for [/r/hardwareswap](https://www.reddit.com/r/hardwareswap)'s trade bot.

===========
List of TODOs:
  1. ~~Generalize the current config handler into something more standardized.~~
    * ~~Don't want to rely on "magic strings" if at all possible.~~
    * Done -- see `bot.config_generator` class and associated `bot.bot.CONFIG_DEFAULTS` dictionary.
  2. ~~Generate method by which to more throughly verify a user's heatware before adding their flair.~~
    * ~~May require direct crawling of the heatware site.~~
    * Done -- see `bot.heatware_crawler` class.
  3. Create handler for long-term storage of user information and associated data.
    * Would rather not have to require the user set up an external database if at all possible.
    * Considering [`shelve`](https://docs.python.org/3/library/shelve.html?highlight=shelve#module-shelve) currently -- see `bot.database_handler` class.
  4. Finalize bot state logic.
    * Any method added to the body of the `bot.bot` class that starts with the string `_state` is automatically added into its logic loop currently.
    * Need to consider whether splitting bot logic into two groups, looped and scheduled, would be useful.
      * Scheduled logic would take crontab-esk input -- [`schedule`](https://github.com/dbader/schedule) would be good for this.
      * Normal looped logic would continue to rely on the current `_state*` naming method.
  5. Finalize interactive bot console.
    * Would like to have the display split horizontally:
      * Bottom portion could display running log of the bot's actions.
      * Top portion would be used for comand input.
    * Considering [`cmd`](https://docs.python.org/3/library/cmd.html?highlight=cmd#module-cmd) currently, would require modification to get the whole "split terminal" thing working.
  6. Open-source the data!
    * It'd be great if users could download the data the bot had collected on them.
    * Could dump data to a linked Google Drive account, keep it there for ~24 hours before deleting it.
    * [`google-api-python-client`](https://github.com/google/google-api-python-client) would be useful.